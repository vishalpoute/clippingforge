"""Tests for Milestone 2: real video upload, FFprobe extraction, thumbnails, proxies, and rendering."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Clip, Job, Project, User, VideoSource
from app.queue import get_queue
from app.worker import MediaWorker

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_default_user_and_project():
    """Ensure database has a default user, project, and clean queue for each test."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        # Clear queue jobs so each test is strictly isolated
        session.query(Job).delete()
        user = session.query(User).filter_by(email="creator@clipforge.local").first()
        if not user:
            user = User(
                email="creator@clipforge.local",
                password_hash="dev_hash",
                display_name="ClipForge Creator",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        proj = session.query(Project).first()
        if not proj:
            proj = Project(user_id=user.id, name="Default Workspace")
            session.add(proj)
            session.commit()
        else:
            session.commit()
    yield


@pytest.fixture(scope="module")
def sample_video_path(tmp_path_factory):
    """Generate a valid 2-second 1280x720 MP4 test video with real audio and video streams."""
    settings = get_settings()
    ffmpeg_bin = settings.get_ffmpeg_binary()
    temp_dir = tmp_path_factory.mktemp("media")
    output_path = temp_dir / "test_sample.mp4"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    assert res.returncode == 0, f"Failed to generate test video: {res.stderr}"
    assert output_path.exists()
    return str(output_path)


def test_video_upload_endpoint(sample_video_path):
    """Verify POST /api/v1/videos/upload saves file and creates background probe job."""
    with open(sample_video_path, "rb") as f:
        response = client.post(
            "/api/v1/videos/upload",
            files={"file": ("test_sample.mp4", f, "video/mp4")},
        )
    assert response.status_code == 201
    data = response.json()
    assert "video_id" in data
    assert "job_id" in data
    assert data["status"] == "uploaded"

    # Verify video exists in database
    with SessionLocal() as session:
        video = session.get(VideoSource, data["video_id"])
        assert video is not None
        assert video.original_filename == "test_sample.mp4"
        assert Path(video.file_path).exists()


def test_worker_probe_and_thumbnail_generation(sample_video_path):
    """Verify worker extracts real metadata, thumbnail, and proxy for a real video."""
    worker = MediaWorker()

    with SessionLocal() as session:
        user = session.query(User).first()
        project = session.query(Project).first()
        video = VideoSource(
            project_id=project.id,
            filename="sample_probe.mp4",
            original_filename="sample_probe.mp4",
            file_path=sample_video_path,
            status="uploaded",
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        video_id = video.id

    queue = get_queue()
    job = queue.enqueue("video_probe", payload={"video_id": video_id})
    claimed = queue.claim_next()
    assert claimed is not None

    result = worker.handle_video_probe(claimed, claimed.get_payload())
    queue.complete(claimed.id, result=result)

    with SessionLocal() as session:
        video = session.get(VideoSource, video_id)
        assert video.status == "ready"
        assert video.width == 1280
        assert video.height == 720
        assert video.fps == 30.0
        assert video.duration_seconds >= 1.5
        assert video.thumbnail_path is not None
        # Check thumbnail file exists
        thumb_file = Path(video.thumbnail_path.lstrip("/"))
        assert thumb_file.exists()


def test_worker_render_clip_real_ffmpeg(sample_video_path):
    """Verify worker renders real 9:16 vertical MP4 clip from video source."""
    worker = MediaWorker()

    with SessionLocal() as session:
        project = session.query(Project).first()
        video = VideoSource(
            project_id=project.id,
            filename="sample_render.mp4",
            original_filename="sample_render.mp4",
            file_path=sample_video_path,
            duration_seconds=2.0,
            status="ready",
        )
        session.add(video)
        session.commit()
        session.refresh(video)

        clip = Clip(
            video_id=video.id,
            title="Test 9:16 Render Clip",
            start_time=0.0,
            end_time=1.5,
            aspect_ratio="9:16",
            crop_x=0.5,
            status="draft",
        )
        session.add(clip)
        session.commit()
        session.refresh(clip)
        clip_id = clip.id

    queue = get_queue()
    job = queue.enqueue("render_clip", payload={"clip_id": clip_id})
    claimed = queue.claim_next()
    assert claimed is not None

    result = worker.handle_render_clip(claimed, claimed.get_payload())
    queue.complete(claimed.id, result=result)

    with SessionLocal() as session:
        clip = session.get(Clip, clip_id)
        assert clip.status == "ready"
        assert clip.output_path is not None
        output_file = Path(clip.output_path.lstrip("/"))
        assert output_file.exists()
        assert output_file.stat().st_size > 0

def test_url_import_library_and_duplicate(sample_video_path, monkeypatch):
    import shutil
    from app import ingestion

    def fixture_download(url, destination, worker, job_id, quality):
        path = destination.with_suffix(".mp4")
        shutil.copyfile(sample_video_path, path)
        return path, "Controlled recording"

    monkeypatch.setattr(ingestion, "acquire", fixture_download)
    route = "/api/v1/videos/import"
    assert client.post(route, json={"url": "https://example.org/file"}).status_code == 422
    request = {"url": "https://youtu.be/abcdefghijk"}
    response = client.post(route, json=request)
    assert response.status_code == 202
    job = get_queue().claim_next()
    assert job.id == response.json()["job_id"]
    MediaWorker()._process_job(job)
    assert client.get("/api/v1/jobs/" + job.id).json()["status"] == "completed"
    records = [v for v in client.get("/api/v1/videos").json() if v["filename"] == "Controlled recording"]
    assert len(records) == 1 and records[0]["thumbnail_path"] and records[0]["status"] == "ready"
    assert client.post(route, json=request).json() == {"job_id": job.id, "status": "completed"}

def test_failed_job_can_be_retried_from_api():
    queue = get_queue()
    job = queue.enqueue('video_probe', {'video_id': 1}, max_retries=1)
    assert queue.claim_next().id == job.id
    assert client.post(f'/api/v1/jobs/{job.id}/retry').status_code == 409
    queue.fail(job.id, 'Transient failure')
    response = client.post(f'/api/v1/jobs/{job.id}/retry')
    assert response.json() == {'id': job.id, 'status': 'queued'}
    with SessionLocal() as db:
        retried = db.get(Job, job.id)
        assert retried.retry_count == 0 and retried.error_message is None


@pytest.mark.parametrize('mode, flag', [('ai', 'CLIPFORGE_TEST_SPEECH'), ('transcript', 'CLIPFORGE_TEST_OFFLINE_SPEECH')])
def test_speech_to_captioned_mp4(tmp_path, mode, flag):
    if os.getenv(flag) != '1':
        pytest.skip(f'Enable {flag} to test the installed speech runtime')
    import json
    from app.models import Transcript
    cfg = get_settings()
    fixture = Path(__file__).resolve().parents[4] / "tools/whisper-runtime/jfk.wav"
    media = tmp_path / "speech.mp4"
    subprocess.run([cfg.get_ffmpeg_binary(), "-v", "error", "-f","lavfi","-i","color=s=640x360:r=24",
                    "-i",str(fixture),"-shortest","-c:v","libx264","-c:a","aac",str(media)],check=True)
    with media.open("rb") as f:
        video_id = client.post("/api/v1/videos/upload", files={"file":("speech.mp4",f,"video/mp4")}).json()["video_id"]
    worker = MediaWorker()
    def process(task):
        job = worker.queue.claim_next()
        assert job.task_type == task
        worker._process_job(job)
        state = client.get("/api/v1/jobs/" + job.id).json()
        assert state["status"] == "completed", state
    process("video_probe")
    client.post(f"/api/v1/videos/{video_id}/analyze", params={"mode": mode}).raise_for_status()
    for task in ("transcribe","detect_moments","render_clip"):
        process(task)
    with SessionLocal() as db:
        tr = db.query(Transcript).filter_by(video_id=video_id).one()
        assert tr.language == "en" and "country" in tr.raw_text.lower()
    row = client.get(f"/api/v1/videos/{video_id}/clips").json()[0]
    output = Path(row["output_path"].lstrip("/"))
    assert client.get("/api/v1/clips").json()[0]["id"] == row["id"]
    download = client.get(f"/api/v1/clips/{row['id']}/download")
    assert download.content == output.read_bytes() and "attachment" in download.headers["content-disposition"]
    assert "-->" in output.with_suffix(".srt").read_text()
    streams = json.loads(subprocess.check_output([cfg.get_ffprobe_binary(),"-v","error","-show_streams","-of","json",str(output)]))["streams"]
    assert any(s["codec_name"]=="aac" for s in streams)
    assert any(s["codec_name"]=="h264" and (s["width"],s["height"])==(198,352) for s in streams)
    print("Verified speech clip", row["start_time"], row["end_time"], row["viral_score"], output.stat().st_size)

def test_resume_range_download(sample_video_path, tmp_path, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from types import SimpleNamespace
    import time
    from app.ingestion import acquire, FORMATS
    from yt_dlp import YoutubeDL

    content = Path(sample_video_path).read_bytes()
    ranges = []
    class Media(BaseHTTPRequestHandler):
        def do_GET(self):
            value = self.headers.get("Range")
            ranges.append(value)
            offset = int(value.split("=")[1].split("-")[0]) if value else 0
            self.send_response(206 if offset else 200)
            self.send_header("Content-Length", str(len(content) - offset))
            if offset:
                self.send_header("Content-Range", f"bytes {offset}-{len(content)-1}/{len(content)}")
            self.end_headers()
            for i in range(offset, len(content), 8192):
                try:
                    self.wfile.write(content[i:i+8192])
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    break  # Expected when the client cancels mid-transfer.
                time.sleep(0.06)

    server = ThreadingHTTPServer(("127.0.0.1",0), Media)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def metadata(ydl, url, ie_key):
        assert ydl.params["format"] == FORMATS["best"] == "bv*+ba/b"
        return ydl.process_ie_result(dict(id="fixture",title="fixture",duration=2,
            extractor="fixture", extractor_key="Fixture",webpage_url=url,
            formats=[dict(format_id="local",url=f"http://127.0.0.1:{server.server_port}/media.mp4",ext="mp4")]),download=True)
    monkeypatch.setattr(YoutubeDL,"extract_info",metadata)
    partial = Path("data/downloads/resume/best/media-local.mp4.part")
    partial.parent.mkdir(parents=True,exist_ok=True)
    partial.write_bytes(content[:8192])
    owner = MediaWorker()
    job = owner.queue.enqueue("import_recording", {}, job_id="resume")
    assert owner.queue.claim_next().id == job.id
    report = owner.queue.update_progress

    def cancel_on_progress(job_id, percent, message):
        report(job_id, percent, message)
        assert owner.queue.cancel(job_id)

    monkeypatch.setattr(owner.queue, "update_progress", cancel_on_progress)
    try:
        with pytest.raises(ValueError, match="Import cancelled"):
            acquire("https://youtu.be/abcdefghijk", tmp_path / "result", owner, job.id)
        assert not (tmp_path / "result.mp4").exists()
        assert "bytes=8192-" in ranges
        assert owner.queue.is_cancelled(job.id)
        from app.queue import DurableQueue
        replacement = SimpleNamespace(settings=get_settings(), queue=DurableQueue())
        assert replacement.queue.enqueue("import_recording", {}, job_id=job.id).status == "cancelled"
        waiting = replacement.queue.enqueue("import_recording", {}, priority=-1)
        assert replacement.queue.claim_next(max_downloads=1) is None
        owner.queue.release_cancelled_import(job.id)
        owner.queue.enqueue("import_recording", {}, job_id=job.id)
        assert replacement.queue.cancel(waiting.id)
        assert replacement.queue.claim_next().id == job.id
        path, _ = acquire("https://youtu.be/abcdefghijk", tmp_path / "result", replacement, job.id)
        assert path.read_bytes() == content
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
