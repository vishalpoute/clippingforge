"""Exercise the durable queue from independent, provider-free worker processes."""

import multiprocessing
import os
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest


IPC_TIMEOUT = 20
EXIT_TIMEOUT = 5


def _isolated_url(sandbox):
    root = Path(sandbox).resolve()
    database = root / "test.db"
    url = "sqlite:///" + database.as_posix()
    if (
        Path.cwd().resolve() != root
        or root.parent != Path(tempfile.gettempdir()).resolve()
        or not root.name.startswith("clipforge-tests-")
        or database.resolve() != database
        or os.environ.get("DATABASE_URL") != url
    ):
        raise RuntimeError("Worker tests require the API conftest temporary SQLite database")
    return url


def _checked_db(sandbox):
    url = _isolated_url(sandbox)  # Check before importing app.db, which initializes the engine.
    from sqlalchemy.engine import make_url

    from app import db

    if db.engine.url != make_url(url) or db.SessionLocal.kw.get("bind") is not db.engine:
        raise RuntimeError("App engine and sessions must use the API test database")
    return db


@pytest.fixture
def isolated_db(pytestconfig):
    conftest_path = Path(__file__).resolve().parents[2] / "conftest.py"
    plugin = pytestconfig.pluginmanager.get_plugin(str(conftest_path))
    if plugin is None or not getattr(plugin, "_sandbox", None):
        pytest.fail("API conftest database isolation is absent; refusing to run worker tests")
    sandbox = plugin._sandbox.name
    db = _checked_db(sandbox)
    from app.models import Job

    Job.__table__.create(db.engine, checkfirst=True)
    # The queue's download limit and stale recovery both span all queue names.
    with db.SessionLocal.begin() as session:
        session.query(Job).delete()
    try:
        yield sandbox, db.SessionLocal
    finally:
        with db.SessionLocal.begin() as session:
            session.query(Job).delete()


def _worker(conn, sandbox, action, value):
    db = _checked_db(sandbox)
    from app.ingestion import canonical_url
    from app.worker import MediaWorker

    worker = MediaWorker()
    queue = worker.queue
    try:
        conn.send((os.getpid(), queue.worker_id))
        if not conn.poll(IPC_TIMEOUT) or conn.recv() != "go":
            raise RuntimeError("Worker did not receive start signal")

        if action == "enqueue":
            raw_url, quality = value
            provider, url = canonical_url(raw_url)
            job = queue.enqueue(
                "import_recording", {"provider": provider, "url": url, "quality": quality},
                job_id=str(uuid5(NAMESPACE_URL, url)),
            )
            conn.send((job.id, job.status, job.get_payload()))
        elif action in ("claim", "recover", "crash"):
            recovered = queue.recover_stale_jobs() if action == "recover" else 0
            job = queue.claim_next(max_downloads=1)
            if action == "crash":
                assert job is not None, "Crash worker did not claim a download"

                def hold_download(claim, _payload):
                    queue.update_progress(claim.id, 42, "Test download in progress")
                    conn.send(claim.id)
                    # Remain inside the handler until killed, without calling the provider.
                    if conn.poll(IPC_TIMEOUT):
                        conn.recv()
                    raise RuntimeError("Test did not kill the worker while the handler was active")

                worker.handle_import_recording = hold_download
                worker._process_job(job)
                raise RuntimeError("Crash worker returned without being killed")
            conn.send((recovered, job.id if job else None))
        else:
            raise ValueError(f"Unknown worker action: {action}")
    finally:
        db.engine.dispose()
        conn.close()


@contextmanager
def _spawn(sandbox, action, value=None):
    ctx = multiprocessing.get_context("spawn")
    conn, child_conn = ctx.Pipe()
    process = ctx.Process(target=_worker, args=(child_conn, sandbox, action, value))
    try:
        process.start()
        child_conn.close()
        yield process, conn
    finally:
        child_conn.close()
        conn.close()
        if process.pid is not None:
            if process.is_alive():
                process.kill()
            process.join(EXIT_TIMEOUT)
            assert not process.is_alive(), f"Worker {process.pid} did not stop"
        process.close()


def _receive(process, conn):
    assert conn.poll(IPC_TIMEOUT), f"Timed out waiting for worker {process.pid}"
    try:
        return conn.recv()
    except EOFError:
        process.join(EXIT_TIMEOUT)
        pytest.fail(f"Worker {process.pid} closed its pipe early (exit {process.exitcode})")


def _ready(process, conn):
    pid, worker_id = _receive(process, conn)
    assert pid == process.pid and pid != os.getpid()
    return worker_id


