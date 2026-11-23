# WINDOWS_SETUP.md

## Native Windows 11 Development & Deployment Guide

ClipForge AI runs 100% natively on Windows 11 without any Docker or virtualization containers.

### Prerequisites
- **Operating System**: Windows 11 64-bit
- **Python**: 3.10+ (Python 3.14 supported)
- **Node.js**: 18.0+ (Node 24 tested)
- **npm**: 10.0+
- **FFmpeg & FFprobe**: Installed and added to system PATH

### Automated Quick Setup

Run PowerShell as standard user:

```powershell
cd clipforge-ai
.\scripts\setup.ps1
```

This script:
1. Verifies Python, Node.js, and npm versions.
2. Checks for `ffmpeg.exe` and `ffprobe.exe` in PATH.
3. Creates a virtual environment at `services/api/.venv` with system site-packages.
4. Installs required Python backend packages (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `apscheduler`, `pytest`).
5. Prepares `storage/` and `data/` directories.
6. Installs frontend dependencies in `apps/web/`.
7. Initializes `.env` from `.env.example`.

### Running the Application

```powershell
.\scripts\start.ps1
```

The script starts:
- **FastAPI API Server**: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
- **Next.js Web Application**: `http://localhost:3000`
- **Durable Background Worker**: processes media queue jobs

### Stopping Services

```powershell
.\scripts\stop.ps1
```

Stops all project-associated Node and Python processes gracefully using stored PIDs.

### Running Verification Tests

```powershell
.\scripts\test.ps1
```

Executes the automated pytest test suite and verifies live API connectivity.
