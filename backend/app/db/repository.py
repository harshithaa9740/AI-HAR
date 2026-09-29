"""
Database Repository Layer for AURAVISION
Provides clean, reusable persistence functions and repositories without embedded business logic.
Fully transactional with automated rollback handling.
"""
import os
import json
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db import models


def _dispatch_cloud_sync(table_name: str, payload: dict, fk_fields: list = None):
    """Safely dispatch entity to Supabase cloud in real-time non-blocking thread."""
    try:
        from app.services.supabase_service import supabase_service
        supabase_service.forward_entity(table_name, payload, fk_fields=fk_fields)
    except Exception:
        pass


# =====================================================================
# 1. EXPERIMENT PROTOCOLS (experiments)
# =====================================================================

def create_experiment(
    db: Session,
    name: str,
    description: Optional[str] = None,
    version: str = "1.0",
    is_active: bool = True
) -> models.Experiment:
    """Create and persist a new Experiment definition."""
    exp = models.Experiment(
        name=name,
        description=description,
        version=version,
        is_active=is_active
    )
    try:
        db.add(exp)
        db.commit()
        db.refresh(exp)
        _dispatch_cloud_sync("experiments", {
            "id": exp.id,
            "name": exp.name,
            "description": exp.description,
            "version": exp.version,
            "is_active": exp.is_active,
            "created_at": exp.created_at
        })
        return exp
    except Exception:
        db.rollback()
        raise


def get_experiment(db: Session, experiment_id: Union[int, str]) -> Optional[models.Experiment]:
    """Retrieve an Experiment by its primary key ID."""
    try:
        exp_id_int = int(experiment_id)
        return db.query(models.Experiment).filter(models.Experiment.id == exp_id_int).first()
    except (ValueError, TypeError):
        return None


def get_experiment_by_name(db: Session, name: str) -> Optional[models.Experiment]:
    """Retrieve an Experiment by its unique name."""
    return db.query(models.Experiment).filter(models.Experiment.name == name).first()


def list_experiments(db: Session, is_active_only: bool = False) -> List[models.Experiment]:
    """List all experiments, optionally filtering for active only."""
    query = db.query(models.Experiment)
    if is_active_only:
        query = query.filter(models.Experiment.is_active == True)  # noqa: E712
    return query.order_by(models.Experiment.created_at.desc()).all()


def update_experiment(db: Session, experiment_id: Union[int, str], **kwargs) -> Optional[models.Experiment]:
    """Update attributes of an existing Experiment."""
    exp = get_experiment(db, experiment_id)
    if not exp:
        return None
    for key, value in kwargs.items():
        if hasattr(exp, key) and value is not None:
            setattr(exp, key, value)
    exp.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(exp)
        _dispatch_cloud_sync("experiments", {
            "id": exp.id,
            "name": exp.name,
            "description": exp.description,
            "version": exp.version,
            "is_active": exp.is_active,
            "updated_at": getattr(exp, "updated_at", None)
        })
        return exp
    except Exception:
        db.rollback()
        raise


def delete_experiment(db: Session, experiment_id: Union[int, str]) -> bool:
    """Delete an experiment and its child cascade entities."""
    exp = get_experiment(db, experiment_id)
    if not exp:
        return False
    try:
        db.delete(exp)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# =====================================================================
# 2. PROTOCOL STEPS (experiment_steps)
# =====================================================================

