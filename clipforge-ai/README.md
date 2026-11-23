# ClipForge AI

A professional, high-performance desktop-grade SaaS web application that transforms long-form videos and livestreams into viral short-form clips (YouTube Shorts, Instagram Reels, Facebook Reels) with AI-powered moment discovery, automated animated subtitles, complete frame-accurate video editing, and metadata customization.

Built exclusively for native **Windows 11** — zero Docker required.

---

## ⚡ Quick Start (Native Windows)

### Prerequisites
- **Windows 11** (64-bit)
- **Python 3.10+** (Python 3.14 tested)
- **Node.js 18+** & **npm 11+**
- **FFmpeg & FFprobe** (v9.0.2 included in `tools/ffmpeg/` or via system PATH)

### One-Command Setup & Launch

```powershell
# 1. Clone / Navigate to project
cd clipforge-ai

# 2. Run automated setup (creates virtual environment, installs packages, prepares storage)
.\scripts\setup.ps1

# 3. Start development servers (FastAPI backend + Next.js frontend + background worker)
.\scripts\start.ps1

# 4. Open in browser:
#    Dashboard: http://localhost:3000
#    Backend API: http://localhost:8000
#    API Docs: http://localhost:8000/docs
```

### Stop Services & Run Tests

```powershell
.\scripts\stop.ps1     # Stops all project processes gracefully
.\scripts\test.ps1     # Runs pytest suite + live health verification
```

---

## 📁 Repository Structure

```text
clipforge-ai/
├── README.md                          # Main project guide
├── AGENTS.md                          # Agent team pointer
│
├── docs/                              # Canonical documentation
│   ├── 01-project/
│   │   ├── PROJECT.md                 # Project vision & scope
│   │   ├── REQUIREMENTS.md            # Detailed product requirements (PRD)
│   │   └── IMPLEMENTATION_PLAN.md     # Phase-by-phase roadmap
│   ├── 02-architecture/
│   │   ├── ARCHITECTURE.md            # System architecture & data flow
│   │   ├── DATABASE_SCHEMA.md         # Database tables & relations
│   │   ├── API_CONTRACTS.md           # REST endpoint specifications
│   │   └── DECISIONS.md               # Architecture decision records (ADRs)
│   ├── 03-agents/
│   │   ├── AGENTS.md                  # Team roles & collaboration rules
│   │   ├── TASKS.md                   # Task board with status & owners
│   │   ├── PROGRESS.md                # Milestone completion tracking
│   │   └── HANDOFF.md                 # Inter-agent handoff log
│   ├── 04-engineering/
│   │   ├── AI_PIPELINE.md             # OmniRouter & Faster-Whisper pipeline
│   │   ├── VIDEO_PIPELINE.md          # FFmpeg, reframing, and proxy pipeline
│   │   ├── INTEGRATIONS.md            # Social platform & AI integrations
│   │   ├── TESTING.md                 # Test strategy & commands
│   │   └── SECURITY.md                # Secret management & data validation
│   └── 05-operations/
│       ├── WINDOWS_SETUP.md           # Native Windows setup & manual start
│       ├── TROUBLESHOOTING.md         # Common errors & solutions
│       └── RELEASE_CHECKLIST.md       # Pre-release verification checklist
│
├── apps/
│   └── web/                           # Next.js 14 frontend (Tailwind CSS, App Router)
├── services/
│   └── api/                           # FastAPI backend (SQLite, SQLAlchemy, Alembic)
│       ├── app/                       # Application code & REST routers
│       ├── data/                      # Local SQLite databases (clipforge.db, jobs.db)
│       └── migrations/                # Alembic schema migrations
├── scripts/                           # Windows PowerShell automation scripts
└── storage/                           # Local media storage (uploads, clips, proxies, thumbnails)
```

---

## 🛠 Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | Next.js 14, React 18, TypeScript | App Router, Tailwind CSS, Framer Motion, Zustand |
| **Backend** | FastAPI, Python 3.14 | Uvicorn, SQLAlchemy 2.0, Alembic, SQLite WAL mode |
| **Background Processing** | SQLite Durable Queue | Atomic job claiming, restart recovery, retry handling |
| **Media Processing** | FFmpeg, FFprobe, OpenCV | Low-res proxy editing, 9:16 smart crop, ASS subtitles |
| **AI Integration** | Local OmniRouter | Moment scoring, title/description generation, hashtags |
