"""ClipForge AI — Durable SQLite-backed background job queue.

Provides atomic job claiming, restart recovery, retry handling, progress tracking,
and cancellation checkpoints for native Windows media processing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, and_, or_, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Job

logger = logging.getLogger("clipforge.queue")


class DurableQueue:
    """Thread-safe and process-safe durable queue on top of SQLite/SQLAlchemy."""

    def __init__(self, worker_id: Optional[str] = None) -> None:
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        queue: str = "default",
        priority: int = 0,
        max_retries: int = 3,
        job_id: Optional[str] = None,
        *,
        preserve_existing: bool = False,
    ) -> Optional[Job]:
        """Enqueue a new job idempotently."""
        jid = job_id or str(uuid.uuid4())
        payload_str = json.dumps(payload)

        with SessionLocal() as session:
            if session.get_bind().dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            existing = session.get(Job, jid)
            if existing:
                if preserve_existing:
                    return None
                if (existing.status in ("queued", "claimed", "running")
                        or (task_type == "import_recording" and (existing.status == "completed"
                            or (existing.status == "cancelled" and existing.claimed_by)))):
                    logger.debug("Reusing job %s (%s)", jid, existing.status)
                    return existing
                # If failed/completed, reset it
                existing.status = "queued"
                existing.progress = 0
                existing.progress_message = "Re-queued"
                existing.payload_json = payload_str
                existing.error_message = None
                existing.result_json = None
                existing.retry_count = 0
                existing.claimed_by = None
                existing.started_at = None
                existing.completed_at = None
                existing.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(existing)
                return existing

            job = Job(
                id=jid,
                queue=queue,
                task_type=task_type,
                payload_json=payload_str,
                status="queued",
                progress=0,
                progress_message="Job queued",
                priority=priority,
                retry_count=0,
                max_retries=max_retries,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            logger.info("Enqueued job %s (task: %s, queue: %s)", jid, task_type, queue)
            return job

    def active_downloads(self) -> int:
        """Count download jobs atomically from durable queue state."""
        with SessionLocal() as session:
            return int(session.execute(select(func.count(Job.id)).where(
                Job.task_type == "import_recording",
                or_(Job.status.in_(("claimed", "running")),
                    and_(Job.status == "cancelled", Job.claimed_by.is_not(None))),
            )).scalar_one())

    def claim_next(self, queues: Optional[List[str]] = None, max_downloads: Optional[int] = None) -> Optional[Job]:
        """Atomically claim the highest-priority queued job."""
        from app.config import get_settings
        
        target_queues = queues or ["default"]
        max_d = max_downloads if max_downloads is not None else get_settings().MAX_CONCURRENT_DOWNLOADS
        now = datetime.now(timezone.utc)

        with SessionLocal() as session:
            # Serialize SQLite claim decisions so download limits hold across processes.
            if session.bind and session.bind.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            active_downloads = select(func.count(Job.id)).where(
                Job.task_type == "import_recording",
                or_(Job.status.in_(("claimed", "running")),
                    and_(Job.status == "cancelled", Job.claimed_by.is_not(None))),
            ).scalar_subquery()
            has_capacity = or_(Job.task_type != "import_recording", active_downloads < max(1, max_d))
            stmt = (
                select(Job)
                .where(
                    and_(
                        Job.queue.in_(target_queues),
                        func.coalesce(func.json_extract(Job.payload_json, "$.retry_after"), 0) <= now.timestamp(),
                        Job.status == "queued",
                        has_capacity,
                    )
                )
                .order_by(Job.priority.desc(), Job.created_at.asc())
                .limit(1)
            )
            candidate = session.execute(stmt).scalars().first()
            if not candidate:
                return None
            update_stmt = (
                update(Job)
                .where(
                    and_(
                        Job.id == candidate.id,
                        Job.status == "queued",
                        has_capacity,
                    )
                )
                .values(
                    status="claimed",
                    claimed_by=self.worker_id,
                    started_at=now,
                    updated_at=now,
                    progress_message="Claimed by worker",
                )
            )
            result = session.execute(update_stmt)
            session.commit()

            if result.rowcount > 0:
                claimed_job = session.get(Job, candidate.id)
                logger.info("Worker %s successfully claimed job %s", self.worker_id, candidate.id)
                return claimed_job
            return None

    def heartbeat(self, job_id: str, *, keep_cancelled_import: bool = False) -> bool:
        """Renew the lease, including while an import is unwinding cancellation."""
        active = Job.status.in_(("claimed", "running"))
        if keep_cancelled_import:
            active = or_(active, and_(Job.status == "cancelled", Job.task_type == "import_recording"))
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            result = session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    active,
                    Job.claimed_by == self.worker_id,
                )
                .values(updated_at=now)
            )
            session.commit()
            return result.rowcount > 0

    def update_progress(self, job_id: str, progress: int, message: str = "") -> None:
        """Update job progress percentage and status message."""
        progress_clamped = max(0, min(100, progress))
        now = datetime.now(timezone.utc)

        with SessionLocal() as session:
            session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status.in_(("claimed", "running")),
                    Job.claimed_by == self.worker_id,
                )
                .values(
                    status="running",
                    progress=progress_clamped,
                    progress_message=message[:255] if message else "",
                    updated_at=now,
                )
            )
            session.commit()

    def is_cancelled(self, job_id: str) -> bool:
        """Checkpoint check: returns True if user cancelled this job."""
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            return bool(job and job.status == "cancelled")

    def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark job as successfully completed."""
        now = datetime.now(timezone.utc)
        result_str = json.dumps(result) if result is not None else None

        with SessionLocal() as session:
            session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status.in_(("claimed", "running")),
                    Job.claimed_by == self.worker_id,
                )
                .values(
                    status="completed",
                    progress=100,
                    progress_message="Completed successfully",
                    result_json=result_str,
                    completed_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            logger.info("Job %s completed successfully", job_id)

    def defer_network(self, job_id, message="OmniRouter unavailable", minimum_delay=15):
        """Release the worker while OmniRouter is unreachable."""
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job or job.status not in ("claimed", "running") or job.claimed_by != self.worker_id:
                return
            payload = job.get_payload()
            attempts = payload.get("network_attempts", 0) + 1
            delay = min(900, minimum_delay * 2 ** min(attempts - 1, 6))
            payload.update(network_attempts=attempts, retry_after=datetime.now(timezone.utc).timestamp() + delay)
            session.execute(update(Job).where(Job.id == job_id, Job.status.in_(("claimed","running")),
                                             Job.claimed_by == self.worker_id).values(
                status="queued", claimed_by=None, payload_json=json.dumps(payload),
                progress_message=f"{message}; retry {attempts} in {delay}s"))
            session.commit()

    def fail(self, job_id: str, error: str) -> None:
        """Record job error and handle automatic retries."""
        now = datetime.now(timezone.utc)

        with SessionLocal() as session:
            if session.get_bind().dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            job = session.get(Job, job_id)
            if not job or job.status not in ("claimed", "running") or job.claimed_by != self.worker_id:
                return

            new_retry_count = job.retry_count + 1
            if new_retry_count < job.max_retries:
                # Re-queue with incremented retry count
                job.status = "queued"
                job.claimed_by = None
                job.retry_count = new_retry_count
                job.progress_message = f"Retrying ({new_retry_count}/{job.max_retries}): {error[:100]}"
                job.error_message = error
                job.updated_at = now
                logger.warning("Job %s failed; scheduled retry %d/%d", job_id, new_retry_count, job.max_retries)
            else:
                job.status = "failed"
                job.retry_count = new_retry_count
                job.progress_message = f"Failed: {error[:100]}"
                job.error_message = error
                job.completed_at = now
                job.updated_at = now
                logger.error("Job %s permanently failed after %d retries: %s", job_id, new_retry_count, error)

            session.commit()

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            if session.get_bind().dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            job = session.get(Job, job_id)
            if not job or job.status in ("completed", "failed", "cancelled"):
                return False

            job.status = "cancelled"
            job.progress_message = "Cancelled by user"
            job.completed_at = now
            job.updated_at = now
            session.commit()
            logger.info("Job %s cancelled", job_id)
            return True

    def release_cancelled_import(self, job_id: str) -> None:
        with SessionLocal() as session:
            session.execute(update(Job).where(
                Job.id == job_id, Job.task_type == "import_recording",
                Job.status == "cancelled", Job.claimed_by == self.worker_id,
            ).values(claimed_by=None))
            session.commit()

    def recover_stale_jobs(self, timeout_seconds: int = 300) -> int:
        """Recover jobs left in claimed/running state by crashed workers."""
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            result = session.execute(update(Job).where(
                Job.status.in_(("claimed", "running")),
                Job.updated_at < now - timedelta(seconds=timeout_seconds),
            ).values(status="queued", claimed_by=None, updated_at=now,
                     progress_message="Recovered after worker restart"))
            recovered_count = result.rowcount
            session.execute(update(Job).where(
                Job.task_type == "import_recording", Job.status == "cancelled",
                Job.claimed_by.is_not(None), Job.updated_at < now - timedelta(seconds=timeout_seconds),
            ).values(claimed_by=None))
            session.commit()

        if recovered_count:
            logger.info("Recovered %d stale jobs from crashed workers", recovered_count)
        return recovered_count

    def get_queue_stats(self) -> Dict[str, Any]:
        """Return counts by status."""
        with SessionLocal() as session:
            from sqlalchemy import func
            rows = session.execute(
                select(Job.status, func.count(Job.id)).group_by(Job.status)
            ).all()
            stats = {status: count for status, count in rows}
            total = sum(stats.values())
            return {
                "total": total,
                "queued": stats.get("queued", 0),
                "running": stats.get("running", 0) + stats.get("claimed", 0),
                "completed": stats.get("completed", 0),
                "failed": stats.get("failed", 0),
                "cancelled": stats.get("cancelled", 0),
            }


# Singleton queue helper
_queue: Optional[DurableQueue] = None


def get_queue() -> DurableQueue:
    global _queue
    if _queue is None:
        _queue = DurableQueue()
    return _queue
