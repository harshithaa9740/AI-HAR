"""
System Settings and Runtime Configuration Endpoints
"""
from typing import Dict, Any
from fastapi import APIRouter
from app.schemas.system import SettingsUpdateRequest
from app.core.config import settings
from app.services.sequence_validator import SequenceValidator
from app.services.experiment_service import experiment_service
from app.services.stream_service import stream_service
from app.services.video_service import video_service

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def get_settings():
    """Retrieve current runtime configuration."""
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
def update_settings(payload: SettingsUpdateRequest):
    """Update system settings dynamically at runtime."""
    if payload.ai_mode is not None:
        settings.AI_MODE = payload.ai_mode
    if payload.confidence_threshold is not None:
        settings.CONFIDENCE_THRESHOLD = payload.confidence_threshold
        experiment_service.validator.confidence_threshold = payload.confidence_threshold
    if payload.object_confidence_threshold is not None:
        settings.OBJECT_CONFIDENCE_THRESHOLD = payload.object_confidence_threshold
    if payload.video_source is not None:
        settings.VIDEO_SOURCE = payload.video_source
        video_service.source = payload.video_source
    if payload.video_recording_enabled is not None:
        settings.VIDEO_RECORDING_ENABLED = payload.video_recording_enabled
    if payload.voice_enabled is not None:
        settings.VOICE_ENABLED = payload.voice_enabled
    if payload.log_level is not None:
        settings.LOG_LEVEL = payload.log_level

    # Streaming adjustments
    if payload.stream_destination_ip is not None:
        stream_service.destination_ip = payload.stream_destination_ip
    if payload.stream_port is not None:
        stream_service.port = payload.stream_port
    if payload.stream_enabled is not None:
        if payload.stream_enabled and not stream_service.is_streaming:
            stream_service.start_streaming()
        elif not payload.stream_enabled and stream_service.is_streaming:
            stream_service.stop_streaming()

    return {
        "status": "UPDATED",
        "settings": get_settings()
    }
