"""Tests for the durable SQLite-backed job queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models import Job
from app.queue import DurableQueue


@pytest.fixture(autouse=True)
def setup_tables():
    """Ensure database tables exist and queue is clean before each test."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        session.query(Job).delete()
        session.commit()
    yield


def test_queue_enqueue_and_claim():
    queue = DurableQueue(worker_id="test-worker-1")
    job = queue.enqueue(
        task_type="test_task",
        payload={"param1": "value1"},
        priority=10,
    )
    assert job is not None
    assert job.status == "queued"
    assert job.task_type == "test_task"

    # Claim the job
    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "test-worker-1"


def test_queue_progress_and_completion():
    queue = DurableQueue(worker_id="test-worker-2")
    job = queue.enqueue(task_type="progress_task", payload={"data": 123})

    claimed = queue.claim_next()
    assert claimed is not None

    queue.update_progress(claimed.id, 50, "Halfway done")
    assert not queue.is_cancelled(claimed.id)

    queue.complete(claimed.id, result={"output_file": "clip_01.mp4"})

    stats = queue.get_queue_stats()
    assert stats["completed"] >= 1


def test_queue_retry_and_cancellation():
    queue = DurableQueue(worker_id="test-worker-3")
    job = queue.enqueue(task_type="fail_task", payload={}, max_retries=2)
    claimed = queue.claim_next()
    assert claimed is not None

    # First failure -> should be re-queued with retry_count=1
    queue.fail(claimed.id, "Simulated transient error")

    # Cancel the job
    cancelled = queue.cancel(job.id)
    assert cancelled is True
    assert queue.is_cancelled(job.id) is True


def test_worker_heartbeat_and_crash_recovery():
    healthy = DurableQueue(worker_id="healthy")
    job = healthy.enqueue("render_clip", {"clip_id": 1})
    claimed_by_healthy = healthy.claim_next()
    assert claimed_by_healthy is not None
    assert claimed_by_healthy.claimed_by == "healthy"

    assert healthy.heartbeat(job.id)
    assert DurableQueue(worker_id="restart").recover_stale_jobs(timeout_seconds=10) == 0
    with SessionLocal() as db:
        record = db.get(Job, job.id)
        record.updated_at = datetime.now(timezone.utc) - timedelta(seconds=40)
        db.commit()

    restart = DurableQueue(worker_id="restart")
    recovered_count = restart.recover_stale_jobs(timeout_seconds=10)
    assert recovered_count == 1

    replacement = DurableQueue(worker_id="replacement")
    claimed_by_restart = restart.claim_next()
    assert claimed_by_restart is not None
    assert claimed_by_restart.claimed_by == "restart"

    healthy.complete(job.id, {"output": "stale_output.mp4"})
    with SessionLocal() as db:
        assert db.get(Job, job.id).status == "claimed"
        assert db.get(Job, job.id).claimed_by == "restart"


def test_ffmpeg_cancellation_stops_process(tmp_path):
    from app.speech import run_process
    from app.config import get_settings

    ffmpeg = get_settings().get_ffmpeg_binary()
    output = tmp_path / "cancelled.mp4"
    state = {"checks": 0}

    def cancel():
        state["checks"] += 1
        if state["checks"] > 0:
            raise ValueError("Job cancelled")

    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match="cancelled"):
        run_process([
            ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
            "-t", "30", "-c:v", "libx264", str(output),
        ], cancel)
    produced = [path for path in tmp_path.iterdir() if path not in before and path.stat().st_size]
    assert produced == []


def test_cancelled_job_resists_late_worker_updates():
    queue = DurableQueue()
    job = queue.enqueue("render_clip", {})
    assert queue.claim_next().id == job.id
    assert queue.cancel(job.id)
    assert not queue.cancel(job.id)
    queue.update_progress(job.id, 90)
    queue.complete(job.id)
    queue.fail(job.id, "late error")
    assert queue.is_cancelled(job.id)

def test_offline_analysis_releases_worker_and_resumes(monkeypatch):
    import json
    import time
    import httpx
    from app.worker import MediaWorker

    worker = MediaWorker()
    job = worker.queue.enqueue("detect_moments", {"video_id": 42})
    def disconnected(*args):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(worker, "handle_detect_moments", disconnected)
    worker._process_job(worker.queue.claim_next())
    assert worker.queue.claim_next() is None
    with SessionLocal() as db:
        record = db.get(Job, job.id)
        payload = record.get_payload()
        assert payload["retry_after"] > time.time()
        payload["retry_after"] = 0
        record.payload_json = json.dumps(payload)
        db.commit()
    monkeypatch.setattr(worker, "handle_detect_moments", lambda *args: {"clips": 1})
    worker._process_job(worker.queue.claim_next())
    with SessionLocal() as db:
        assert db.get(Job, job.id).status == "completed"

def test_monitor_and_vod_deferral(monkeypatch):
    from app import monitoring
    from app.ingestion import AwaitReplay
    from app.worker import MediaWorker
    monkeypatch.setattr(monitoring.YoutubeDL, "extract_info", lambda *a, **kw: {"entries":[{"id":"abcdefghijk","live_status":"is_live"}]})
    for _ in range(2):
        monitoring.poll_channel("https://www.youtube.com/@creator")
    worker = MediaWorker()
    job = worker.queue.claim_next()
    def live(*args):
        raise AwaitReplay()
    monkeypatch.setattr(worker, "handle_import_recording", live)
    worker._process_job(job)
    assert worker.queue.claim_next() is None
    with SessionLocal() as db:
        assert db.query(Job).count() == 1
        assert "VOD" in db.get(Job,job.id).progress_message
