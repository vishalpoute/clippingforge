"""ClipForge AI — Production FastAPI application entry point.

Provides complete REST endpoints for video ingestion, AI moment analysis,
professional clip editing, metadata customization, social publishing,
and durable job queue monitoring.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .models import Clip, Job, Project, PublishingJob, Transcript, User, VideoSource
from .queue import DurableQueue, get_queue
from .scheduler import get_scheduler, shutdown_scheduler, start_scheduler

logger = logging.getLogger("clipforge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

APP_VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    settings = get_settings()

    # Ensure required storage directories exist
    dirs = [
        "data",
        "storage/uploads",
        "storage/proxies",
        "storage/clips",
        "storage/thumbnails",
        "storage/temp",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Ensure database schema exists
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    # Recover any stale jobs left in claimed/running state from previous run
    queue = get_queue()
    recovered = queue.recover_stale_jobs()
    if recovered:
        logger.info("Recovered %d stale background jobs", recovered)

    # Initialize default user & project if empty
    with SessionLocal() as session:
        default_user = session.query(User).filter_by(email="creator@clipforge.local").first()
        if not default_user:
            default_user = User(
                email="creator@clipforge.local",
                password_hash="local_dev_hash",
                display_name="ClipForge Creator",
            )
            session.add(default_user)
            session.commit()
            session.refresh(default_user)

            default_proj = Project(
                user_id=default_user.id,
                name="Default Workspace",
                description="Default video clipping workspace",
            )
            session.add(default_proj)
            session.commit()
            logger.info("Default user and workspace seeded")

    # Start the periodic background scheduler
    start_scheduler()
    logger.info("ClipForge API v%s started", APP_VERSION)
    yield

    # Shutdown
    shutdown_scheduler()
    logger.info("ClipForge API shut down")


# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ClipForge AI",
    version=APP_VERSION,
    description="Professional AI video clipping and social publishing API (Windows Native)",
    lifespan=lifespan,
)

settings = get_settings()
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if "http://localhost:3000" not in origins:
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local storage directory for thumbnails, proxies, and rendered clips
Path("storage").mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
from typing import Literal


class ImportRequest(BaseModel):
    quality: Literal["best","balanced","fast"] = "best"
    mode: Literal["ai", "transcript"] = "ai"
    url: str = Field(max_length=2048)


@app.post("/api/v1/videos/import", status_code=202)
def import_recording(request: ImportRequest, db: Session = Depends(get_db)):
    from .ingestion import canonical_url
    from sqlalchemy.exc import IntegrityError
    try:
        provider, url = canonical_url(request.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    existing = db.get(Job, job_id)
    if existing and existing.status == "completed":
        return {"job_id": job_id, "status": existing.status}
    try:
        job = get_queue().enqueue("import_recording", {"url": url, "provider": provider, "quality": request.quality, "mode": request.mode}, job_id=job_id)
    except IntegrityError:
        db.rollback()
        job = db.get(Job, job_id)
        if job is None:
            raise
    return {"job_id": job.id, "status": job.status}


class ClipUpdateSchema(BaseModel):
    title: Optional[str] = None
    hook_text: Optional[str] = None
    description: Optional[str] = None
    youtube_tags: Optional[str] = None
    social_hashtags: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    aspect_ratio: Optional[str] = None
    crop_x: Optional[float] = None
    crop_y: Optional[float] = None
    crop_zoom: Optional[float] = None
    caption_preset: Optional[str] = None
    caption_color: Optional[str] = None
    caption_highlight_color: Optional[str] = None
    caption_font_size: Optional[int] = None


class AISuggestionsRequest(BaseModel):
    action: str = Field(..., description="Action: generate_titles, improve_title, generate_hashtags, rewrite_platform")
    target_platform: Optional[str] = "youtube_shorts"
    current_title: Optional[str] = ""
    current_description: Optional[str] = ""


class PublishRequestSchema(BaseModel):
    platform: str = Field(..., description="youtube_shorts, instagram_reels, facebook_reels")
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Core / Health Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root() -> Dict[str, str]:
    return {
        "app": "ClipForge AI",
        "version": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/api/v1/info", tags=["System"])
async def api_info() -> Dict[str, Any]:
    s = get_settings()
    return {
        "version": APP_VERSION,
        "database_backend": "sqlite" if s.DATABASE_URL.startswith("sqlite") else "postgresql",
        "storage_root": s.STORAGE_ROOT,
        "omnirouter_configured": bool(s.OMNIROUTER_BASE_URL),
        "windows_native": True,
    }


@app.get("/api/v1/health", tags=["System"])
async def health_check() -> JSONResponse:
    return JSONResponse(content={
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
    })


@app.get("/api/v1/health/dependencies", tags=["System"])
async def health_dependencies() -> Dict[str, Any]:
    results: Dict[str, Any] = {}

    # Database
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        results["database"] = {"status": "ok", "backend": "sqlite"}
    except Exception as exc:
        results["database"] = {"status": "error", "detail": str(exc)}

    # FFmpeg
    ffmpeg_path = get_settings().get_ffmpeg_binary()
    try:
        proc = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3)
        results["ffmpeg"] = {
            "status": "ok" if proc.returncode == 0 else "error",
            "version": proc.stdout.split("\n")[0].strip() if proc.stdout else "unknown",
            "path": ffmpeg_path,
        }
    except FileNotFoundError:
        results["ffmpeg"] = {"status": "not_found", "detail": f"{ffmpeg_path} not in PATH"}
    except Exception as exc:
        results["ffmpeg"] = {"status": "error", "detail": str(exc)}

    # OmniRouter (quick socket/HTTP ping)
    omnirouter_url = get_settings().OMNIROUTER_BASE_URL.replace('localhost','127.0.0.1').rstrip('/')
    results["omnirouter"] = {"status": "unreachable", "url": omnirouter_url}
    if omnirouter_url:
        import urllib.request, urllib.error
        try:
            api_key = get_settings().OMNIROUTER_API_KEY
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            req = urllib.request.Request(f"{omnirouter_url}/models", headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status < 400:
                    results["omnirouter"] = {"status": "ok", "url": omnirouter_url}
        except urllib.error.HTTPError as http_err:
            results["omnirouter"] = {"status": "error", "detail": f"HTTP {http_err.code}"}
        except Exception as exc:
            results["omnirouter"] = {"status": "error", "detail": str(exc)}

    # Durable Queue Worker
    try:
        q = get_queue()
        stats = q.get_queue_stats()
        results["worker"] = {
            "status": "ok",
            "active_worker_id": q.worker_id,
            "queue_stats": stats,
        }
    except Exception as exc:
        results["worker"] = {"status": "error", "detail": str(exc)}

    return results


# ---------------------------------------------------------------------------
# Videos / Media Library Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/videos/upload", status_code=status.HTTP_201_CREATED, tags=["Videos"])
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload a raw long-form video, save it to disk, and enqueue probing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Generate unique stored filename
    ext = Path(file.filename).suffix.lower() or ".mp4"
    unique_name = f"{uuid.uuid4().hex[:12]}_{Path(file.filename).stem[:32]}{ext}"
    upload_dir = Path("storage/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / unique_name

    # Write file to disk
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = destination.stat().st_size

    # Fetch default project
    project = db.query(Project).first()
    if not project:
        user = db.query(User).first()
        if not user:
            user = User(
                email="creator@clipforge.local",
                password_hash="local_dev_hash",
                display_name="ClipForge Creator",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        project = Project(user_id=user.id, name="Default Workspace")
        db.add(project)
        db.commit()
        db.refresh(project)

    video = VideoSource(
        project_id=project.id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=str(destination),
        file_size_bytes=file_size,
        status="uploaded",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Enqueue background probing job in durable queue
    queue = get_queue()
    job = queue.enqueue(
        task_type="video_probe",
        payload={"video_id": video.id},
        priority=10,
    )

    return {
        "video_id": video.id,
        "filename": video.original_filename,
        "status": video.status,
        "job_id": job.id,
    }


@app.get("/api/v1/videos", tags=["Videos"])
def list_videos(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all imported videos with clip counts."""
    videos = db.query(VideoSource).order_by(desc(VideoSource.created_at)).all()
    results = []
    for v in videos:
        clip_count = len(v.clips)
        results.append({
            "id": v.id,
            "filename": v.original_filename,
            "duration": v.duration_seconds,
            "resolution": f"{v.width}x{v.height}" if v.width else "N/A",
            "fps": v.fps,
            "status": v.status,
            "thumbnail_path": v.thumbnail_path,
            "proxy_path": v.proxy_path,
            "clip_count": clip_count,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        })
    return results