def create_step(
    db: Session,
    experiment_id: Union[int, str],
    step_number: int,
    step_code: str,
    name: str,
    expected_action: str,
    description: Optional[str] = None,
    required_objects: Optional[Union[List[str], str]] = None,
    confidence_threshold: float = 0.70,
    validation_rules: Optional[Union[Dict[str, Any], str]] = None,
    expected_duration_seconds: Optional[int] = None
) -> models.ExperimentStep:
    """Create and persist an ordered step within an experiment."""
    exp_id_int = int(experiment_id)
    if isinstance(required_objects, list):
        req_objs_str = json.dumps(required_objects)
    elif isinstance(required_objects, str):
        req_objs_str = required_objects
    else:
        req_objs_str = "[]"

    if isinstance(validation_rules, dict):
        val_rules_str = json.dumps(validation_rules)
    else:
        val_rules_str = validation_rules

    step = models.ExperimentStep(
        experiment_id=exp_id_int,
        step_number=step_number,
        step_code=step_code,
        name=name,
        description=description,
        expected_action=expected_action,
        required_objects=req_objs_str,
        confidence_threshold=confidence_threshold,
        validation_rules=val_rules_str,
        expected_duration_seconds=expected_duration_seconds
    )
    try:
        db.add(step)
        db.commit()
        db.refresh(step)
        _dispatch_cloud_sync("experiment_steps", {
            "id": step.id,
            "experiment_id": step.experiment_id,
            "step_number": step.step_number,
            "step_code": step.step_code,
            "name": step.name,
            "description": step.description,
            "expected_action": step.expected_action,
            "required_objects": step.required_objects,
            "confidence_threshold": step.confidence_threshold,
            "validation_rules": step.validation_rules,
            "expected_duration_seconds": step.expected_duration_seconds,
            "created_at": step.created_at
        }, fk_fields=["experiment_id"])
        return step
    except Exception:
        db.rollback()
        raise


def get_step(db: Session, step_id: Union[int, str]) -> Optional[models.ExperimentStep]:
    """Retrieve an ExperimentStep by its primary key ID."""
    try:
        step_id_int = int(step_id)
        return db.query(models.ExperimentStep).filter(models.ExperimentStep.id == step_id_int).first()
    except (ValueError, TypeError):
        return None


def get_steps_for_experiment(db: Session, experiment_id: Union[int, str]) -> List[models.ExperimentStep]:
    """Retrieve all ordered steps for a specific experiment, sorted by step_number ascending."""
    try:
        exp_id_int = int(experiment_id)
        return db.query(models.ExperimentStep).filter(
            models.ExperimentStep.experiment_id == exp_id_int
        ).order_by(models.ExperimentStep.step_number.asc()).all()
    except (ValueError, TypeError):
        return []


def update_step(db: Session, step_id: Union[int, str], **kwargs) -> Optional[models.ExperimentStep]:
    """Update attributes of an existing ExperimentStep."""
    step = get_step(db, step_id)
    if not step:
        return None
    for key, value in kwargs.items():
        if hasattr(step, key) and value is not None:
            if key in ("required_objects", "expected_objects") and isinstance(value, list):
                setattr(step, "required_objects", json.dumps(value))
            elif key == "validation_rules" and isinstance(value, dict):
                setattr(step, "validation_rules", json.dumps(value))
            elif key == "action_code":
                setattr(step, "expected_action", value)
            elif key == "display_name":
                setattr(step, "name", value)
            else:
                setattr(step, key, value)
    try:
        db.commit()
        db.refresh(step)
        _dispatch_cloud_sync("experiment_steps", {
            "id": step.id,
            "experiment_id": step.experiment_id,
            "step_number": step.step_number,
            "step_code": step.step_code,
            "name": step.name,
            "description": step.description,
            "expected_action": step.expected_action,
            "required_objects": step.required_objects,
            "confidence_threshold": step.confidence_threshold,
            "validation_rules": step.validation_rules,
            "expected_duration_seconds": step.expected_duration_seconds,
            "created_at": step.created_at
        }, fk_fields=["experiment_id"])
        return step
    except Exception:
        db.rollback()
        raise


def delete_step(db: Session, step_id: Union[int, str]) -> bool:
    """Delete an individual ExperimentStep."""
    step = get_step(db, step_id)
    if not step:
        return False
    try:
        db.delete(step)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def delete_steps_for_experiment(db: Session, experiment_id: Union[int, str]) -> int:
    """Delete all steps for a given experiment."""
    try:
        exp_id_int = int(experiment_id)
        count = db.query(models.ExperimentStep).filter(
            models.ExperimentStep.experiment_id == exp_id_int
        ).delete()
        db.commit()
        return count
    except (ValueError, TypeError):
        db.rollback()
        return 0


