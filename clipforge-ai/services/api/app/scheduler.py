"""ClipForge AI — APScheduler background job scheduler (singleton)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_REMOVED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_creator_status: dict[str, dict] = {}


def creator_poll_status(key: str) -> Optional[dict]:
    return _creator_status.get(key)


def record_creator_poll(event) -> None:
    if not event.job_id.startswith("creator-"):
        return
    if event.code == EVENT_JOB_REMOVED:
        _creator_status.pop(event.job_id, None)
    elif event.code == EVENT_JOB_ERROR:
        _creator_status[event.job_id] = {
            "at": datetime.now(timezone.utc), "error": "Poll failed; will retry at the next scheduled check."
        }
    elif isinstance(event.retval, dict):
        _creator_status[event.job_id] = {"at": datetime.now(timezone.utc), **event.retval}

# ── Default job store location ────────────────────────────────────────
_JOBS_DB_PATH = Path("data/jobs.db")


def _ensure_data_dir() -> None:
    _JOBS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Placeholder jobs ─────────────────────────────────────────────────

def cleanup_old_files() -> None:
    """Remove temporary files older than 7 days.  Placeholder implementation."""
    logger.info("cleanup_old_files: placeholder executed — nothing to clean yet.")


# ── Singleton access ──────────────────────────────────────────────────

def get_scheduler() -> BackgroundScheduler:
    """Return the global scheduler instance, creating it on first call."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is None:
        _ensure_data_dir()
        job_store = SQLAlchemyJobStore(url=f"sqlite:///{_JOBS_DB_PATH}")
        _scheduler = BackgroundScheduler(
            jobstores={"default": job_store},
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        _scheduler.add_listener(record_creator_poll, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_REMOVED)
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler and register default jobs (idempotent)."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        # Register the daily cleanup job if not already present
        if not sched.get_job("cleanup_old_files"):
            sched.add_job(
                cleanup_old_files,
                trigger="cron",
                hour=3,
                minute=0,
                id="cleanup_old_files",
                replace_existing=True,
            )
        logger.info("Background scheduler started.")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler shut down.")
    _scheduler = None