@app.get("/api/v1/videos/{video_id}", tags=["Videos"])
def get_video(video_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get single video metadata and associated clips."""
    v = db.get(VideoSource, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "id": v.id,
        "filename": v.original_filename,
        "file_path": v.file_path,
        "duration": v.duration_seconds,
        "width": v.width,
        "height": v.height,
        "fps": v.fps,
        "codec": v.codec,
        "file_size": v.file_size_bytes,
        "thumbnail_path": v.thumbnail_path,
        "proxy_path": v.proxy_path,
        "status": v.status,
        "clip_count": len(v.clips),
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ---------------------------------------------------------------------------
# Clips / AI Moments Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/videos/{video_id}/analyze", tags=["Clips"])
def analyze_video_moments(video_id: int, mode: Literal["ai", "transcript"] = "ai", db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Trigger AI viral moment discovery for a video."""
    video = db.get(VideoSource, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    queue = get_queue()
    job = queue.enqueue(
        task_type="transcribe",
        payload={"video_id": video.id, "mode": mode},
        priority=5,
    )
    return {
        "message": "Transcription and clip generation queued",
        "video_id": video.id,
        "job_id": job.id,
    }


@app.get("/api/v1/videos/{video_id}/clips", tags=["Clips"])
def list_video_clips(video_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all short-form clips extracted from a video."""
    video = db.get(VideoSource, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    clips = db.query(Clip).filter_by(video_id=video.id).order_by(desc(Clip.viral_score)).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "hook_text": c.hook_text,
            "description": c.description,
            "youtube_tags": c.youtube_tags,
            "social_hashtags": c.social_hashtags,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "duration": round(c.end_time - c.start_time, 1),
            "viral_score": c.viral_score,
            "explanation": c.explanation,
            "aspect_ratio": c.aspect_ratio,
            "output_path": c.output_path,
            "caption_preset": c.caption_preset,
            "status": c.status,
        }
        for c in clips
    ]


@app.get("/api/v1/clips")
def rendered_clips(db: Session = Depends(get_db)):
    rows = db.query(Clip).filter(Clip.status == "ready", Clip.output_path.isnot(None)).order_by(desc(Clip.id))
    return [{"id": c.id, "title": c.title, "output_path": c.output_path} for c in rows]


@app.get("/api/v1/clips/{clip_id}/download")
def download_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if not clip or not clip.output_path:
        raise HTTPException(404, "Rendered clip unavailable")
    root = Path("storage/clips").resolve()
    path = (root / Path(clip.output_path).name).resolve()
    if path.parent != root or not path.is_file() or not path.stat().st_size:
        raise HTTPException(404, "Rendered file unavailable")
    return FileResponse(path, media_type="video/mp4", filename=f"clip-{clip_id}.mp4")


@app.get("/api/v1/clips/{clip_id}", tags=["Clips"])
def get_clip_details(clip_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get complete editable attributes for a clip."""
    c = db.get(Clip, clip_id)
    if not c:
        raise HTTPException(status_code=404, detail="Clip not found")

    return {
        "id": c.id,
        "video_id": c.video_id,
        "title": c.title,
        "hook_text": c.hook_text,
        "description": c.description,
        "youtube_tags": c.youtube_tags,
        "social_hashtags": c.social_hashtags,
        "start_time": c.start_time,
        "end_time": c.end_time,
        "duration": round(c.end_time - c.start_time, 1),
        "viral_score": c.viral_score,
        "explanation": c.explanation,
        "aspect_ratio": c.aspect_ratio,
        "crop_x": c.crop_x,
        "crop_y": c.crop_y,
        "crop_zoom": c.crop_zoom,
        "caption_preset": c.caption_preset,
        "caption_color": c.caption_color,
        "caption_highlight_color": c.caption_highlight_color,
        "caption_font_size": c.caption_font_size,
        "status": c.status,
        "output_path": c.output_path,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@app.patch("/api/v1/clips/{clip_id}", tags=["Clips"])
def update_clip(
    clip_id: int,
    payload: ClipUpdateSchema,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update timeline bounds, reframing, subtitles, or metadata without overwriting."""
    c = db.get(Clip, clip_id)
    if not c:
        raise HTTPException(status_code=404, detail="Clip not found")

    changes = payload.model_dump(exclude_unset=True)
    if "start_time" in changes or "end_time" in changes:
        start = changes.get("start_time", c.start_time)
        end = changes.get("end_time", c.end_time)
        if start is None or end is None or not c.video or not 0 <= start < end <= c.video.duration_seconds:
            raise HTTPException(422, "Trim must be inside the source with the end after the start.")
    for field, val in changes.items():
        setattr(c, field, val)

    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "title": c.title,
        "status": "updated",
        "start_time": c.start_time,
        "end_time": c.end_time,
    }


@app.post("/api/v1/clips/{clip_id}/ai-suggestions", tags=["AI Assistant"])
def generate_ai_suggestions(
    clip_id: int,
    req: AISuggestionsRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate high-converting title, hook, or hashtag recommendations."""
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    action = req.action
    base_title = req.current_title or clip.title

    if action == "generate_titles":
        titles = [
            f"The Exact Way To {base_title}",
            f"Why Everyone Is Wrong About {base_title}",
            f"Stop Doing This If You Want Better Results",
            f"The 1 Secret To {base_title} (Proven)",
            f"Watch This Before Trying To {base_title}",
        ]
        return {"action": action, "suggestions": titles}

    elif action == "generate_hashtags":
        tags = ["#shorts", "#viral", "#creatorhacks", "#productivity", "#mindset", "#growthtips"]
        if req.target_platform == "youtube_shorts":
            yt_keywords = ["shorts", "trending", "how to", "tips and tricks", "viral video"]
            return {"action": action, "hashtags": " ".join(tags), "youtube_tags": ", ".join(yt_keywords)}
        return {"action": action, "hashtags": " ".join(tags)}

    elif action == "improve_hook":
        hooks = [
            "Wait until you see how this changes everything...",
            "If you make this one mistake, you're losing hours...",
            "Here is the single biggest hack I learned this year...",
        ]
        return {"action": action, "suggestions": hooks}

    return {
        "action": action,
        "suggestions": [f"Optimized variation for {req.target_platform}: {base_title}"],
    }


@app.post("/api/v1/clips/{clip_id}/render", tags=["Clips"])
def render_clip(clip_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Enqueue a real background render of the clip with cropping and subtitles."""
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip.status = "rendering"
    db.commit()

    queue = get_queue()
    job = queue.enqueue(
        task_type="render_clip",
        payload={"clip_id": clip.id},
        priority=8,
    )
    return {
        "clip_id": clip.id,
        "status": "rendering_enqueued",
        "job_id": job.id,
    }


# ---------------------------------------------------------------------------
# Social Media Publishing Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/clips/{clip_id}/publish", tags=["Publishing"])
def schedule_or_publish_clip(
    clip_id: int,
    req: PublishRequestSchema,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Queue or immediately publish a clip to YouTube Shorts / Reels."""
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    status_str = "scheduled" if req.scheduled_at else "publishing"
    pub_job = PublishingJob(
        clip_id=clip.id,
        platform=req.platform,
        scheduled_at=req.scheduled_at,
        status=status_str,
    )
    db.add(pub_job)
    db.commit()
    db.refresh(pub_job)

    return {
        "publishing_job_id": pub_job.id,
        "clip_id": clip.id,
        "platform": pub_job.platform,
        "status": pub_job.status,
    }


# ---------------------------------------------------------------------------
# Durable Job Queue Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/v1/jobs", tags=["Jobs"])
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Inspect background processing jobs and live progress."""
    jobs = db.query(Job).order_by(desc(Job.created_at)).limit(limit).all()
    return [
        {
            "id": j.id,
            "queue": j.queue,
            "task_type": j.task_type,
            "status": j.status,
            "progress": j.progress,
            "progress_message": j.progress_message,
            "priority": j.priority,
            "retry_count": j.retry_count,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        }
        for j in jobs
    ]


@app.get("/api/v1/jobs/{job_id}", tags=["Jobs"])
def get_job(job_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get single job status and progress details."""
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": j.id,
        "task_type": j.task_type,
        "status": j.status,
        "progress": j.progress,
        "progress_message": j.progress_message,
        "error_message": j.error_message,
        "result": j.get_result(),
    }


@app.post("/api/v1/jobs/{job_id}/retry", tags=["Jobs"])
def retry_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    retried = get_queue().enqueue(job.task_type, job.get_payload(), queue=job.queue,
                                  priority=job.priority, max_retries=job.max_retries, job_id=job.id)
    return {"id": retried.id, "status": retried.status}


@app.post("/api/v1/jobs/{job_id}/cancel", tags=["Jobs"])
def cancel_job(job_id: str) -> Dict[str, Any]:
    """Request graceful cancellation of a job at the next checkpoint."""
    queue = get_queue()
    success = queue.cancel(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job could not be cancelled or does not exist")
    return {"id": job_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

class MonitorRequest(BaseModel):
    url: str = Field(max_length=512)


@app.post("/api/v1/monitors")
def monitor_creator(request: MonitorRequest):
    from .monitoring import channel_url, poll_channel
    try:
        url = channel_url(request.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    key = "creator-" + uuid.uuid5(uuid.NAMESPACE_URL, url).hex
    
    sched = get_scheduler()
    if not sched.get_job(key):
        sched.add_job(poll_channel, "interval", minutes=5, id=key, args=[url],
                      replace_existing=True, next_run_time=datetime.now(timezone.utc))
    return {"id": key, "url": url}


@app.get("/api/v1/monitors")
def list_monitors():
    from .scheduler import creator_poll_status

    return [{"id": j.id, "url": j.args[0], "paused": j.next_run_time is None,
             "next_run_at": j.next_run_time, "last_poll": creator_poll_status(j.id)}
            for j in get_scheduler().get_jobs() if j.id.startswith("creator-")]


class MonitorUpdate(BaseModel):
    paused: bool


@app.patch("/api/v1/monitors/{key}")
def update_monitor(key: str, request: MonitorUpdate):
    from apscheduler.jobstores.base import JobLookupError

    sched = get_scheduler()
    if not key.startswith("creator-"):
        raise HTTPException(404, "Unknown creator monitor")
    try:
        if request.paused:
            sched.pause_job(key)
        else:
            sched.resume_job(key)
    except JobLookupError as exc:
        raise HTTPException(404, "Unknown creator monitor") from exc
    return {"id": key, "paused": request.paused}


@app.delete("/api/v1/monitors/{key}")
def stop_monitor(key: str):
    if not key.startswith("creator-") or not get_scheduler().get_job(key):
        raise HTTPException(404, "Unknown creator monitor")
    get_scheduler().remove_job(key)
    return {"removed": key}
