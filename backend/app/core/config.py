"""
Configuration Settings for AURAVISION Offline System
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
LOGS_DIR = DATA_DIR / "logs"
EXPERIMENTS_DIR = DATA_DIR / "experiments"
DATASETS_DIR = DATA_DIR / "datasets"
MODELS_DIR = BASE_DIR / "models"


class Settings(BaseSettings):
    # App Information
    APP_ENV: str = "development"
    APP_NAME: str = "AURAVISION-Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Offline Guarantee
    OFFLINE_ONLY: bool = True

    # AI Pipeline Mode (mock / development / production)
    AI_MODE: str = "mock"

    # Database Engine Selection: "sqlite" (default, 100% offline) or "postgres" / "supabase"
    DB_ENGINE: str = "sqlite"

    # Database
    DATABASE_URL: Optional[str] = f"sqlite:///{DATA_DIR}/auravision.db"

    # Supabase / PostgreSQL Configuration (Step 5)
    # Strictly disabled during local offline operations. No credentials hardcoded.
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_DB_URL: Optional[str] = None
    SUPABASE_SYNC_ENABLED: bool = False
    SUPABASE_STORAGE_BUCKET_RECORDINGS: str = "auravision-recordings"
    SUPABASE_STORAGE_BUCKET_ARTIFACTS: str = "auravision-artifacts"

    @model_validator(mode="after")
    def validate_database_configuration(self):
        """
        Validate database selection and enforce clear failure if PostgreSQL/Supabase
        is explicitly selected without required connection credentials.
        """
        engine_type = (self.DB_ENGINE or "sqlite").strip().lower()
        if engine_type in ("postgres", "postgresql", "supabase"):
            target_url = self.SUPABASE_DB_URL or (
                self.DATABASE_URL if self.DATABASE_URL and "postgres" in self.DATABASE_URL.lower() else None
            )
            if not target_url or not target_url.strip():
                raise ValueError(
                    f"PostgreSQL/Supabase engine is explicitly selected (DB_ENGINE='{self.DB_ENGINE}'), "
                    "but SUPABASE_DB_URL (or a PostgreSQL DATABASE_URL) is not configured. "
                    "Please configure SUPABASE_DB_URL in your environment or set DB_ENGINE='sqlite' "
                    "for local offline operation."
                )
            self.DATABASE_URL = target_url.strip()
            self.OFFLINE_ONLY = False
        else:
            # Default to SQLite local file if not explicitly configured with another sqlite path
            if not self.DATABASE_URL or "sqlite" not in self.DATABASE_URL.lower():
                self.DATABASE_URL = f"sqlite:///{DATA_DIR}/auravision.db"
        return self

    @property
    def sanitized_database_url(self) -> str:
        """Return safe database URL with credentials masked for API responses, diagnostics, and logs."""
        url = self.DATABASE_URL or ""
        if "@" in url and "://" in url:
            try:
                prefix, rest = url.split("://", 1)
                userinfo, hostinfo = rest.split("@", 1)
                if ":" in userinfo:
                    username = userinfo.split(":", 1)[0]
                    return f"{prefix}://{username}:***@{hostinfo}"
                return f"{prefix}://***@{hostinfo}"
            except Exception:
                return "postgresql://[REDACTED]"
        return url

    # Camera & Frame Ingestion Pipeline (Step 7)
    CAMERA_SOURCE: str = "mock"  # "mock", "file", or "webcam"
    CAMERA_INDEX: int = 0
    VIDEO_FILE_PATH: Optional[str] = None
    TARGET_FPS: int = 10
    FRAME_WIDTH: int = 640
    FRAME_HEIGHT: int = 480
    FRAME_BUFFER_SIZE: int = 5

    # Video Settings
    VIDEO_SOURCE: str = "synthetic"  # Default to offline synthetic generator to avoid locking hardware camera
    VIDEO_RECORDING_ENABLED: bool = True
    VIDEO_FRAME_WIDTH: int = 1280
    VIDEO_FRAME_HEIGHT: int = 720
    VIDEO_FPS: int = 30

    # Local IP Video Streaming (Modular, Offline)
    STREAM_ENABLED: bool = False
    STREAM_DESTINATION_IP: str = "127.0.0.1"
    STREAM_PORT: int = 8554


    # AI Confidence Thresholds
    CONFIDENCE_THRESHOLD: float = Field(default=0.70, ge=0.0, le=1.0)
    OBJECT_CONFIDENCE_THRESHOLD: float = Field(default=0.60, ge=0.0, le=1.0)

    # Voice Engine Settings
    VOICE_ENABLED: bool = True
    VOICE_ENGINE: str = "mock"  # "local_tts" or "mock"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Custom Model Paths (Optional)
    MODEL_OBJECT_PATH: Optional[str] = None
    MODEL_ACTIVITY_PATH: Optional[str] = None
    MODEL_POSE_PATH: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self):
        """Ensure all required local data storage directories exist."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
        DATASETS_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
