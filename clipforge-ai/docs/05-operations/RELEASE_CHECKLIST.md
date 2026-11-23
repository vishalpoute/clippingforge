# ClipForge AI — Release & Verification Checklist

## Pre-Release Verification Steps

### 1. Environment & Infrastructure
- [ ] Windows 11 64-bit operating system verified.
- [ ] Python 3.10+ installed and virtual environment (`services/api/.venv`) active.
- [ ] Node.js 18+ and npm installed and verified.
- [ ] FFmpeg & FFprobe available in system PATH (or specified in `.env`).
- [ ] No Docker dependencies or background container requirements exist.

### 2. Database & Migrations
- [ ] SQLite database file created at `services/api/data/clipforge.db`.
- [ ] WAL mode enabled (`PRAGMA journal_mode=WAL`).
- [ ] Foreign keys enabled (`PRAGMA foreign_keys=ON`).
- [ ] Alembic migrations run cleanly to `head` (`python -m alembic upgrade head`).
- [ ] Tables verified: `users`, `projects`, `video_sources`, `clips`, `jobs`.

### 3. Backend & Background Worker
- [ ] FastAPI starts cleanly on `http://127.0.0.1:8000`.
- [ ] `GET /api/v1/health` returns HTTP 200 with status `ok`.
- [ ] `GET /api/v1/health/dependencies` checks real dependency status.
- [ ] SQLite durable job queue operates, claims jobs atomically, and handles process restarts.
- [ ] Automated pytest suite passes with 100% success (`pytest app/tests -v`).

### 4. Frontend & User Interface
- [ ] Next.js starts on `http://localhost:3000`.
- [ ] Production build succeeds (`npm run build`).
- [ ] TypeScript type checks pass (`npx tsc --noEmit`).
- [ ] Dashboard displays live system health and dependency statuses.
- [ ] Video library, editor, timeline, and metadata panels render without console errors.
- [ ] Dark theme design system consistent across all views.

### 5. Scripts & Automation
- [ ] `scripts/setup.ps1` runs idempotently without errors.
- [ ] `scripts/start.ps1` starts frontend, backend, and worker.
- [ ] `scripts/test.ps1` executes all tests and live endpoint verifications.
- [ ] `scripts/stop.ps1` gracefully stops only project-owned processes.

### 6. Documentation
- [ ] All 18 canonical documents organized under `docs/`.
- [ ] Root `README.md` and `AGENTS.md` accurate and up to date.
- [ ] Zero references to Docker or container workflows in setup instructions.
