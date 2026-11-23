# TROUBLESHOOTING.md

## Common Issues & Solutions (Native Windows)

### 1. Backend won't start

**Symptom**: `uvicorn` fails or exits immediately.

**Solutions**:
1. Ensure the Python virtual environment is activated:
   ```powershell
   .\services\api\.venv\Scripts\Activate.ps1
   ```
2. Check for port 8000 conflicts:
   ```powershell
   netstat -ano | findstr :8000
   ```
3. Inspect the error log: `scripts\backend.err.log`.

### 2. Frontend won't start or build errors

**Symptom**: `npm run dev` or `npm run build` fails.

**Solutions**:
1. Verify Node.js version: `node --version` (needs >= 18).
2. Clean and reinstall modules if packages were corrupted:
   ```powershell
   cd apps\web
   Remove-Item -Recurse -Force node_modules, .next
   npm install
   ```
3. Check for port 3000 conflicts:
   ```powershell
   netstat -ano | findstr :3000
   ```

### 3. SQLite Database Locked / Concurrency

**Symptom**: `sqlite3.OperationalError: database is locked`

**Solutions**:
1. WAL (Write-Ahead Logging) is enabled by default in `app/db.py`.
2. Ensure directory `services/api/data/` has standard write permissions.
3. If database file is corrupted during unexpected shutdown, backup and remove `services/api/data/clipforge.db`, then run `python -m alembic upgrade head`.

### 4. FFmpeg / FFprobe not found

**Symptom**: Health endpoint reports `"ffmpeg": {"status": "not_found"}`

**Solutions**:
1. Download a static Windows build from https://gyan.dev/ffmpeg/builds/
2. Extract and copy `ffmpeg.exe` and `ffprobe.exe` into a folder on your machine (e.g. `C:\ffmpeg\bin`).
3. Add `C:\ffmpeg\bin` to your Windows User or System PATH environment variable.
4. Alternatively, specify the absolute path in `.env`:
   ```
   FFMPEG_PATH=C:/ffmpeg/bin/ffmpeg.exe
   FFPROBE_PATH=C:/ffmpeg/bin/ffprobe.exe
   ```

### 5. OmniRouter Unreachable

**Symptom**: Health endpoint reports `"omnirouter": {"status": "unreachable"}`

**Solutions**:
1. Ensure your local OmniRouter service is running on `http://localhost:11434`.
2. Check `OMNIROUTER_BASE_URL` in `.env`.
3. If OmniRouter runs on a custom port or path, update `.env` and restart the backend.
