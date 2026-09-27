"""
Database Repository Layer for AURAVISION
Provides clean, reusable persistence functions and repositories without embedded business logic.
"""
import json
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db import models


# =====================================================================
# EXPERIMENTS
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
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


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
    db.commit()
    db.refresh(exp)
    return exp


def delete_experiment(db: Session, experiment_id: Union[int, str]) -> bool:
    """Delete an experiment and its child cascade entities."""
    exp = get_experiment(db, experiment_id)
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True


# =====================================================================
# EXPERIMENT STEPS
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
    confidence_threshold: float = 0.70
) -> models.ExperimentStep:
    """Create and persist an ordered step within an experiment."""
    exp_id_int = int(experiment_id)
    if isinstance(required_objects, list):
        req_objs_str = json.dumps(required_objects)
    elif isinstance(required_objects, str):
        req_objs_str = required_objects
    else:
        req_objs_str = "[]"

    step = models.ExperimentStep(
        experiment_id=exp_id_int,
        step_number=step_number,
        step_code=step_code,
        name=name,
        description=description,
        expected_action=expected_action,
        required_objects=req_objs_str,
        confidence_threshold=confidence_threshold
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


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
            elif key == "action_code":
                setattr(step, "expected_action", value)
            elif key == "display_name":
                setattr(step, "name", value)
            else:
                setattr(step, key, value)
    db.commit()
    db.refresh(step)
    return step


def delete_step(db: Session, step_id: Union[int, str]) -> bool:
    """Delete an individual ExperimentStep."""
    step = get_step(db, step_id)
    if not step:
        return False
    db.delete(step)
    db.commit()
    return True


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
        return 0


# =====================================================================
# EXPERIMENT SESSIONS
# =====================================================================

def create_session(
    db: Session,
    experiment_id: Union[int, str],
    session_uuid: Optional[str] = None,
    session_code: Optional[str] = None,
    status: str = "CREATED",
    stream_enabled: bool = False,
    current_step_number: Optional[int] = 1,
    current_step_code: Optional[str] = None,
    expected_next_step: Optional[str] = None,
    recording_path: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    **kwargs
) -> models.ExperimentSession:
    """Create and persist a new execution session for an experiment."""
    exp_id_int = int(experiment_id)
    uuid_str = session_uuid or session_code or kwargs.get("code") or models.generate_uuid()
    step_num = current_step_number if current_step_number is not None else kwargs.get("current_step", 1)
    session = models.ExperimentSession(
        experiment_id=exp_id_int,
        session_uuid=uuid_str,
        status=status,
        stream_enabled=stream_enabled,
        current_step_number=step_num,
        current_step_code=current_step_code,
        expected_next_step=expected_next_step,
        recording_path=recording_path,
        started_at=started_at,
        ended_at=ended_at
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session



def get_session(db: Session, session_id: Union[int, str]) -> Optional[models.ExperimentSession]:
    """Retrieve an ExperimentSession by its ID or UUID."""
    # Try as integer ID first
    try:
        sess_id_int = int(session_id)
        sess = db.query(models.ExperimentSession).filter(models.ExperimentSession.id == sess_id_int).first()
        if sess:
            return sess
    except (ValueError, TypeError):
        pass
    # Fallback to lookup by UUID
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
    db.commit()
    db.refresh(session)
    return session



# =====================================================================
# EVENTS (Detection, Sequence, Alert, System)
# =====================================================================

def create_detection_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    entity_type: str,
    entity_name: str,
    confidence: Optional[float] = None,
    frame_number: Optional[int] = None,
    bbox: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    source: Optional[str] = None,
    metadata: Optional[Union[Dict[str, Any], str]] = None
) -> models.DetectionEvent:
    """Record an AI perception detection event."""
    sess_id_int = None
    if session_id is not None:
        sess = get_session(db, session_id)
        sess_id_int = sess.id if sess else None

    bbox_str = json.dumps(bbox, default=str) if isinstance(bbox, (dict, list)) else (bbox or "")
    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    event = models.DetectionEvent(
        session_id=sess_id_int,
        frame_number=frame_number,
        entity_type=entity_type,
        entity_name=entity_name,
        confidence=confidence,
        bbox=bbox_str,
        source=source,
        metadata_json=meta_str
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_sequence_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    result: str,
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

    meta_str = json.dumps(metadata, default=str) if isinstance(metadata, dict) else (metadata or "{}")

    event = models.SequenceEvent(
        session_id=sess_id_int,
        expected_step_number=expected_step_number,
        expected_step_code=expected_step_code,
        observed_step_number=observed_step_number,
        observed_step_code=observed_step_code,
        result=result,
        confidence=confidence,
        message=message,
        metadata_json=meta_str
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_alert_event(
    db: Session,
    session_id: Optional[Union[int, str]],
    alert_type: str,
    message: str,
    severity: str = "INFO",
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
        alert_type=alert_type,
        severity=severity,
        message=message,
        acknowledged=acknowledged,
        spoken=spoken,
        metadata_json=meta_str
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


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
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# Query helpers for events
def get_session_detection_events(db: Session, session_id: Union[int, str]) -> List[models.DetectionEvent]:
    """Retrieve all detection events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.DetectionEvent).filter(
        models.DetectionEvent.session_id == sess.id
    ).order_by(models.DetectionEvent.timestamp.asc()).all()


def get_session_sequence_events(db: Session, session_id: Union[int, str]) -> List[models.SequenceEvent]:
    """Retrieve all sequence validation events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.SequenceEvent).filter(
        models.SequenceEvent.session_id == sess.id
    ).order_by(models.SequenceEvent.timestamp.asc()).all()


def get_session_alert_events(db: Session, session_id: Union[int, str]) -> List[models.AlertEvent]:
    """Retrieve all alert events for a given session."""
    sess = get_session(db, session_id)
    if not sess:
        return []
    return db.query(models.AlertEvent).filter(
        models.AlertEvent.session_id == sess.id
    ).order_by(models.AlertEvent.timestamp.asc()).all()


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
# REPOSITORY CLASS WRAPPERS (For backwards compatibility and grouping)
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
        step_code: Optional[str] = None
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
            confidence_threshold=confidence_threshold
        )

    get_step = staticmethod(get_step)
    get_steps = staticmethod(get_steps_for_experiment)
    update_step = staticmethod(update_step)
    delete_step = staticmethod(delete_step)


class SessionRepository:
    create = staticmethod(create_session)
    create_session = staticmethod(create_session)
    get_all = staticmethod(list_sessions)
    get_by_id = staticmethod(get_session)
    get_by_code = staticmethod(get_session_by_uuid)
    list_for_experiment = staticmethod(list_sessions_for_experiment)

    @staticmethod
    def update_status(
        db: Session,
        session_id: Union[int, str],
        status: str,
        current_step: Optional[int] = None,
        recording_path: Optional[str] = None,
        log_path: Optional[str] = None,
        ended_at: Optional[datetime] = None
    ) -> Optional[models.ExperimentSession]:
        kwargs: Dict[str, Any] = {"status": status}
        if current_step is not None:
            kwargs["current_step_number"] = current_step
        if recording_path is not None:
            kwargs["recording_path"] = recording_path
        if ended_at is not None:
            kwargs["ended_at"] = ended_at
        return update_session(db, session_id, **kwargs)


class EventRepository:
    @staticmethod
    def record_detection(
        db: Session,
        session_id: Optional[Union[int, str]],
        event_type: str,
        confidence: float,
        action_code: Optional[str] = None,
        object_name: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        frame_number: Optional[int] = None,
        bbox: Optional[Any] = None,
        source: Optional[str] = None
    ) -> models.DetectionEvent:
        entity_name = action_code or object_name or "unknown"
        return create_detection_event(
            db=db,
            session_id=session_id,
            entity_type=event_type,
            entity_name=entity_name,
            confidence=confidence,
            frame_number=frame_number,
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
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.SequenceEvent:
        return create_sequence_event(
            db=db,
            session_id=session_id,
            result=result,
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
        spoken: bool = False,
        acknowledged: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.AlertEvent:
        return create_alert_event(
            db=db,
            session_id=session_id,
            alert_type=alert_type,
            severity=severity,
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
    get_session_alerts = staticmethod(get_session_alert_events)
    get_session_detections = staticmethod(get_session_detection_events)
    get_session_system_events = staticmethod(get_session_system_events)
    get_system_events = staticmethod(get_system_events)

