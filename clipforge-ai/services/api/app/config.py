"""ClipForge AI — application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/clipforge.db"

    # ── OmniRouter (LLM gateway) ─────────────────────────────────────
    OMNIROUTER_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTER_API_KEY: str = ""
    OMNIROUTER_MODEL: str = "llama3"

    # ── Storage ───────────────────────────────────────────────────────
    STORAGE_ROOT: str = str(Path("storage").resolve())
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_CONCURRENT_DOWNLOADS: int = 1
    DOWNLOAD_MAX_RETRIES: int = 6
    NETWORK_TIMEOUT_SECONDS: int = 90

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── FFmpeg ────────────────────────────────────────────────────────
    FFMPEG_PATH: str = ""
    FFPROBE_PATH: str = ""

    def get_ffmpeg_binary(self) -> str:
        """Resolve valid ffmpeg executable path."""
        import shutil
        if self.FFMPEG_PATH and shutil.which(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        if self.FFMPEG_PATH and Path(self.FFMPEG_PATH).exists():
            return str(Path(self.FFMPEG_PATH).resolve())
        # Check tools/ffmpeg directory in project
        candidates = [
            Path("tools/ffmpeg/ffmpeg.exe"),
            Path("../../tools/ffmpeg/ffmpeg.exe"),
            Path(__file__).resolve().parents[3] / "tools" / "ffmpeg" / "ffmpeg.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        return shutil.which("ffmpeg") or "ffmpeg"

    def get_ffprobe_binary(self) -> str:
        """Resolve valid ffprobe executable path."""
        import shutil
        if self.FFPROBE_PATH and shutil.which(self.FFPROBE_PATH):
            return self.FFPROBE_PATH
        if self.FFPROBE_PATH and Path(self.FFPROBE_PATH).exists():
            return str(Path(self.FFPROBE_PATH).resolve())
        # Check tools/ffmpeg directory in project
        candidates = [
            Path("tools/ffmpeg/ffprobe.exe"),
            Path("../../tools/ffmpeg/ffprobe.exe"),
            Path(__file__).resolve().parents[3] / "tools" / "ffmpeg" / "ffprobe.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        return shutil.which("ffprobe") or "ffprobe"

    # ── Security ──────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    ENCRYPTION_KEY: str = ""


def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