# =====================================================================
# 3. EXPERIMENT SESSIONS (experiment_sessions)
# =====================================================================

def create_session(
    db: Session,
    experiment_id: Union[int, str],
    session_uuid: Optional[str] = None,
    session_code: Optional[str] = None,
    session_name: Optional[str] = None,
    status: str = "CREATED",
    stream_enabled: bool = False,
    current_step_number: Optional[int] = 1,
    current_step_code: Optional[str] = None,
    expected_next_step: Optional[str] = None,
    operator_label: Optional[str] = "Astronaut Specialist",
    notes: Optional[str] = None,
    recording_path: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    **kwargs
) -> models.ExperimentSession:
    """Create and persist a new execution session for an experiment."""
    exp_id_int = int(experiment_id)
    uuid_str = session_uuid or session_code or kwargs.get("code") or models.generate_uuid()
    step_num = current_step_number if current_step_number is not None else kwargs.get("current_step", 1)
    s_name = session_name or kwargs.get("name") or f"Session-{uuid_str[:8]}"

    session = models.ExperimentSession(
        experiment_id=exp_id_int,
        session_uuid=uuid_str,
        session_name=s_name,
        status=status,
        stream_enabled=stream_enabled,
        current_step_number=step_num,
        current_step_code=current_step_code,
        expected_next_step=expected_next_step,
        operator_label=operator_label,
        notes=notes,
        recording_path=recording_path,
        started_at=started_at,
        ended_at=ended_at
    )
    try:
        db.add(session)
        db.commit()
        db.refresh(session)
        _dispatch_cloud_sync("experiment_sessions", {
            "id": session.id,
            "experiment_id": session.experiment_id,
            "session_uuid": session.session_uuid,
            "session_name": session.session_name,
            "status": session.status,
            "stream_enabled": session.stream_enabled,
            "current_step_number": session.current_step_number,
            "current_step_code": session.current_step_code,
            "expected_next_step": session.expected_next_step,
            "operator_label": session.operator_label,
            "notes": session.notes,
            "recording_path": session.recording_path,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "created_at": session.created_at,
            "updated_at": session.updated_at
        }, fk_fields=["experiment_id"])
        return session
    except Exception:
        db.rollback()
        raise


def get_session(db: Session, session_id: Union[int, str]) -> Optional[models.ExperimentSession]:
    """Retrieve an ExperimentSession by its ID or UUID."""
    try:
        sess_id_int = int(session_id)
        sess = db.query(models.ExperimentSession).filter(models.ExperimentSession.id == sess_id_int).first()
        if sess:
            return sess
    except (ValueError, TypeError):
        pass
    return get_session_by_uuid(db, str(session_id))


def get_session_by_uuid(db: Session, session_uuid: str) -> Optional[models.ExperimentSession]:
    """Retrieve an ExperimentSession by its session UUID."""
    return db.query(models.ExperimentSession).filter(
        models.ExperimentSession.session_uuid == session_uuid
    ).first()


def list_sessions(db: Session, limit: int = 100, offset: int = 0) -> List[models.ExperimentSession]:
    """List all experiment execution sessions ordered by creation date."""
    return db.query(models.ExperimentSession).order_by(
        models.ExperimentSession.created_at.desc()
    ).offset(offset).limit(limit).all()


def list_sessions_for_experiment(db: Session, experiment_id: Union[int, str]) -> List[models.ExperimentSession]:
    """List all sessions belonging to an experiment."""
    try:
        exp_id_int = int(experiment_id)
        return db.query(models.ExperimentSession).filter(
            models.ExperimentSession.experiment_id == exp_id_int
        ).order_by(models.ExperimentSession.created_at.desc()).all()
    except (ValueError, TypeError):
        return []


