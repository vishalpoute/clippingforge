
import pytest
from app.main import monitor_creator, MonitorRequest
from app.scheduler import get_scheduler, shutdown_scheduler
from app.db import Base, SessionLocal, engine
from app.models import Job

@pytest.fixture(autouse=True)
def setup_scheduler():
    Base.metadata.create_all(bind=engine)
    get_scheduler().remove_all_jobs()
    with SessionLocal() as db:
        db.query(Job).delete()
        db.commit()
    yield
    shutdown_scheduler()

def test_monitor_submission_deduplication():
    url = "https://www.youtube.com/@testcreator"
    monitor_creator(MonitorRequest(url=url))
    sched = get_scheduler()
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    
    # Try adding again - should replace (idempotent)
    monitor_creator(MonitorRequest(url=url))
    assert len(sched.get_jobs()) == 1

def test_monitor_discovery_queues_jobs(monkeypatch):
    from app import monitoring
    url = "https://www.youtube.com/@testcreator"

    class MockYDL:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, *args, **kwargs):
            return {
                "entries": [{"id": "abcdefghijk", "live_status": "is_live", "title": "Live stream"}]
            }

    monkeypatch.setattr(monitoring, "YoutubeDL", MockYDL)

    result = monitoring.poll_channel(url)
    assert result["queued"] == 1
    # Second poll should deduplicate based on canonical URL job ID
    assert monitoring.poll_channel(url)["queued"] == 0

    with SessionLocal() as db:
        assert db.query(Job).filter_by(task_type="import_recording").count() == 1
        job = db.query(Job).filter_by(task_type="import_recording").first()
        assert "youtube" in job.payload_json
        assert job.get_payload()["url"] == "https://www.youtube.com/watch?v=abcdefghijk"


def test_kick_finished_vod_discovery(monkeypatch):
    from app import monitoring

    vod_id = "01234567-89ab-cdef-0123-456789abcdef"

    def extract(self, url, *, download):
        assert url == "https://kick.com/testcreator/videos"
        assert download is False
        return {"entries": [
            {"id": vod_id},
            {"id": "invalid"},
        ]}

    monkeypatch.setattr(monitoring.YoutubeDL, "extract_info", extract)
    assert monitoring.poll_channel("https://www.kick.com/TestCreator/")["queued"] == 1
    with SessionLocal() as db:
        assert db.query(Job).one().get_payload()["url"] == f"https://kick.com/testcreator/videos/{vod_id}"


def test_monitor_pause_persists_across_scheduler_restart():
    from app.main import list_monitors, MonitorUpdate, update_monitor

    get_scheduler().start(paused=True)
    request = MonitorRequest(url="https://www.youtube.com/@testcreator")
    key = monitor_creator(request)["id"]
    update_monitor(key, MonitorUpdate(paused=True))
    shutdown_scheduler()
    get_scheduler().start(paused=True)
    assert list_monitors()[0]["paused"] is True
    assert monitor_creator(request)["id"] == key
    assert list_monitors()[0]["paused"] is True
    update_monitor(key, MonitorUpdate(paused=False))
    assert list_monitors()[0]["paused"] is False