def _race(sandbox, action, *values):
    with ExitStack() as stack:
        children = [stack.enter_context(_spawn(sandbox, action, value)) for value in values]
        workers = [_ready(*child) for child in children]
        assert len({process.pid for process, _ in children}) == len(children)
        assert len(set(workers)) == len(children)
        for _, conn in children:
            conn.send("go")
        results = {}
        for worker_id, (process, conn) in zip(workers, children):
            results[worker_id] = _receive(process, conn)
            process.join(EXIT_TIMEOUT)
            assert process.exitcode == 0, f"Worker {process.pid} exit: {process.exitcode}"
        return results


def test_workers_compete_for_one_download_slot(isolated_db):
    sandbox, sessions = isolated_db
    from app.models import Job
    from app.queue import DurableQueue

    queue = DurableQueue()
    first = queue.enqueue("import_recording", {}, priority=10).id
    second = queue.enqueue("import_recording", {}).id

    results = _race(sandbox, "claim", None, None, None)
    winners = [owner for owner, (_, job_id) in results.items() if job_id is not None]
    assert len(winners) == 1
    assert results[winners[0]] == (0, first)
    with sessions() as session:
        claimed = session.get(Job, first)
        waiting = session.get(Job, second)
        assert (claimed.status, claimed.claimed_by) == ("claimed", winners[0])
        assert (waiting.status, waiting.claimed_by) == ("queued", None)
    assert queue.active_downloads() == 1


def test_workers_enqueue_same_canonical_recording(isolated_db):
    sandbox, sessions = isolated_db
    from app.models import Job
    from app.queue import DurableQueue

    canonical = "https://www.youtube.com/watch?v=AbCdEf12345"
    expected_id = str(uuid5(NAMESPACE_URL, canonical))
    submissions = (
        ("https://youtu.be/AbCdEf12345?t=12", "fast"),
        ("https://m.youtube.com/watch?v=AbCdEf12345", "balanced"),
        (canonical, "best"),
    )
    results = list(_race(sandbox, "enqueue", *submissions).values())
    payload = results[0][2]
    assert results == [(expected_id, "queued", payload)] * len(submissions)
    assert payload == {"provider": "youtube", "url": canonical, "quality": payload["quality"]}
    assert payload["quality"] in {quality for _, quality in submissions}

    queue = DurableQueue()
    assert queue.claim_next(max_downloads=1).id == expected_id
    queue.complete(expected_id, {"test": "already completed"})

    repeated = _race(sandbox, "enqueue", *submissions)
    assert list(repeated.values()) == [(expected_id, "completed", payload)] * len(submissions)
    with sessions() as session:
        job = session.query(Job).one()
        assert (job.id, job.status, job.get_payload(), job.get_result()) == (
            expected_id, "completed", payload, {"test": "already completed"},
        )


def test_killed_worker_download_is_reclaimed_once_when_stale(isolated_db):
    sandbox, sessions = isolated_db
    from app.models import Job
    from app.queue import DurableQueue

    queue = DurableQueue()
    download = queue.enqueue("import_recording", {}, priority=10).id
    waiting = queue.enqueue("import_recording", {}).id

    with _spawn(sandbox, "crash") as (process, conn):
        dead_owner = _ready(process, conn)
        conn.send("go")
        assert _receive(process, conn) == download
        with sessions() as session:
            job = session.get(Job, download)
            assert (job.status, job.claimed_by, job.progress) == ("running", dead_owner, 42)
        assert process.is_alive()
        process.kill()
        process.join(EXIT_TIMEOUT)
        assert process.exitcode not in (None, 0), "Worker did not exit abruptly"

    # Process death alone must not free a fresh lease or its download slot.
    fresh = _race(sandbox, "recover", None)
    assert list(fresh.values()) == [(0, None)]
    with sessions.begin() as session:
        job = session.get(Job, download)
        assert (job.status, job.claimed_by) == ("running", dead_owner)
        job.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)

    results = _race(sandbox, "recover", None, None)
    assert sorted(count for count, _ in results.values()) == [0, 1]
    winners = [owner for owner, (_, job_id) in results.items() if job_id is not None]
    assert len(winners) == 1 and winners[0] != dead_owner
    assert results[winners[0]][1] == download
    with sessions() as session:
        job = session.get(Job, download)
        assert (job.status, job.claimed_by, job.retry_count) == ("claimed", winners[0], 0)
        queued = session.get(Job, waiting)
        assert (queued.status, queued.claimed_by) == ("queued", None)
