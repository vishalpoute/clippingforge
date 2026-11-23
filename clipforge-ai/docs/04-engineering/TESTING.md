# TESTING.md

## Test Strategy

- **Unit tests** – pure functions, Pydantic models, SQLAlchemy model creation
- **Integration tests** – FastAPI TestClient hitting real endpoints, database operations
- **End-to-end (E2E)** – Start backend + frontend, verify health dashboard (manual)

## Test Location

All tests are in `services/api/app/tests/`:
- `test_health.py` — Health and info endpoint tests (4 tests)
- `test_db.py` — Database engine, table creation, session tests (3 tests)

## Running Tests

```powershell
# Using test script
.\scripts\test.ps1

# Manual (from services/api/ with venv activated)
python -m pytest app/tests -v
```

## Current Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_health.py` | test_root_returns_200 | ✅ |
| | test_health_returns_ok | ✅ |
| | test_health_dependencies_returns_expected_keys | ✅ |
| | test_api_info_returns_200 | ✅ |
| | test_list_videos_returns_list | ✅ |
| | test_list_jobs_returns_list | ✅ |
| `test_db.py` | test_engine_creates_with_sqlite | ✅ |
| | test_tables_created | ✅ |
| | test_get_db_yields_session | ✅ |
| `test_queue.py` | test_queue_enqueue_and_claim | ✅ |
| | test_queue_progress_and_completion | ✅ |
| | test_queue_retry_and_cancellation | ✅ |
| `test_milestone2.py` | test_video_upload_endpoint | ✅ |
| | test_worker_probe_and_thumbnail_generation | ✅ |
| | test_worker_render_clip_real_ffmpeg | ✅ |

**Summary**: 15/15 tests passing in 3.64 seconds.

## CI (future)
- GitHub Actions workflow will run pytest on each push
- Frontend lint/type check: `npm run lint` in `apps/web/`
