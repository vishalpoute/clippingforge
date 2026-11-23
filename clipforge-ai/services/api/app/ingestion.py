"""Import public, permitted recordings through provider-specific yt-dlp extractors."""
import os
import json
import subprocess
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def canonical_url(value):
    url = urlsplit(value.strip())
    host = url.netloc.lower()
    if url.scheme == "https":
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"):
            video = (parse_qs(url.query).get("v", [""])[0] if url.path == "/watch"
                     else url.path.split("/")[-1] if re.fullmatch(r"/(?:live|shorts)/[^/]+", url.path)
                     else url.path[1:] if host == "youtu.be" else "")
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
                return "youtube", "https://www.youtube.com/watch?v=" + video
        if host in ("kick.com", "www.kick.com"):
            match = re.fullmatch(r"/([\w-]+)/videos/([a-fA-F0-9-]{36})/?", url.path, re.ASCII)
            if match:
                return "kick", f"https://kick.com/{match[1].lower()}/videos/{uuid.UUID(match[2])}"
    raise ValueError("Enter an HTTPS YouTube video or Kick creator VOD URL.")


class AwaitReplay(ValueError):
    """A public live recording can be checked again after it ends."""


FORMATS = {"best": "bv*+ba/b", "balanced": "bv*[height<=1080]+ba/b[height<=1080]", "fast": "bv*[height<=720]+ba/b[height<=720]"}


def permitted(info, *, incomplete=False):
    if info.get('is_live') or info.get('live_status') in ('is_upcoming', 'is_live', 'post_live'):
        raise AwaitReplay('Waiting for a finished replay')
    if info.get('availability') in ('private', 'premium_only', 'subscriber_only', 'needs_auth'):
        return 'This recording requires restricted access'
    return None


def recording_duration(url, settings):
    from math import isfinite

    provider, url = canonical_url(url)
    with YoutubeDL(dict(quiet=True, noplaylist=True, js_runtimes={'node': {}},
                        match_filter=permitted, socket_timeout=max(5, settings.NETWORK_TIMEOUT_SECONDS))) as downloader:
        info = downloader.extract_info(url, download=False, ie_key='Youtube' if provider == 'youtube' else 'KickVOD')
    if not info or permitted(info):
        raise ValueError('Finished recording unavailable')
    duration = info.get('duration')
    if not isinstance(duration, (int, float)) or not isfinite(duration) or duration <= 0:
        raise ValueError('Continuous clipping requires a known recording duration; use full download instead')
    return duration, info.get('title') or 'Recording'


def acquire(url, destination, worker, job_id, quality="best", *, section=None):
    provider, url = canonical_url(url)
    last = 0.0

    def checkpoint():
        if worker.queue.is_cancelled(job_id):
            raise ValueError("Import cancelled")
        if not worker.queue.heartbeat(job_id):
            raise ValueError("Import ownership lost")

    def progress(data):
        nonlocal last
        now = time.monotonic()
        if now - last < 0.5:
            return
        last = now
        checkpoint()
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        done = data.get("downloaded_bytes", 0)
        worker.queue.update_progress(job_id, min(90, int(90 * done / total)) if total else 5,
                                     f"Downloading ({quality} quality): {done:,} bytes" + (f" / {total:,}" if total else " / unknown total")
                                     + (f" | {data['speed']/1024:.1f} KiB/s" if data.get("speed") else " | speed unknown")
                                     + (f" | ETA {data['eta']}s" if data.get("eta") is not None else " | ETA unknown"))

    tmp = Path("data/downloads") / job_id / quality
    if section is not None:
        tmp /= f'section-{section[0]}'
    tmp.mkdir(parents=True, exist_ok=True)

    settings = worker.settings

    def backoff(attempt):
        checkpoint()
        worker.queue.update_progress(job_id, -1, f"Transfer interrupted; retry {attempt}, retaining partial data")
        return min(60, 2 ** min(attempt, 6))

    options = dict(outtmpl=str(Path(tmp) / "media-%(format_id)s.%(ext)s"), noplaylist=True, js_runtimes={"node": {}},
                   format=FORMATS[quality], merge_output_format="mkv", continuedl=True,
                   concurrent_fragment_downloads=1, skip_unavailable_fragments=False,
                   fragment_retries=settings.DOWNLOAD_MAX_RETRIES,
                   retry_sleep_functions={"http": backoff, "fragment": backoff},
                   quiet=True, noprogress=True,
                   socket_timeout=max(5, settings.NETWORK_TIMEOUT_SECONDS),
                   retries=settings.DOWNLOAD_MAX_RETRIES,
                   ffmpeg_location=settings.get_ffmpeg_binary(),
                   progress_hooks=[progress], match_filter=permitted)
    if section is not None:
        from yt_dlp.utils import download_range_func

        options['download_ranges'] = download_range_func(None, [section])
        options['external_downloader'] = 'ffmpeg'
    checkpoint()
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, ie_key="Youtube" if provider == "youtube" else "KickVOD")
    except DownloadError as exc:
        reason = next((label for word, label in (("private","private recording"), ("removed","removed recording"), ("sign in","authentication required"), ("unavailable","recording unavailable"), ("drm","DRM-protected media"), ("unsupported","unsupported recording")) if word in str(exc).lower()), "media unavailable or network error")
        raise ValueError(f"{provider}: {reason}") from exc
    if not info or permitted(info):
        raise ValueError(permitted(info or {}) or "Recording unavailable")
    files = [Path(info["requested_downloads"][0]["filepath"])] if info.get("requested_downloads") else []
    if not files or not files[0].is_file() or files[0].resolve().parent != tmp.resolve():
        raise ValueError("Expected completed download is missing")
    if len(files) != 1 or not files[0].stat().st_size:
        raise ValueError("Download did not produce a complete media file")
    checkpoint()
    probe = subprocess.run([worker.settings.get_ffprobe_binary(), "-v", "error", "-show_streams",
                            "-show_format", "-of", "json", str(files[0])], capture_output=True, timeout=60)
    checkpoint()
    meta = json.loads(probe.stdout) if probe.returncode == 0 else {}
    duration = float(meta.get("format", {}).get("duration", 0))
    if not any(s.get("codec_type") == "video" for s in meta.get("streams", [])) or not duration > 0 or (info.get("duration") and duration + max(2, info["duration"] * 0.01) < info["duration"]):
        files[0].unlink(missing_ok=True)
        raise ValueError("Downloaded recording is invalid or incomplete; retry required")
    target = destination.with_suffix(files[0].suffix)
    files[0].replace(target)
    return target, info.get("title") or target.name
