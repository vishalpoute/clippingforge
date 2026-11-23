"""ClipForge AI — SQLAlchemy ORM models."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Application user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Project(Base):
    """A project groups uploaded videos, clips, and publishing settings."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="projects")
    videos = relationship("VideoSource", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class VideoSource(Base):
    """An imported or uploaded long-form video file."""

    __tablename__ = "video_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    original_filename = Column(String(256), nullable=False)
    source_type = Column(String(32), nullable=True)  # upload, youtube, kick, direct, live
    source_url = Column(String(512), nullable=True)
    file_path = Column(String(512), nullable=False)
    proxy_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)
    duration_seconds = Column(Float, default=0.0, nullable=False)
    width = Column(Integer, default=0, nullable=False)
    height = Column(Integer, default=0, nullable=False)
    fps = Column(Float, default=30.0, nullable=False)
    codec = Column(String(64), default="h264", nullable=False)
    audio_channels = Column(Integer, default=2, nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="uploaded", nullable=False)  # uploaded, processing, ready, failed
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="videos")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VideoSource id={self.id} filename={self.filename!r} status={self.status}>"


class Transcript(Base):
    """Transcription data extracted from a video source."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_sources.id"), nullable=False, unique=True, index=True)
    language = Column(String(16), default="en", nullable=False)
    raw_text = Column(Text, nullable=False)
    segments_json = Column(Text, default="[]", nullable=False)  # List of {start, end, text, words}
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    video = relationship("VideoSource", back_populates="transcript")


class Clip(Base):
    """A generated or edited short-form clip extracted from a video source."""

    __tablename__ = "clips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("video_sources.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    hook_text = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    youtube_tags = Column(Text, nullable=True)  # comma separated
    social_hashtags = Column(Text, nullable=True)  # space separated (#shorts #viral)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    viral_score = Column(Float, default=75.0, nullable=False)
    explanation = Column(Text, nullable=True)
    aspect_ratio = Column(String(16), default="9:16", nullable=False)
    crop_x = Column(Float, default=0.5, nullable=False)
    crop_y = Column(Float, default=0.5, nullable=False)
    crop_zoom = Column(Float, default=1.0, nullable=False)
    caption_preset = Column(String(64), default="mrbeast", nullable=False)
    caption_color = Column(String(32), default="#FFFFFF", nullable=False)
    caption_highlight_color = Column(String(32), default="#FFFF00", nullable=False)
    caption_font_size = Column(Integer, default=48, nullable=False)
    output_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)
    status = Column(String(32), default="ready", nullable=False)  # draft, rendering, ready, failed
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    video = relationship("VideoSource", back_populates="clips")
    publishing_jobs = relationship("PublishingJob", back_populates="clip", cascade="all, delete-orphan")


class PublishingJob(Base):
    """A social media scheduling and publishing task."""

    __tablename__ = "publishing_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)  # youtube_shorts, instagram_reels, facebook_reels
    platform_post_id = Column(String(128), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="draft", nullable=False)  # draft, scheduled, publishing, published, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="publishing_jobs")


class Job(Base):
    """Durable SQLite-backed background processing job."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)  # UUID
    queue = Column(String(64), default="default", nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, default="{}", nullable=False)
    status = Column(String(32), default="queued", nullable=False, index=True)  # queued, claimed, running, completed, failed, cancelled
    progress = Column(Integer, default=0, nullable=False)
    progress_message = Column(String(256), default="", nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    claimed_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def get_payload(self) -> Dict[str, Any]:
        try:
            return json.loads(self.payload_json)
        except Exception:
            return {}

    def get_result(self) -> Optional[Dict[str, Any]]:
        if not self.result_json:
            return None
        try:
            return json.loads(self.result_json)
        except Exception:
            return None
