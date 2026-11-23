# IMPLEMENTATION_PLAN.md

## Milestones

| Milestone | Description | Deliverables | Acceptance Criteria |
|-----------|-------------|--------------|----------------------|
| **M1** – Foundation | Repo init, native Windows dev environment, health checks, dashboard shell | PowerShell scripts, FastAPI skeleton, Next.js dashboard, SQLite + APScheduler, documentation | Backend and frontend start natively on Windows; `/api/v1/health` returns OK; dashboard loads; tests pass. |
| **M2** – Video Ingestion | Upload endpoint, file validation, FFprobe metadata, thumbnail generation, background job | `POST /videos/upload`, DB records, thumbnail in storage, job status SSE | Real MP4 uploaded via UI appears in dashboard with correct metadata and thumbnail. |
| **M3** – AI Analysis | OmniRouter adapter, Faster-Whisper transcription, scene detection, viral moment generation | `/videos/{id}/transcript`, `/videos/{id}/candidates` endpoints | Transcript segments stored; at least three candidate moments returned with scores. |
| **M4** – Rendering | FFmpeg clip extraction, smart cropping, caption presets, progress tracking | `POST /clips/generate`, `POST /clips/{id}/render`, preview URLs | Generated MP4 clips playable; FFprobe confirms codec/size; captions visible. |
| **M5** – Clip Editor | Timeline UI, trim, subtitle edit, re-render | In-app clip editor, updated clip after edit | User can adjust start/end, change caption preset, and re-render without errors. |
| **M6** – Publishing | OAuth flows, YouTube/Instagram/Facebook publishing, scheduling queue | Connected account management, `POST /publishing/jobs`, status tracking | Authenticated account can publish a clip; API returns platform post ID and final status `published`. |
| **M7** – Livestream Automation | Kick source monitoring, segment capture, auto-clip generation | Live monitor UI, background ingestion of livestream segments, candidate generation | Authorized Kick livestream produces at least one queued clip after go-live. |
| **M8** – Analytics & Hardening | Platform analytics collection, ranking calibration, security audit, extensive tests | Analytics dashboard, calibrated scoring, security report, >80% test coverage | Real analytics displayed; security checks pass; CI runs all tests. |

## Task Dependencies
- M2 depends on M1.
- M3 depends on M2 (transcript data).
- M4 depends on M3 (candidate moments).
- M5 depends on M4 (rendered clips).
- M6 depends on M4/M5 (available clips).
- M7 can run in parallel with M3–M5 after basic ingestion exists.
- M8 runs after all core features are functional.

## Implementation Order
1. Repository scaffolding (folders, scripts, .env.example). ✅
2. Core docs and markdown files. ✅
3. Backend skeleton (FastAPI, health, config, models). ✅
4. Frontend skeleton (Next.js, dashboard, health display). ✅
5. Video upload & storage.
6. Background job infrastructure. ✅ (APScheduler)
7. Transcription pipeline.
8. AI analysis service.
9. Rendering pipeline.
10. Clip editor UI.
11. Social publishing integrations.
12. Livestream monitoring.
13. Analytics collection.
14. Security hardening & test expansion.

## Acceptance Checklist
- All health endpoints respond. ✅
- End-to-end flow works on a real video file. (M2+)
- No placeholder data; real FFmpeg/Faster-Whisper processes run. (M2+)
- Documentation files are up-to-date after each milestone. ✅