def update_session(db: Session, session_id: Union[int, str], **kwargs) -> Optional[models.ExperimentSession]:
    """Update attributes of an active or completed ExperimentSession."""
    session = get_session(db, session_id)
    if not session:
        return None
    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)
    session.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(session)
        _dispatch_cloud_sync("experiment_sessions", {
            "id": session.id,
            "experiment_id": session.experiment_id,
            "session_uuid": session.session_uuid,
            "session_name": session.session_name,
            "status": session.status,
            "stream_enabled": session.stream_enabled,
            "current_step_number": session.current_step_number,
            "current_step_code": session.current_step_code,
            "expected_next_step": session.expected_next_step,
            "operator_label": session.operator_label,
            "notes": session.notes,
            "recording_path": session.recording_path,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "updated_at": session.updated_at
        }, fk_fields=["experiment_id"])
        return session
    except Exception:
        db.rollback()
        raise


def sync_session_to_cloud(session: models.ExperimentSession):
    """Explicitly synchronize an ExperimentSession's current state to Supabase."""
    if not session:
        return
    _dispatch_cloud_sync("experiment_sessions", {
        "id": session.id,
        "experiment_id": session.experiment_id,
        "session_uuid": session.session_uuid,
        "session_name": session.session_name,
        "status": session.status,
        "stream_enabled": session.stream_enabled,
        "current_step_number": session.current_step_number,
        "current_step_code": session.current_step_code,
        "expected_next_step": session.expected_next_step,
        "operator_label": session.operator_label,
        "notes": session.notes,
        "recording_path": session.recording_path,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "created_at": session.created_at,
        "updated_at": getattr(session, "updated_at", None)
    }, fk_fields=["experiment_id"])


# =====================================================================
# 4. ACTIVITY DETECTIONS (detection_events)
# =====================================================================

