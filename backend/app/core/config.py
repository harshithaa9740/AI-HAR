"""
Configuration Settings for AURAVISION Offline System
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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

    # Database
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/auravision.db"

    # Camera & Frame Ingestion Pipeline (Step 7)
    CAMERA_SOURCE: str = "mock"  # "mock", "file", or "webcam"
    CAMERA_INDEX: int = 0
    VIDEO_FILE_PATH: Optional[str] = None
    TARGET_FPS: int = 10
    FRAME_WIDTH: int = 640
    FRAME_HEIGHT: int = 480
    FRAME_BUFFER_SIZE: int = 5

    # Video Settings
    VIDEO_SOURCE: str = "0"  # Can be integer "0", file path, or "rtsp://..."
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
