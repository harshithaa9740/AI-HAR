"""
Real-Time Processing Endpoints for Session Experiment Ingestion & Validation Loop
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repository import get_session
from app.schemas.processing import (
    ProcessingStartRequest,
    ProcessingStatusResponse,
    ProcessingMetricsResponse,
)
from app.services.realtime_processor import (
    RealTimeProcessorRegistry,
    RealTimeProcessorError,
)
from app.services.processing_state import InvalidProcessingStateTransitionError
from app.camera.exceptions import CameraStoppedError, CameraSourceError
from app.ml.exceptions import ProviderUnavailableError


router = APIRouter(prefix="/sessions/{session_id}/processing", tags=["Real-Time Processing"])


@router.post("/start", response_model=ProcessingStatusResponse)
def start_session_processing(
    session_id: str,
    payload: Optional[ProcessingStartRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Start continuous real-time AI inference and protocol validation loop for a session.
    Requires the session to be in RUNNING status and camera to be active.
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    target_fps = payload.target_fps if payload else None
    processor = RealTimeProcessorRegistry.get_or_create(session_id=session_id, target_fps=target_fps)

    if processor.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Real-time processing worker for session '{session_id}' is already running."
        )

    try:
        status_dict = processor.start(db=db)
        return status_dict
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (CameraStoppedError, CameraSourceError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProviderUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except RealTimeProcessorError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start processor: {str(e)}")


@router.post("/stop", response_model=ProcessingStatusResponse)
def stop_session_processing(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Stop continuous real-time AI processing loop for a session.
    Preserves session events and accumulated metrics.
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    processor = RealTimeProcessorRegistry.get_for_session(session_id)
    if processor is None:
        # Return stopped status gracefully
        return {
            "session_id": str(session_id),
            "state": "STOPPED",
            "worker_active": False,
            "camera_active": False,
            "ai_ready": True,
            "target_fps": 10,
            "frames_processed": 0,
            "last_frame_timestamp": None,
            "last_result": None,
            "last_error": None,
        }

    status_dict = processor.stop(db=db)
    return status_dict


@router.post("/pause", response_model=ProcessingStatusResponse)
def pause_session_processing(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Pause real-time frame processing while keeping the worker and session state intact.
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    processor = RealTimeProcessorRegistry.get_for_session(session_id)
    if processor is None or not processor.is_active():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No active processing worker running for session '{session_id}'."
        )

    try:
        status_dict = processor.pause(db=db)
        return status_dict
    except (RealTimeProcessorError, InvalidProcessingStateTransitionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/resume", response_model=ProcessingStatusResponse)
def resume_session_processing(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Resume real-time frame processing from PAUSED state.
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    processor = RealTimeProcessorRegistry.get_for_session(session_id)
    if processor is None or not processor.is_active():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No active processing worker to resume for session '{session_id}'."
        )

    try:
        status_dict = processor.resume(db=db)
        return status_dict
    except (RealTimeProcessorError, InvalidProcessingStateTransitionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/status", response_model=ProcessingStatusResponse)
def get_session_processing_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve real-time processing status, worker state, and latest validation result.
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    processor = RealTimeProcessorRegistry.get_for_session(session_id)
    if processor is None:
        return {
            "session_id": str(session_id),
            "state": "STOPPED",
            "worker_active": False,
            "camera_active": False,
            "ai_ready": True,
            "target_fps": 10,
            "frames_processed": 0,
            "last_frame_timestamp": None,
            "last_result": None,
            "last_error": None,
        }

    return processor.status()


@router.get("/metrics", response_model=ProcessingMetricsResponse)
def get_session_processing_metrics(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve in-memory runtime processing metrics (latency, FPS, dropped frames, results).
    """
    sess = get_session(db, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    processor = RealTimeProcessorRegistry.get_for_session(session_id)
    if processor is None:
        return {
            "session_id": str(session_id),
            "state": "STOPPED",
            "frames_received": 0,
            "frames_processed": 0,
            "frames_dropped": 0,
            "successful_inferences": 0,
            "failed_inferences": 0,
            "validation_results": {},
            "average_inference_time_ms": 0.0,
            "average_processing_time_ms": 0.0,
            "processing_fps": 0.0,
            "uptime_seconds": 0.0,
            "last_frame_timestamp": None,
            "last_successful_processing_timestamp": None,
        }

    return processor.get_metrics()
