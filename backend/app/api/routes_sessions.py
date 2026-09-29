"""
Session Lifecycle, Validation Events, and Log Retrieval Endpoints
"""
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.schemas.session import (
    SessionCreate,
    SessionStartRequest,
    SessionStopRequest,
    SessionResponse,
    SessionLogResponse
)
from app.schemas.event import (
    AlertResponse,
    DetectionEventResponse,
    SequenceEventResponse,
    AlertEventResponse,
    SystemEventResponse,
    SessionTimelineResponse,
    TimelineEvent
)
from app.services.session_service import (
    session_service,
    InvalidStateTransitionError,
    SessionNotFoundError,
    ExperimentNotFoundError,
)
from app.services.event_service import event_service
from app.services.logging_service import SessionLoggingService
from app.services.video_service import video_service
from app.workers.video_worker import video_worker
from app.schemas.camera import CameraStartRequest, CameraStatusResponse, FrameMetadataResponse
from app.schemas.detection import SessionInferenceResponse, InferenceFrameRequest
from app.services.camera_service import camera_service
from app.camera.mock_camera import MockCameraSource
from app.camera.exceptions import (
    CameraAlreadyRunningError,
    CameraStoppedError,
    CameraSourceError,
    InvalidVideoFileError,
)
from app.ml.inference_engine import inference_engine
from app.services.sequence_validator import sequence_validator
from app.db.repository import get_steps_for_experiment




router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """
    Create a new experiment execution session in CREATED state.
    Session is not started until POST /api/sessions/{session_id}/start is called.
    """
    try:
        session = session_service.create_session(
            db=db,
            experiment_id=payload.experiment_id,
            session_uuid=payload.session_uuid or payload.session_code,
            stream_enabled=payload.stream_enabled,
            session_name=payload.session_name,
            operator_label=payload.operator_label,
            notes=payload.notes
        )
        return session
    except ExperimentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[SessionResponse])
@router.get("/", response_model=List[SessionResponse])
def list_sessions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    experiment_id: Optional[Union[int, str]] = Query(None, description="Filter sessions by experiment ID"),
    db: Session = Depends(get_db)
):
    """Retrieve all experiment execution sessions ordered by creation date."""
    return session_service.list_sessions(db, limit=limit, offset=offset, experiment_id=experiment_id)


@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session_direct(payload: SessionStartRequest, db: Session = Depends(get_db)):
    """
    Convenience endpoint: Initialize and start an experiment session immediately.
    Maintained for backward compatibility.
    """
    try:
        session = session_service.start_session(
            db=db,
            experiment_id=payload.experiment_id,
            session_code=payload.session_code or payload.session_uuid
        )
        video_worker.start(session_id=session.id)
        return session
    except (ExperimentNotFoundError, SessionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
def get_session_status(session_id: str, db: Session = Depends(get_db)):
    """Retrieve session details, current step, and execution state."""
    try:
        session = session_service.get_session(db, session_id)
        return session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/start", response_model=SessionResponse)
def start_existing_session(session_id: str, db: Session = Depends(get_db)):
    """Start an existing session (CREATED -> RUNNING)."""
    try:
        session = session_service.start_session(db=db, session_id=session_id)
        video_worker.start(session_id=session.id)
        return session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_id}/pause", response_model=SessionResponse)
def pause_session(session_id: str, db: Session = Depends(get_db)):
    """Pause an active experiment session (RUNNING -> PAUSED). Sequence state is preserved."""
    try:
        session = session_service.pause_session(db=db, session_id=session_id)
        return session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_id}/resume", response_model=SessionResponse)
def resume_session(session_id: str, db: Session = Depends(get_db)):
    """Resume a paused experiment session (PAUSED -> RUNNING). Sequence state is preserved."""
    try:
        session = session_service.resume_session(db=db, session_id=session_id)
        return session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_id}/stop", response_model=SessionResponse)
def stop_session(
    session_id: str,
    payload: Optional[SessionStopRequest] = None,
    db: Session = Depends(get_db)
):
    """Stop active or paused session (RUNNING/PAUSED -> STOPPED). Historical events are preserved."""
    try:
        reason = payload.reason if payload else "User requested stop"
        session = session_service.stop_session(db=db, session_id=session_id, reason=reason)

        # Stop video capture and worker
        video_summary = video_service.stop_capture()
        video_worker.stop()

        if video_summary.get("recording_path"):
            rec_path = video_summary.get("recording_path")
            session.recording_path = rec_path
            db.commit()
            db.refresh(session)

            try:
                import os
                from app.db.repository import ArtifactRepository
                if os.path.exists(rec_path):
                    ArtifactRepository.create(
                        db=db,
                        session_id=session.id,
                        artifact_type="recording",
                        file_path=str(rec_path),
                        file_name=os.path.basename(rec_path),
                        mime_type="video/mp4",
                        file_size_bytes=os.path.getsize(rec_path),
                        metadata={"duration": video_summary.get("duration", 0), "fps": video_summary.get("fps", 30)}
                    )
            except Exception as e:
                logger.error(f"Failed to record session artifact: {e}")

        return session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_id}/reset", response_model=SessionResponse)
