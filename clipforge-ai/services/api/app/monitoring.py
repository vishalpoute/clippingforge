"""Discover recordings on authorized creator pages and queue them for VOD import."""
import re
import uuid
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL

from .queue import get_queue

YOUTUBE_HANDLE = re.compile(r"/@[\w.-]+")
YOUTUBE_CHANNEL = re.compile(r"/channel/UC[\w-]{22}")
KICK_CHANNEL = re.compile(r"/([\w-]+)")


def channel_url(value):
    """Normalize a supported YouTube channel or Kick creator URL."""
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTPS YouTube channel or Kick creator URL")
    host = parsed.netloc.lower()
    if host in ("youtube.com", "www.youtube.com") and (YOUTUBE_HANDLE.fullmatch(parsed.path) or YOUTUBE_CHANNEL.fullmatch(parsed.path)):
        return "https://www.youtube.com" + parsed.path
    if host in ("kick.com", "www.kick.com") and KICK_CHANNEL.fullmatch(parsed.path):
        return "https://kick.com" + parsed.path.lower()
    raise ValueError("Use a YouTube channel URL or Kick creator URL")


def _queue_recording(recording, provider, title=None):
    from .ingestion import canonical_url

    try:
        actual_provider, recording = canonical_url(recording)
    except ValueError:
        return None
    if actual_provider != provider:
        return None
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, recording))
    payload = {"provider": provider, "url": recording, "quality": "best"}
    if title:
        payload["title_hint"] = title[:256]
    return get_queue().enqueue("import_recording", payload, job_id=key, preserve_existing=True)


def poll_channel(url):
    """Discover currently live or recently finished recordings without downloading."""
    normalized = channel_url(url)
    parsed = urlsplit(normalized)
    provider = "kick" if parsed.netloc.lower().endswith("kick.com") else "youtube"
    target = normalized + ("/streams" if provider == "youtube" else "/videos")
    options = {"quiet": True, "skip_download": True, "playlistend": 5,
               "socket_timeout": 30, "js_runtimes": {"node": {}}}
    if provider == "kick":
        options["extract_flat"] = "in_playlist"
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(target, download=False)
    queued = 0
    for entry in (info or {}).get("entries", []):
        if (not entry or entry.get("live_status") in ("is_upcoming", "post_live")
                or entry.get("availability") in ("private", "premium_only", "subscriber_only", "needs_auth")):
            continue
        identifier = entry.get("id")
        if provider == "youtube":
            if not identifier or not re.fullmatch(r"[\w-]{11}", identifier):
                continue
            recording = "https://www.youtube.com/watch?v=" + identifier
        else:
            if not identifier:
                continue
            recording = f"{normalized}/videos/{identifier}"
        if _queue_recording(recording, provider, entry.get("title")):
            queued += 1
    return {"provider": provider, "url": normalized, "queued": queued}