def create_detection_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    entity_type: str,
    entity_name: str,
    confidence: Optional[float] = None,
    protocol_step_id: Optional[Union[int, str]] = None,
    frame_number: Optional[int] = None,
    start_time_ms: Optional[float] = None,
    end_time_ms: Optional[float] = None,
    bbox: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    source: Optional[str] = None,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.DetectionEvent:
    """Record an AI perception detection event."""
    sess_id_int = None
    if session_id is not None:
        sess = get_session(db, session_id)
        sess_id_int = sess.id if sess else None

    step_id_int = None
    if protocol_step_id is not None:
        try:
            step_id_int = int(protocol_step_id)
        except (ValueError, TypeError):
            pass

    bbox_str = json.dumps(bbox, default=str) if isinstance(bbox, (dict, list)) else (bbox or "")
    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    event = models.DetectionEvent(
        session_id=sess_id_int,
        protocol_step_id=step_id_int,
        frame_number=frame_number,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        entity_type=entity_type,
        entity_name=entity_name,
        confidence=confidence,
        bbox=bbox_str,
        source=source,
        metadata_json=meta_str
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        _dispatch_cloud_sync("detection_events", {
            "id": event.id,
            "session_id": event.session_id,
            "protocol_step_id": event.protocol_step_id,
            "timestamp": event.timestamp,
            "frame_number": event.frame_number,
            "start_time_ms": event.start_time_ms,
            "end_time_ms": event.end_time_ms,
            "entity_type": event.entity_type,
            "entity_name": event.entity_name,
            "confidence": event.confidence,
            "bbox": event.bbox,
            "source": event.source,
            "metadata": event.metadata_json
        }, fk_fields=["session_id", "protocol_step_id"])
        return event
    except Exception:
        db.rollback()
        raise


def get_session_detection_events(db: Session, session_id: Union[int, str]) -> List[models.DetectionEvent]:
    """Retrieve all detection events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.DetectionEvent).filter(
        models.DetectionEvent.session_id == sess.id
    ).order_by(models.DetectionEvent.timestamp.asc()).all()


# =====================================================================
# 5. VALIDATION EVENTS (sequence_events)
# =====================================================================

def create_sequence_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    result: str,
    event_type: Optional[str] = None,
    protocol_step_id: Optional[Union[int, str]] = None,
    expected_step_number: Optional[int] = None,
    expected_step_code: Optional[str] = None,
    observed_step_number: Optional[int] = None,
    observed_step_code: Optional[str] = None,
    confidence: Optional[float] = None,
    message: Optional[str] = None,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.SequenceEvent:
    """Record a deterministic sequence validation event."""
    sess_id_int = None
    if session_id is not None:
        sess = get_session(db, session_id)
        sess_id_int = sess.id if sess else None

    step_id_int = None
    if protocol_step_id is not None:
        try:
            step_id_int = int(protocol_step_id)
        except (ValueError, TypeError):
            pass

    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")
    e_type = event_type or result

    event = models.SequenceEvent(
        session_id=sess_id_int,
        protocol_step_id=step_id_int,
        event_type=e_type,
        expected_step_number=expected_step_number,
        expected_step_code=expected_step_code,
        observed_step_number=observed_step_number,
        observed_step_code=observed_step_code,
        result=result,
        confidence=confidence,
        message=message,
        metadata_json=meta_str
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        _dispatch_cloud_sync("sequence_events", {
            "id": event.id,
            "session_id": event.session_id,
            "protocol_step_id": event.protocol_step_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "expected_step_number": event.expected_step_number,
            "expected_step_code": event.expected_step_code,
            "observed_step_number": event.observed_step_number,
            "observed_step_code": event.observed_step_code,
            "result": event.result,
            "confidence": event.confidence,
            "message": event.message,
            "metadata": event.metadata_json
        }, fk_fields=["session_id", "protocol_step_id"])
        return event
    except Exception:
        db.rollback()
        raise


def get_session_sequence_events(db: Session, session_id: Union[int, str]) -> List[models.SequenceEvent]:
    """Retrieve all sequence validation events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.SequenceEvent).filter(
        models.SequenceEvent.session_id == sess.id
    ).order_by(models.SequenceEvent.timestamp.asc()).all()


# =====================================================================
# 6. ALERTS (alert_events)
# =====================================================================

