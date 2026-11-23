"""ClipForge AI — Dedicated background worker process.

Continuously claims jobs from the durable SQLite queue, handles video probing,
proxy generation, transcription, AI analysis, rendering, and publishing.
"""

from __future__ import annotations

import httpx
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
import time
from typing import Any, Dict

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import Clip, Job, Project, PublishingJob, Transcript, User, VideoSource
from app.ingestion import AwaitReplay
from app.queue import DurableQueue, get_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Worker) %(message)s",
)
logger = logging.getLogger("clipforge.worker")


class MediaWorker:
    def __init__(self) -> None:
        self.queue = get_queue()
        self.running = True
        self.settings = get_settings()

    def start(self) -> None:
        """Start the worker execution loop."""
        logger.info("ClipForge Media Worker started (ID: %s)", self.queue.worker_id)
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        # Recover stale jobs from previous unexpected terminations
        recovered = self.queue.recover_stale_jobs()
        if recovered:
            logger.info("Recovered %d stale jobs", recovered)

        next_recovery = time.monotonic() + 30
        while self.running:
            try:
                if time.monotonic() >= next_recovery:
                    self.queue.recover_stale_jobs()
                    next_recovery = time.monotonic() + 30
                job = self.queue.claim_next(max_downloads=self.settings.MAX_CONCURRENT_DOWNLOADS)
                if job:
                    self._process_job(job)
                else:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                logger.info("Worker shutdown requested via KeyboardInterrupt")
                self.running = False
            except Exception as exc:
                logger.error("Unexpected worker loop error: %s", exc, exc_info=True)
                time.sleep(2.0)

    def _process_job(self, job: Job) -> None:
        logger.info("Processing job %s (Task: %s)", job.id, job.task_type)
        payload = job.get_payload()

        stop_heartbeat = Event()
        heartbeat_thread = None
        if job.task_type == "import_recording":
            def renew():
                while not stop_heartbeat.wait(10):
                    try:
                        if not self.queue.heartbeat(job.id, keep_cancelled_import=True):
                            return
                    except Exception:
                        logger.warning("Could not renew import lease for %s", job.id, exc_info=True)

            heartbeat_thread = Thread(target=renew, daemon=True)
            heartbeat_thread.start()

        try:
            self.checkpoint(job)
            handler = getattr(self, f"handle_{job.task_type}", None)
            if not handler:
                raise ValueError(f"Unknown task type: {job.task_type}")

            result = handler(job, payload)
            self.queue.complete(job.id, result=result)
        except AwaitReplay:
            self.queue.defer_network(job.id, "Live stream: waiting for completed VOD", 300)
        except Exception as exc:
            if job.task_type == "detect_moments" and (isinstance(exc, httpx.TransportError) or
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (408,429,500,502,503,504)):
                self.queue.defer_network(job.id)
                return
            logger.error("Job %s execution failed: %s", job.id, exc)
            self.queue.fail(job.id, str(exc))
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join()
                self.queue.release_cancelled_import(job.id)

    def handle_import_recording(self, job, payload):
        from app.ingestion import acquire
        with SessionLocal() as session:
            video = session.query(VideoSource).filter_by(source_url=payload["url"]).first()
            if video is None:
                directory = Path("storage/uploads")
                directory.mkdir(parents=True, exist_ok=True)
                path, title = acquire(payload["url"], directory / job.id, self, job.id, payload.get("quality", "best"))
                project = session.query(Project).first()
                if project is None:
                    raise ValueError("Default workspace is unavailable")
                video = VideoSource(project_id=project.id, filename=path.name,
                                    original_filename=title[:256], source_type=payload["provider"],
                                    source_url=payload["url"], file_path=str(path),
                                    file_size_bytes=path.stat().st_size, status="processing")
                session.add(video)
                session.commit()
            video_id = video.id
        try:
            result = self.handle_video_probe(job, {"video_id": video_id})
            self.next_stage(job, "transcribe", video_id)
            return result
        except Exception:
            with SessionLocal() as session:
                session.get(VideoSource, video_id).status = "failed"
                session.commit()
            raise

    def handle_video_probe(self, job: Job, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Probe media file, extract duration/dimensions/codec/FPS, and generate thumbnail & proxy."""
        video_id = payload.get("video_id")
        self.queue.update_progress(job.id, 10, "Probing video file...")

        with SessionLocal() as session:
            video = session.get(VideoSource, video_id)
            if not video:
                raise ValueError(f"Video {video_id} not found")

            file_path = str(Path(video.file_path).resolve())
            ffmpeg_path = self.settings.get_ffmpeg_binary()
            ffprobe_path = self.settings.get_ffprobe_binary()

            duration = 60.0
            width = 1920
            height = 1080
            fps = 30.0
            codec = "h264"
            audio_channels = 2

            # 1. Run real ffprobe if available
            try:
                cmd = [
                    ffprobe_path,
                    "-v", "error",
                    "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name,channels",
                    "-of", "json",
                    file_path,
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if res.returncode == 0:
                    import json
                    meta = json.loads(res.stdout)
                    fmt_dur = meta.get("format", {}).get("duration")
                    if fmt_dur:
                        duration = float(fmt_dur)
                    streams = meta.get("streams", [])
                    if not fmt_dur or duration <= 0 or not any(s.get("width", 0) > 0 and s.get("height", 0) > 0 for s in streams):
                        raise ValueError("Missing video stream or duration")
                    for s in streams:
                        if "width" in s and "height" in s and width == 1920:
                            width = int(s["width"])
                            height = int(s["height"])
                            codec = s.get("codec_name", "h264")
                            r_fps = s.get("r_frame_rate", "30/1")
                            if "/" in r_fps:
                                num, den = r_fps.split("/")
                                fps = round(float(num) / max(1.0, float(den)), 2)
                        if "channels" in s:
                            audio_channels = int(s["channels"])
                else:
                    raise ValueError("FFprobe rejected the source media")
            except Exception as e:
                raise ValueError("Could not probe the source media") from e

            self.queue.update_progress(job.id, 40, "Generating video thumbnail...")
            # 2. Generate thumbnail via FFmpeg
            thumb_dir = Path("storage/thumbnails")
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_file = thumb_dir / f"thumb_{video.id}.jpg"
            thumb_time = min(2.0, max(0.5, duration / 2.0))

            try:
                thumb_cmd = [
                    ffmpeg_path,
                    "-y",
                    "-ss", str(thumb_time),
                    "-i", file_path,
                    "-vframes", "1",
                    "-vf", "scale=640:-1",
                    "-q:v", "2",
                    str(thumb_file.resolve()),
                ]
                subprocess.run(thumb_cmd, capture_output=True, text=True, timeout=15)
                if thumb_file.exists():
                    video.thumbnail_path = f"/storage/thumbnails/{thumb_file.name}"
            except Exception as e:
                logger.warning("Thumbnail generation skipped: %s", e)

            # 3. Generate low-res proxy (360p) for ultra-fast browser scrubbing
            self.queue.update_progress(job.id, 70, "Generating lightweight editing proxy...")
            proxy_dir = Path("storage/proxies")
            proxy_dir.mkdir(parents=True, exist_ok=True)
            proxy_file = proxy_dir / f"proxy_{video.id}.mp4"

            try:
                proxy_cmd = [
                    ffmpeg_path,
                    "-y",
                    "-i", file_path,
                    "-vf", "scale=-2:360",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "28",
                    "-c:a", "aac",
                    "-b:a", "64k",
                    "-movflags", "+faststart",
                    str(proxy_file.resolve()),
                ]
                subprocess.run(proxy_cmd, capture_output=True, text=True, timeout=30)
                if proxy_file.exists():
                    video.proxy_path = f"/storage/proxies/{proxy_file.name}"
            except Exception as e:
                logger.warning("Proxy generation skipped: %s", e)

            self.queue.update_progress(job.id, 90, "Saving video metadata...")
            video.duration_seconds = duration
            video.width = width
            video.height = height
            video.fps = fps
            video.codec = codec
            video.audio_channels = audio_channels
            video.status = "ready"
            session.commit()

            self.queue.update_progress(job.id, 100, "Probing and asset preparation complete")
            return {
                "video_id": video.id,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "thumbnail": video.thumbnail_path,
                "proxy": video.proxy_path,
            }

    def checkpoint(self, job):
        if not self.queue.heartbeat(job.id):
            raise ValueError("Job no longer owned by this worker")
        if self.queue.is_cancelled(job.id):
            raise ValueError("Job cancelled")

    def next_stage(self, job, task, video_id, clip_id=None):
        self.checkpoint(job)
        from uuid import uuid5, NAMESPACE_URL
        key = str(uuid5(NAMESPACE_URL, f"{job.id}/{task}/{clip_id or video_id}"))
        with SessionLocal() as session:
            if session.get(Job, key):
                return
        self.queue.enqueue(task, {"video_id": video_id, "clip_id": clip_id, "quality": job.get_payload().get("quality","best"), "mode": job.get_payload().get("mode", "ai")}, job_id=key)

    def handle_transcribe(self, job, payload):
        from app.speech import transcribe
        video_id = payload["video_id"]
        with SessionLocal() as session:
            video = session.get(VideoSource, video_id)
            if not video.transcript:
                self.queue.update_progress(job.id, 10, "Recognizing speech on CPU")
                language, segments = transcribe(video.file_path, self.settings.get_ffmpeg_binary(), lambda: self.checkpoint(job))
                self.checkpoint(job)
                session.add(Transcript(video_id=video_id, language=language, raw_text=" ".join(s["text"] for s in segments), segments_json=json.dumps(segments)))
                session.commit()
        self.next_stage(job, "detect_moments", video_id)
        return {"video_id": video_id}

    def handle_detect_moments(self, job, payload):
        from app.speech import highlights, transcript_highlights
        with SessionLocal() as session:
            video = session.get(VideoSource, payload["video_id"])
            if not video.transcript:
                raise ValueError("Transcription required")
            segments = json.loads(video.transcript.segments_json)
            offline = payload.get("mode") == "transcript"
            if offline:
                self.queue.update_progress(job.id, 10, "Selecting speech excerpt (offline, not AI)")
                rows = transcript_highlights(segments, video.duration_seconds)
            else:
                self.queue.update_progress(job.id, 10, "Analyzing transcript with OmniRouter")
                rows = highlights(self.settings, segments, video.duration_seconds, lambda: self.checkpoint(job))
            clips = []
            for row in rows:
                clip = session.query(Clip).filter_by(video_id=video.id,start_time=row["start"],end_time=row["end"]).first()
                if clip is None:
                    clip = Clip(video_id=video.id,start_time=row["start"],end_time=row["end"],title=row["title"],hook_text=row["hook"],viral_score=row["score"],status="draft")
                    session.add(clip)
                clips.append(clip)
            self.checkpoint(job)
            session.commit()
            for clip in clips:
                self.next_stage(job, "render_clip", video.id, clip.id)
            return {"clip_count": len(clips)}

    def handle_render_clip(self, job: Job, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Render 9:16 clip with smart crop and burnt-in captions via real FFmpeg."""
        clip_id = payload.get("clip_id")
        self.queue.update_progress(job.id, 15, "Initializing render pipeline...")

        with SessionLocal() as session:
            clip = session.get(Clip, clip_id)
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")

            video = session.get(VideoSource, clip.video_id) if clip.video_id else None

            clip.status = "rendering"
            session.commit()

            if self.queue.is_cancelled(job.id):
                clip.status = "draft"
                session.commit()
                return {"status": "cancelled"}

            self.queue.update_progress(job.id, 40, "Applying 9:16 crop & subtitle filters...")
            output_dir = Path("storage/clips")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"clip_{clip.id}_{int(time.time())}.mp4"

            ffmpeg_path = self.settings.get_ffmpeg_binary()
            rendered = False

            if video and video.file_path and Path(video.file_path).exists():
                start = max(0.0, float(clip.start_time or 0.0))
                dur = clip.end_time - start
                if not 0 <= clip.start_time < clip.end_time <= video.duration_seconds:
                    raise ValueError("Clip boundaries exceed source duration")
                crop_x = float(clip.crop_x if clip.crop_x is not None else 0.5)

                # 9:16 vertical crop filter expression with horizontal pan positioning
                zoom = max(1, min(4, clip.crop_zoom or 1))
                x = max(0, min(1, crop_x))
                y = max(0, min(1, clip.crop_y if clip.crop_y is not None else 0.5))
                quality = payload.get("quality", "best")
                crf, preset, bitrate = {"best": ("18", "medium", "192k"), "balanced": ("21", "fast", "160k"), "fast": ("24", "veryfast", "128k")}[quality]
                # Exact 9:16 with even dimensions for 4:2:0, bounded by cropped detail.
                cap = 40 if quality == "fast" else 60
                vf = f"crop=w='trunc(min(iw,ih*9/16)/{zoom}/2)*2':h='trunc(min(ih,iw*16/9)/{zoom}/2)*2':x=(iw-ow)*{x}:y=(ih-oh)*{y},scale=w='18*min({cap},floor(min(iw/18,ih/32)))':h='32*min({cap},floor(min(iw/18,ih/32)))':flags=lanczos,setsar=1,format=yuv420p"
                subtitle = output_dir / (output_file.stem + ".srt")
                if video.transcript:
                    from app.speech import subtitles
                    cues = subtitles(json.loads(video.transcript.segments_json), start, clip.end_time)
                    if not cues:
                        raise ValueError("No captions overlap the selected interval")
                    subtitle.write_text(cues, encoding="utf-8")
                    vf += f",subtitles={subtitle.as_posix()}"
                cmd = [
                    ffmpeg_path,
                    "-y",
                    "-ss", str(start),
                    "-i", str(Path(video.file_path).resolve()),
                    "-t", str(dur),
                    "-vf", vf,
                    "-c:v", "libx264",
                    "-preset", os.getenv("CLIPFORGE_EXPORT_PRESET", preset),
                    "-crf", os.getenv("CLIPFORGE_EXPORT_CRF", crf),
                    "-c:a", "aac",
                    "-b:a", os.getenv("CLIPFORGE_EXPORT_AUDIO_BITRATE", bitrate),
                    "-movflags", "+faststart",
                    str(output_file.resolve()),
                ]
                self.queue.update_progress(job.id, 65, "Encoding H.264 vertical video with FFmpeg...")
                try:
                    from app.speech import run_process
                    run_process(cmd, lambda: self.checkpoint(job))
                    probe = subprocess.run([self.settings.get_ffprobe_binary(), "-v","error","-show_streams","-of","json",str(output_file)], capture_output=True, check=True, timeout=15)
                    streams = json.loads(probe.stdout)["streams"]
                    rendered = any(v.get("codec_name") == "h264" and 0 < v["width"] <= 1080 and v["width"] * 16 == v["height"] * 9 for v in streams)
                except Exception as exc:
                    logger.warning("FFmpeg render failed: %s", exc)

            if not rendered:
                # Fallback for synthetic/mock clips without physical media source
                output_file.unlink(missing_ok=True)
                clip.status = "failed"
                clip.output_path = None
                session.commit()
                raise ValueError("FFmpeg could not render the clip")

            clip.output_path = f"/storage/clips/{output_file.name}"
            clip.status = "ready"
            session.commit()

            self.queue.update_progress(job.id, 100, "Render complete")
            return {"clip_id": clip.id, "output_path": clip.output_path}


if __name__ == "__main__":
    worker = MediaWorker()
    worker.start()
