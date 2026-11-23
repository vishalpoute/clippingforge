# TASKS.md — Active Task Board

| ID | Description | Owner | Priority | Status | Acceptance Criteria |
|---|---|---|---|---|---|
| **T1** | Initialize repository structure | DevOps (Agent 7) | High | **DONE** | Monorepo layout ready, Windows native |
| **T2** | Organize markdown documentation into `docs/` hierarchy | Architect (Agent 1) | High | **DONE** | 19 canonical files in `docs/01..05`, root AGENTS.md + README.md |
| **T3** | Completely remove Docker files & configuration | DevOps (Agent 7) | High | **DONE** | Zero Dockerfiles, zero compose files, zero container references |
| **T4** | Implement FastAPI backend & REST endpoints | Backend (Agent 3) | High | **DONE** | Health, videos, clips, AI suggestions, rendering, publishing APIs |
| **T5** | Implement SQLite durable background job queue | Backend (Agent 3) | High | **DONE** | Atomic claiming, restart recovery, retry handling, progress tracking |
| **T6** | Dedicated background media worker process | Backend (Agent 3) | High | **DONE** | `app.worker` claims jobs, executes probe, moment discovery, renders |
| **T7** | Build professional Next.js 14 frontend | Frontend (Agent 2) | High | **DONE** | Dark mode UI, 6 modular tabs, video library, editor canvas, metadata studio |
| **T8** | Implement professional video editor controls | Frontend (Agent 2) | High | **DONE** | Timeline scrubber, 9:16 reframe, crop X/Y, zoom, subtitle presets, audio |
| **T9** | Implement metadata & AI publishing studio | Frontend (Agent 2) | High | **DONE** | Character counters, YouTube/Reels tabs, hashtag injection, AI suggestions |
| **T10** | PowerShell automation scripts | DevOps (Agent 7) | High | **DONE** | `setup.ps1`, `start.ps1`, `stop.ps1`, `test.ps1` natively managing 3 processes |
| **T11** | Automated test suite expansion | QA (Agent 8) | High | **DONE** | 15/15 automated pytest tests passing (`test_db`, `test_health`, `test_queue`, `test_milestone2`) |
| **T12** | Local OmniRouter LLM integration adapter | AI (Agent 4) | Medium | **VERIFIED_OFFLINE** | Configurable endpoint; verified offline on port 11434 without simulation |
| **T13** | Install & configure FFmpeg and FFprobe | Video (Agent 5) | High | **DONE** | Official Gyan.FFmpeg 9.0.2 installed and configured in `tools/ffmpeg/` |
| **T14** | Milestone 2 Core Video Pipeline & Real Rendering | Video (Agent 5) | High | **DONE** | Upload, FFprobe metadata, thumbnail & 360p proxy, real 9:16 vertical render |
| **T15** | Social publishing OAuth integrations | Platform (Agent 6) | Medium | **BACKLOG** | Scheduled publishing stubs active; OAuth flows planned for Phase 5 |
| **T16** | Authorized Kick livestream monitoring | Platform (Agent 6) | Medium | **BACKLOG** | Planned for Phase 6 |
