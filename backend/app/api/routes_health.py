"""
Health and System Status API Endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.schemas.system import HealthResponse, SystemStatusResponse
from app.core.config import settings
from app.services.video_service import video_service
from app.services.stream_service import stream_service
from app.services.voice_service import voice_engine
from app.workers.video_worker import video_worker
from app.db import models

router = APIRouter(tags=["System & Health"])


def _check_db_health(db: Session) -> bool:
    """Safely check if the database is accessible."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """Returns basic health check, database status, and offline status guarantee."""
    db_ok = _check_db_health(db)
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        offline_mode=settings.OFFLINE_ONLY,
        database_connected=db_ok,
        database_path=settings.DATABASE_URL
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    """Returns complete system diagnostics, AI mode, video status, database path, and offline guarantee."""
    db_ok = _check_db_health(db)
    active_sessions_count = 0
    if db_ok:
        try:
            active_sessions_count = db.query(models.ExperimentSession).filter(
                models.ExperimentSession.status.in_(["ACTIVE", "RUNNING", "CREATED"])
            ).count()
        except Exception:
            active_sessions_count = 0

    video_status = video_service.get_status()
    stream_status = stream_service.get_status()
    voice_status = voice_engine.get_status()

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        offline_mode=settings.OFFLINE_ONLY,
        ai_mode=settings.AI_MODE,
        database_connected=db_ok,
        database_path=settings.DATABASE_URL,
        active_sessions=active_sessions_count,
        video_worker_running=video_worker.is_running,
        video_source=str(video_service.source),
        recording_active=video_status["is_recording"],
        ip_streaming_active=stream_status["is_streaming"],
        destination_ip=stream_status["destination_ip"] if stream_status["is_streaming"] else None,
        voice_engine_active=voice_status.get("enabled", True),
        confidence_threshold=settings.CONFIDENCE_THRESHOLD
    )