def reset_session(session_id: str, db: Session = Depends(get_db)):
    """Reset session sequence progression state to Step 1 without deleting historical events."""
    try:
        updated_session = session_service.reset_session(db, session_id)
        return updated_session
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{session_id}/events", response_model=SessionTimelineResponse)
def get_session_events_timeline(
    session_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. SYSTEM, SEQUENCE, ALERT, DETECTION, VALID, etc.)"),
    start_time: Optional[datetime] = Query(None, description="Filter events on or after this ISO timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter events on or before this ISO timestamp"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Max events to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve unified chronological event timeline for a session (Oldest -> Newest).
    Combines system lifecycle, sequence validation, alerts, and perception detections.
    """
    try:
        session = session_service.get_session(db, session_id)
        return event_service.get_session_timeline(
            db=db,
            session_id=session.id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/sequence-events", response_model=List[SequenceEventResponse])
def get_session_sequence_events_route(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieve deterministic sequence validation outcome events for a session."""
    try:
        return event_service.get_session_sequence_events(db, session_id, limit=limit)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/alerts", response_model=List[AlertEventResponse])
def get_session_alerts_route(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieve all alert and deviation events for a session."""
    try:
        return event_service.get_session_alert_events(db, session_id, limit=limit)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/alerts/{alert_id}/acknowledge", response_model=AlertEventResponse)
def acknowledge_alert_route(
    session_id: str,
    alert_id: int,
    db: Session = Depends(get_db)
):
    """Mark an alert event as acknowledged with a timestamp."""
    session = session_service.get_session(db, session_id)
    from app.db.repository import acknowledge_alert
    alert = acknowledge_alert(db, alert_id)
    if not alert or alert.session_id != session.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found for session.")
    return alert


@router.get("/{session_id}/detections", response_model=List[DetectionEventResponse])
def get_session_detections_route(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieve perception detection events for a session."""
    try:
        return event_service.get_session_detection_events(db, session_id, limit=limit)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/system-events", response_model=List[SystemEventResponse])
def get_session_system_events_route(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieve system lifecycle and state transition events for a session."""
    try:
        return event_service.get_session_system_events(db, session_id, limit=limit)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/log")
def get_session_log(
    session_id: str,
    format: str = Query("txt", pattern="^(txt|jsonl)$"),
    download: bool = False,
    db: Session = Depends(get_db)
):
    """Retrieve or download the session audit log in TXT or JSONL format."""
    try:
        session = session_service.get_session(db, session_id)
        content = SessionLoggingService.read_log(session.id, session.session_code, format_type=format)
        
        # Persist log artifact reference in database
        try:
            import os
            from app.db.repository import ArtifactRepository
            paths = SessionLoggingService.get_log_paths(session.id, session.session_code)
            log_p = paths["jsonl"] if format == "jsonl" else paths["txt"]
            if log_p.exists():
                existing = ArtifactRepository.get_for_session(db, session.id, artifact_type=f"log_{format}")
                if not existing:
                    ArtifactRepository.create(
                        db=db,
                        session_id=session.id,
                        artifact_type=f"log_{format}",
                        file_path=str(log_p),
                        file_name=log_p.name,
                        mime_type="application/x-ndjson" if format == "jsonl" else "text/plain",
                        file_size_bytes=log_p.stat().st_size,
                        metadata={"format": format}
                    )
        except Exception as e:
            logger.error(f"Failed to record log artifact: {e}")

        if download:
            filename = f"session_{session.session_code}.{format}"
            headers = {"Content-Disposition": f"attachment; filename={filename}"}
            return PlainTextResponse(content, media_type="text/plain", headers=headers)

        return SessionLogResponse(
            session_id=session.id,
            session_code=session.session_code,
            log_format=format,
            content=content
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/artifacts")
def get_session_artifacts_route(
    session_id: str,
    artifact_type: Optional[str] = Query(None, description="Filter by artifact type (recording, log_txt, log_jsonl)"),
    db: Session = Depends(get_db)
):
    """Retrieve all stored artifacts (recordings, audit logs, reports) for a session."""
    try:
        session = session_service.get_session(db, session_id)
        from app.db.repository import ArtifactRepository
        artifacts = ArtifactRepository.get_for_session(db, session.id, artifact_type=artifact_type)
        return [
            {
                "id": a.id,
                "session_id": a.session_id,
                "artifact_type": a.artifact_type,
                "file_path": a.file_path,
                "file_name": a.file_name,
                "mime_type": a.mime_type,
                "file_size_bytes": a.file_size_bytes,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in artifacts
        ]
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# Session-Scoped Camera Pipeline Endpoints
# ==========================================

@router.post("/{session_id}/camera/start", response_model=CameraStatusResponse)
def start_session_camera_route(
    session_id: str,
    req: Optional[CameraStartRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Start the session-scoped camera pipeline for an active or created experiment session.
    """
    try:
        session = session_service.get_session(db, session_id)
        if session.status in ("COMPLETED", "STOPPED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start camera for session in '{session.status}' state."
            )

        source_type = req.source_type if req else None
        camera_index = req.camera_index if req else None
        file_path = req.file_path if req else None
        target_fps = req.target_fps if req else None
        frame_width = req.frame_width if req else None
        frame_height = req.frame_height if req else None
        buffer_size = req.buffer_size if req else None
        loop = req.loop if req else False

        status_dict = camera_service.start_session_camera(
            session_id=str(session.id),
            source_type=source_type,
            camera_index=camera_index,
            file_path=file_path,
            target_fps=target_fps,
            frame_width=frame_width,
            frame_height=frame_height,
            buffer_size=buffer_size,
            loop=loop,
            db=db
        )
        return status_dict
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except CameraAlreadyRunningError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session camera already running: {str(e)}"
        )
    except (CameraSourceError, InvalidVideoFileError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start session camera: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal camera error: {str(e)}"
        )


@router.post("/{session_id}/camera/stop", response_model=CameraStatusResponse)
def stop_session_camera_route(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Stop the camera pipeline and release resources for the specified session.
    """
    try:
        session = session_service.get_session(db, session_id)
        return camera_service.stop_session_camera(str(session.id), db=db)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop session camera: {str(e)}"
        )


@router.get("/{session_id}/camera/status", response_model=CameraStatusResponse)
def get_session_camera_status_route(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get current camera pipeline status and ingestion metrics for the session.
    """
    try:
        session = session_service.get_session(db, session_id)
        return camera_service.get_session_status(str(session.id))
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/camera/frame", response_model=FrameMetadataResponse)
@router.get("/{session_id}/camera/frame", response_model=FrameMetadataResponse)
def get_session_camera_frame_route(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve latest preprocessed frame metadata for the specified session.
    Excludes large raw image binary payloads.
    """
    try:
        session = session_service.get_session(db, session_id)
        frame = camera_service.read_session_frame(str(session.id))
        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                detail="No frame available in session buffer."
            )
        return frame.to_metadata_dict()
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CameraStoppedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session camera is stopped: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read session frame: {str(e)}"
        )


@router.post("/{session_id}/inference/frame", response_model=SessionInferenceResponse)
def infer_session_frame_route(
    session_id: str,
    validate: bool = Query(default=True, description="Whether to evaluate observation against Sequence Validator"),
    req: Optional[InferenceFrameRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Process an ingested session frame through the AI perception pipeline.
    Produces an ObservedAction and optionally feeds it to the deterministic Sequence Validator.
    """
    try:
        session = session_service.get_session(db, session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if session.status in ("COMPLETED", "STOPPED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot run inference on session in '{session.status}' state."
        )

    # 1. Acquire frame from session's active camera or generate development step frame
    frame: Optional[Frame] = None
    try:
        frame = camera_service.read_session_frame(str(session.id))
    except (CameraStoppedError, Exception):
        pass

    if frame is None:
        # Development fallback: generate deterministic frame matching current session step
        step_idx = session.current_step_number or 1
        mock_source = MockCameraSource(source_id=f"session-{session.id}-dev")
        mock_source.open()
        for _ in range(step_idx):
            frame = mock_source.read_frame()
        mock_source.release()

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No frame available for session inference."
        )

    # 2. Run AI Inference
    scenario_override = req.scenario if req else None
    try:
        obs, detections = inference_engine.infer(frame, scenario_override=scenario_override)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI inference processing failed: {str(e)}"
        )

    validation_payload = None

    # 3. Optional Sequence Validation
    if validate:
        # Record Detection Event in database if active action
        if obs.action_code not in (None, "IDLE"):
            event_service.record_detection_event(
                db=db,
                session_id=session.id,
                entity_type="action",
                action_code=obs.action_code,
                confidence=obs.confidence,
                metadata=obs.metadata
            )

        from app.services.experiment_service import experiment_service
        val_res = experiment_service.validate_session_action(
            db=db,
            session_id=session.id,
            action_code=obs.action_code,
            confidence=obs.confidence,
            observed_objects=obs.observed_objects
        )
        validation_payload = val_res.model_dump() if hasattr(val_res, "model_dump") else dict(val_res)


    return SessionInferenceResponse(
        session_id=str(session.id),
        frame_id=frame.frame_id,
        observation=obs,
        validation=validation_payload
    )