def create_alert_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    alert_type: str,
    message: str,
    severity: str = "INFO",
    category: str = "protocol",
    validation_event_id: Optional[int] = None,
    acknowledged: bool = False,
    spoken: bool = False,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.AlertEvent:
    """Record a system or voice alert event."""
    sess_id_int = None
    if session_id is not None:
        sess = get_session(db, session_id)
        sess_id_int = sess.id if sess else None

    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    event = models.AlertEvent(
        session_id=sess_id_int,
        validation_event_id=validation_event_id,
        alert_type=alert_type,
        severity=severity,
        category=category,
        message=message,
        acknowledged=acknowledged,
        spoken=spoken,
        metadata_json=meta_str
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        _dispatch_cloud_sync("alert_events", {
            "id": event.id,
            "session_id": event.session_id,
            "validation_event_id": event.validation_event_id,
            "timestamp": event.timestamp,
            "alert_type": event.alert_type,
            "severity": event.severity,
            "category": event.category,
            "message": event.message,
            "acknowledged": event.acknowledged,
            "acknowledged_at": event.acknowledged_at,
            "spoken": event.spoken,
            "metadata": event.metadata_json
        }, fk_fields=["session_id", "validation_event_id"])
        return event
    except Exception:
        db.rollback()
        raise


def get_session_alert_events(db: Session, session_id: Union[int, str]) -> List[models.AlertEvent]:
    """Retrieve all alert events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.AlertEvent).filter(
        models.AlertEvent.session_id == sess.id
    ).order_by(models.AlertEvent.timestamp.asc()).all()


def acknowledge_alert(db: Session, alert_id: int) -> Optional[models.AlertEvent]:
    """Mark an alert event as acknowledged with timestamp."""
    alert = db.query(models.AlertEvent).filter(models.AlertEvent.id == alert_id).first()
    if alert:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        try:
            db.commit()
            db.refresh(alert)
        except Exception:
            db.rollback()
            raise
    return alert


# =====================================================================
# 7. SESSION ARTIFACTS (session_artifacts)
# =====================================================================

def create_artifact(
    db: Session,
    session_id: Union[int, str],
    artifact_type: str,
    file_path: str,
    file_name: str,
    mime_type: str,
    file_size_bytes: Optional[int] = None,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.SessionArtifact:
    """Record a reference to a session artifact (video file, exported log, report)."""
    sess = get_session(db, session_id)
    if not sess:
        raise ValueError(f"Session with id/uuid '{session_id}' not found.")

    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    # Auto-detect file size if not provided and file exists
    if file_size_bytes is None and os.path.exists(file_path):
        try:
            file_size_bytes = os.path.getsize(file_path)
        except Exception:
            pass

    artifact = models.SessionArtifact(
        session_id=sess.id,
        artifact_type=artifact_type,
        file_path=str(file_path),
        file_name=file_name,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        metadata_json=meta_str
    )
    try:
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        _dispatch_cloud_sync("session_artifacts", {
            "id": artifact.id,
            "session_id": artifact.session_id,
            "artifact_type": artifact.artifact_type,
            "file_path": artifact.file_path,
            "file_name": artifact.file_name,
            "mime_type": artifact.mime_type,
            "file_size_bytes": artifact.file_size_bytes,
            "created_at": artifact.created_at,
            "metadata": artifact.metadata_json
        }, fk_fields=["session_id"])
        return artifact
    except Exception:
        db.rollback()
        raise


def get_artifact(db: Session, artifact_id: int) -> Optional[models.SessionArtifact]:
    """Retrieve an artifact by primary key."""
    return db.query(models.SessionArtifact).filter(models.SessionArtifact.id == artifact_id).first()


def get_session_artifacts(
    db: Session,
    session_id: Union[int, str],
    artifact_type: Optional[str] = None
) -> List[models.SessionArtifact]:
    """Retrieve all artifacts associated with a session, optionally filtered by type."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    query = db.query(models.SessionArtifact).filter(models.SessionArtifact.session_id == sess.id)
    if artifact_type:
        query = query.filter(models.SessionArtifact.artifact_type == artifact_type)
    return query.order_by(models.SessionArtifact.created_at.desc()).all()


def delete_artifact(db: Session, artifact_id: int) -> bool:
    """Delete an artifact reference from the database."""
    artifact = get_artifact(db, artifact_id)
    if not artifact:
        return False
    try:
        db.delete(artifact)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# =====================================================================
# 8. SYSTEM SETTINGS (system_settings)
# =====================================================================

def get_setting(db: Session, key: str, default: Any = None) -> Any:
    """Retrieve a persistent setting value by its key."""
    record = db.query(models.SystemSetting).filter(models.SystemSetting.setting_key == key).first()
    if not record:
        return default
    try:
        return json.loads(record.setting_value)
    except Exception:
        return record.setting_value


def set_setting(db: Session, key: str, value: Any) -> models.SystemSetting:
    """Set or update a persistent setting value."""
    val_str = json.dumps(value) if not isinstance(value, str) else value
    record = db.query(models.SystemSetting).filter(models.SystemSetting.setting_key == key).first()
    if record:
        record.setting_value = val_str
        record.updated_at = datetime.now(timezone.utc)
    else:
        record = models.SystemSetting(
            setting_key=key,
            setting_value=val_str
        )
        db.add(record)
    try:
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        raise


def get_all_settings(db: Session) -> Dict[str, Any]:
    """Retrieve all stored settings as a dictionary."""
    records = db.query(models.SystemSetting).all()
    result = {}
    for r in records:
        try:
            result[r.setting_key] = json.loads(r.setting_value)
        except Exception:
            result[r.setting_key] = r.setting_value
    return result


def delete_setting(db: Session, key: str) -> bool:
    """Delete a setting by key."""
    record = db.query(models.SystemSetting).filter(models.SystemSetting.setting_key == key).first()
    if not record:
        return False
    try:
        db.delete(record)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# =====================================================================
# 9. SYSTEM EVENTS (system_events)
# =====================================================================

def create_system_event(
    db: Session,
    event_type: str,
    message: str,
    severity: str = "INFO",
    component: Optional[str] = None,
    session_id: Optional[Union[int, str]] = None,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.SystemEvent:
    """Record a system lifecycle, model diagnostic, or general system event."""
    sess_id_int = None
    if session_id is not None:
        sess = get_session(db, session_id)
        sess_id_int = sess.id if sess else None

    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    event = models.SystemEvent(
        session_id=sess_id_int,
        event_type=event_type,
        severity=severity,
        message=message,
        component=component,
        metadata_json=meta_str
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        _dispatch_cloud_sync("system_events", {
            "id": event.id,
            "session_id": event.session_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
            "component": event.component,
            "metadata": event.metadata_json
        }, fk_fields=["session_id"])
        return event
    except Exception:
        db.rollback()
        raise


def get_session_system_events(db: Session, session_id: Union[int, str]) -> List[models.SystemEvent]:
    """Retrieve all system lifecycle events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.SystemEvent).filter(
        models.SystemEvent.session_id == sess.id
    ).order_by(models.SystemEvent.timestamp.asc()).all()


def get_system_events(db: Session, limit: int = 100) -> List[models.SystemEvent]:
    """Retrieve recent system events."""
    return db.query(models.SystemEvent).order_by(
        models.SystemEvent.timestamp.desc()
    ).limit(limit).all()


# =====================================================================
# CLASS REPOSITORY WRAPPERS
# =====================================================================

class ExperimentRepository:
    get_all = staticmethod(list_experiments)
    get_by_id = staticmethod(get_experiment)
    get_by_name = staticmethod(get_experiment_by_name)
    create = staticmethod(create_experiment)
    update = staticmethod(update_experiment)
    delete = staticmethod(delete_experiment)

    @staticmethod
    def add_step(
        db: Session,
        experiment_id: Union[int, str],
        step_number: int,
        action_code: str,
        display_name: str,
        description: Optional[str] = None,
        expected_objects: Optional[List[str]] = None,
        required: bool = True,
        confidence_threshold: float = 0.70,
        step_code: Optional[str] = None,
        validation_rules: Optional[Dict[str, Any]] = None,
        expected_duration_seconds: Optional[int] = None
    ) -> models.ExperimentStep:
        code = step_code or f"STEP_{step_number:02d}"
        return create_step(
            db=db,
            experiment_id=experiment_id,
            step_number=step_number,
            step_code=code,
            name=display_name,
            expected_action=action_code,
            description=description,
            required_objects=expected_objects,
            confidence_threshold=confidence_threshold,
            validation_rules=validation_rules,
            expected_duration_seconds=expected_duration_seconds
        )

    get_step = staticmethod(get_step)
    get_steps = staticmethod(get_steps_for_experiment)
    update_step = staticmethod(update_step)
    delete_step = staticmethod(delete_step)


# Alias
ProtocolRepository = ExperimentRepository


class SessionRepository:
    create = staticmethod(create_session)
    create_session = staticmethod(create_session)
    get_all = staticmethod(list_sessions)
    get_by_id = staticmethod(get_session)
    get_by_code = staticmethod(get_session_by_uuid)
    get_by_uuid = staticmethod(get_session_by_uuid)
    list_for_experiment = staticmethod(list_sessions_for_experiment)

    @staticmethod
    def update_status(
        db: Session,
        session_id: Union[int, str],
        status: str,
        current_step: Optional[int] = None,
        recording_path: Optional[str] = None,
        log_path: Optional[str] = None,
        ended_at: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> Optional[models.ExperimentSession]:
        kwargs: Dict[str, Any] = {"status": status}
        if current_step is not None:
            kwargs["current_step_number"] = current_step
        if recording_path is not None:
            kwargs["recording_path"] = recording_path
        if ended_at is not None:
            kwargs["ended_at"] = ended_at
        if notes is not None:
            kwargs["notes"] = notes
        return update_session(db, session_id, **kwargs)


class EventRepository:
    @staticmethod
    def record_detection(
        db: Session,
        session_id: Optional[Union[int, str]],
        event_type: Optional[str] = "ACTIVITY_RECOGNITION",
        confidence: float = 0.0,
        action_code: Optional[str] = None,
        object_name: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        start_time_ms: Optional[float] = None,
        end_time_ms: Optional[float] = None,
        protocol_step_id: Optional[int] = None,
        bbox: Optional[Any] = None,
        source: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_name: Optional[str] = None,
        **kwargs
    ) -> models.DetectionEvent:
        e_type = entity_type or event_type or "ACTION"
        e_name = entity_name or action_code or object_name or "unknown"
        return create_detection_event(
            db=db,
            session_id=session_id,
            entity_type=e_type,
            entity_name=e_name,
            confidence=confidence,
            protocol_step_id=protocol_step_id,
            frame_number=frame_number,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            bbox=bbox,
            source=source,
            metadata=metadata_json
        )

    @staticmethod
    def record_sequence(
        db: Session,
        session_id: Optional[Union[int, str]],
        expected_step: Optional[int],
        observed_step: Optional[int],
        result: str,
        reason: Optional[str] = None,
        expected_step_code: Optional[str] = None,
        observed_step_code: Optional[str] = None,
        confidence: Optional[float] = None,
        event_type: Optional[str] = None,
        protocol_step_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.SequenceEvent:
        return create_sequence_event(
            db=db,
            session_id=session_id,
            result=result,
            event_type=event_type,
            protocol_step_id=protocol_step_id,
            expected_step_number=expected_step,
            expected_step_code=expected_step_code,
            observed_step_number=observed_step,
            observed_step_code=observed_step_code,
            confidence=confidence,
            message=reason,
            metadata=metadata
        )

    @staticmethod
    def record_alert(
        db: Session,
        session_id: Optional[Union[int, str]],
        alert_type: str,
        severity: str,
        message: str,
        category: str = "protocol",
        validation_event_id: Optional[int] = None,
        spoken: bool = False,
        acknowledged: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.AlertEvent:
        return create_alert_event(
            db=db,
            session_id=session_id,
            alert_type=alert_type,
            severity=severity,
            category=category,
            validation_event_id=validation_event_id,
            message=message,
            spoken=spoken,
            acknowledged=acknowledged,
            metadata=metadata
        )

    @staticmethod
    def record_system_event(
        db: Session,
        event_type: str,
        message: str,
        severity: str = "INFO",
        component: Optional[str] = None,
        session_id: Optional[Union[int, str]] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> models.SystemEvent:
        return create_system_event(
            db=db,
            event_type=event_type,
            message=message,
            severity=severity,
            component=component,
            session_id=session_id,
            metadata=metadata_json
        )

    get_session_events = staticmethod(get_session_sequence_events)
    get_session_sequence = staticmethod(get_session_sequence_events)
    get_session_alerts = staticmethod(get_session_alert_events)
    get_session_detections = staticmethod(get_session_detection_events)
    get_session_system_events = staticmethod(get_session_system_events)
    get_system_events = staticmethod(get_system_events)


class ArtifactRepository:
    create = staticmethod(create_artifact)
    get_by_id = staticmethod(get_artifact)
    get_for_session = staticmethod(get_session_artifacts)
    delete = staticmethod(delete_artifact)


class SettingRepository:
    get = staticmethod(get_setting)
    set = staticmethod(set_setting)
    get_all = staticmethod(get_all_settings)
    delete = staticmethod(delete_setting)
