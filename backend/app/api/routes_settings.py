"""
System Settings and Runtime Configuration Endpoints
Persistent system settings backed by SQLite database layer.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.system import SettingsUpdateRequest
from app.core.config import settings
from app.db.database import get_db
from app.db.repository import SettingRepository
from app.services.sequence_validator import SequenceValidator
from app.services.experiment_service import experiment_service
from app.services.stream_service import stream_service
from app.services.video_service import video_service

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    """Retrieve current runtime configuration, hydrated from persistent database."""
    # Check if persistent settings are stored in database
    db_settings = SettingRepository.get_all(db)

    # Sync any persisted values to runtime settings
    if "ai_mode" in db_settings:
        settings.AI_MODE = db_settings["ai_mode"]
    if "confidence_threshold" in db_settings:
        settings.CONFIDENCE_THRESHOLD = float(db_settings["confidence_threshold"])
    if "object_confidence_threshold" in db_settings:
        settings.OBJECT_CONFIDENCE_THRESHOLD = float(db_settings["object_confidence_threshold"])
    if "video_source" in db_settings:
        settings.VIDEO_SOURCE = db_settings["video_source"]
    if "video_recording_enabled" in db_settings:
        settings.VIDEO_RECORDING_ENABLED = bool(db_settings["video_recording_enabled"])
    if "voice_enabled" in db_settings:
        settings.VOICE_ENABLED = bool(db_settings["voice_enabled"])
    if "log_level" in db_settings:
        settings.LOG_LEVEL = db_settings["log_level"]

    return {
        "app_env": settings.APP_ENV,
        "ai_mode": settings.AI_MODE,
        "offline_only": settings.OFFLINE_ONLY,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "object_confidence_threshold": settings.OBJECT_CONFIDENCE_THRESHOLD,
        "video_source": settings.VIDEO_SOURCE,
        "video_recording_enabled": settings.VIDEO_RECORDING_ENABLED,
        "stream_enabled": stream_service.is_streaming,
        "stream_destination_ip": stream_service.destination_ip,
        "stream_port": stream_service.port,
        "voice_enabled": settings.VOICE_ENABLED,
        "voice_engine": settings.VOICE_ENGINE,
        "log_level": settings.LOG_LEVEL
    }


@router.post("")
def update_settings(payload: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """Update system settings dynamically and persist to database."""
    if payload.ai_mode is not None:
        settings.AI_MODE = payload.ai_mode
        SettingRepository.set(db, "ai_mode", payload.ai_mode)
    if payload.confidence_threshold is not None:
        settings.CONFIDENCE_THRESHOLD = payload.confidence_threshold
        experiment_service.validator.confidence_threshold = payload.confidence_threshold
        SettingRepository.set(db, "confidence_threshold", payload.confidence_threshold)
    if payload.object_confidence_threshold is not None:
        settings.OBJECT_CONFIDENCE_THRESHOLD = payload.object_confidence_threshold
        SettingRepository.set(db, "object_confidence_threshold", payload.object_confidence_threshold)
    if payload.video_source is not None:
        settings.VIDEO_SOURCE = payload.video_source
        video_service.source = payload.video_source
        SettingRepository.set(db, "video_source", payload.video_source)
    if payload.video_recording_enabled is not None:
        settings.VIDEO_RECORDING_ENABLED = payload.video_recording_enabled
        SettingRepository.set(db, "video_recording_enabled", payload.video_recording_enabled)
    if payload.voice_enabled is not None:
        settings.VOICE_ENABLED = payload.voice_enabled
        SettingRepository.set(db, "voice_enabled", payload.voice_enabled)
    if payload.log_level is not None:
        settings.LOG_LEVEL = payload.log_level
        SettingRepository.set(db, "log_level", payload.log_level)

    # Streaming adjustments
    if payload.stream_destination_ip is not None:
        stream_service.destination_ip = payload.stream_destination_ip
        SettingRepository.set(db, "stream_destination_ip", payload.stream_destination_ip)
    if payload.stream_port is not None:
        stream_service.port = payload.stream_port
        SettingRepository.set(db, "stream_port", payload.stream_port)
    if payload.stream_enabled is not None:
        SettingRepository.set(db, "stream_enabled", payload.stream_enabled)
        if payload.stream_enabled and not stream_service.is_streaming:
            stream_service.start_streaming()
        elif not payload.stream_enabled and stream_service.is_streaming:
            stream_service.stop_streaming()

    return {
        "status": "UPDATED",
        "settings": get_settings(db)
    }
