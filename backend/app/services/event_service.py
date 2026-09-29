"""
Event Service for AURAVISION Offline System
Centralizes event persistence, timeline aggregation, filtering, and retrieval for sessions.
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db import models
from app.db.repository import (
    EventRepository,
    SessionRepository,
    create_detection_event,
    create_sequence_event,
    create_alert_event,
    create_system_event,
    get_session_detection_events,
    get_session_sequence_events,
    get_session_alert_events,
    get_session_system_events,
)
from app.schemas.event import (
    TimelineEvent,
    SessionTimelineResponse,
    DetectionEventResponse,
    SequenceEventResponse,
    AlertEventResponse,
    SystemEventResponse,
)
from app.core.constants import AlertSeverity, EventType
from app.core.logging import logger


class EventService:
    """
    Centralized Event Manager for recording and aggregating all session events:
    - Perception & Object Detections (DetectionEvent)
    - Sequence Validation Outcomes (SequenceEvent)
    - Alerts and Deviations (AlertEvent)
    - System Lifecycle & State Transitions (SystemEvent)
    """

    @staticmethod
    def record_detection_event(
        db: Session,
        session_id: Optional[Union[int, str]],
        entity_type: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_name: Optional[str] = None,
        action_code: Optional[str] = None,
        object_name: Optional[str] = None,
        confidence: Optional[float] = None,
        frame_number: Optional[int] = None,
        start_time_ms: Optional[float] = None,
        end_time_ms: Optional[float] = None,
        protocol_step_id: Optional[int] = None,
        bbox: Optional[Any] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> models.DetectionEvent:
        """Record an entity detection event in the database."""
        if session_id is not None:
            sess = SessionRepository.get_by_id(db, session_id)
            if not sess:
                raise ValueError(f"Session '{session_id}' not found.")

        e_type = entity_type or event_type or "action"
        e_name = entity_name or action_code or object_name or "unknown"
        return EventRepository.record_detection(
            db=db,
            session_id=session_id,
            event_type=e_type,
            action_code=e_name,
            object_name=e_name,
            confidence=confidence or 0.0,
            frame_number=frame_number,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            protocol_step_id=protocol_step_id,
            bbox=bbox,
            source=source,
            metadata_json=metadata
        )

    @staticmethod
    def record_sequence_event(
        db: Session,
        session_id: Optional[Union[int, str]],
        result: str = "VALID",
        event_type: Optional[str] = None,
        protocol_step_id: Optional[int] = None,
        expected_step: Optional[int] = None,
        expected_step_number: Optional[int] = None,
        expected_step_code: Optional[str] = None,
        observed_step: Optional[int] = None,
        observed_step_number: Optional[int] = None,
        observed_step_code: Optional[str] = None,
        confidence: Optional[float] = None,
        message: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> models.SequenceEvent:
        """Record a deterministic sequence validation outcome in the database."""
        if session_id is not None:
            sess = SessionRepository.get_by_id(db, session_id)
            if not sess:
                raise ValueError(f"Session '{session_id}' not found.")

        exp_step = expected_step_number if expected_step_number is not None else expected_step
        obs_step = observed_step_number if observed_step_number is not None else observed_step
        msg = message or reason or f"Step validation: {result}"

        return EventRepository.record_sequence(
            db=db,
            session_id=session_id,
            expected_step=exp_step,
            observed_step=obs_step,
            result=result,
            event_type=event_type,
            protocol_step_id=protocol_step_id,
            reason=msg,
            expected_step_code=expected_step_code,
            observed_step_code=observed_step_code,
            confidence=confidence,
            metadata=metadata
        )

    @staticmethod
    def record_alert_event(
        db: Session,
        session_id: Optional[Union[int, str]],
        alert_type: str,
        message: str,
        severity: str = AlertSeverity.INFO.value,
        category: str = "protocol",
        validation_event_id: Optional[int] = None,
        spoken: bool = False,
        acknowledged: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.AlertEvent:
        """Record an alert event in the database."""
        if session_id is not None:
            sess = SessionRepository.get_by_id(db, session_id)
            if not sess:
                raise ValueError(f"Session '{session_id}' not found.")

        return EventRepository.record_alert(
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
        severity: str = AlertSeverity.INFO.value,
        component: Optional[str] = "session",
        session_id: Optional[Union[int, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> models.SystemEvent:
        """Record a system lifecycle or session state transition event."""
        if session_id is not None:
            sess = SessionRepository.get_by_id(db, session_id)
            if not sess:
                raise ValueError(f"Session '{session_id}' not found.")

        return EventRepository.record_system_event(
            db=db,
            event_type=event_type,
            message=message,
            severity=severity,
            component=component,
            session_id=session_id,
            metadata_json=metadata
        )

    # Specific query helpers & Aliases
    @staticmethod
    def get_session_sequence_events(
        db: Session,
        session_id: Union[int, str],
        limit: Optional[int] = None
    ) -> List[models.SequenceEvent]:
        """Retrieve sequence events for a specific session."""
        sess = SessionRepository.get_by_id(db, session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")
        events = get_session_sequence_events(db, sess.id)
        if limit is not None and limit > 0:
            events = events[:limit]
        return events

    get_sequence_events = get_session_sequence_events

    @staticmethod
    def get_session_alert_events(
        db: Session,
        session_id: Union[int, str],
        limit: Optional[int] = None
    ) -> List[models.AlertEvent]:
        """Retrieve alert events for a specific session."""
        sess = SessionRepository.get_by_id(db, session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")
        events = get_session_alert_events(db, sess.id)
        if limit is not None and limit > 0:
            events = events[:limit]
        return events

    get_alerts = get_session_alert_events

    @staticmethod
    def get_session_detection_events(
        db: Session,
        session_id: Union[int, str],
        limit: Optional[int] = None
    ) -> List[models.DetectionEvent]:
        """Retrieve detection events for a specific session."""
        sess = SessionRepository.get_by_id(db, session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")
        events = get_session_detection_events(db, sess.id)
        if limit is not None and limit > 0:
            events = events[:limit]
        return events

    get_detection_events = get_session_detection_events

    @staticmethod
    def get_session_system_events(
        db: Session,
        session_id: Union[int, str],
        limit: Optional[int] = None
    ) -> List[models.SystemEvent]:
        """Retrieve system lifecycle events for a specific session."""
        sess = SessionRepository.get_by_id(db, session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")
        events = get_session_system_events(db, sess.id)
        if limit is not None and limit > 0:
            events = events[:limit]
        return events

    get_system_events = get_session_system_events

    @classmethod
    def get_session_timeline(
        cls,
        db: Session,
        session_id: Union[int, str],
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> SessionTimelineResponse:
        """
        Aggregate all event types into a unified, chronological timeline:
        - SystemEvents (type="SYSTEM")
        - SequenceEvents (type="SEQUENCE")
        - AlertEvents (type="ALERT")
        - DetectionEvents (type="DETECTION")
        Sorted oldest -> newest.
        """
        sess = SessionRepository.get_by_id(db, session_id)
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")

        timeline_items: List[TimelineEvent] = []

        # 1. System Events
        for se in get_session_system_events(db, sess.id):
            timeline_items.append(TimelineEvent(
                timestamp=se.timestamp,
                type="SYSTEM",
                event_type=se.event_type,
                severity=se.severity or "INFO",
                message=se.message or "",
                component=se.component,
                category="system",
                data={"id": se.id, "component": se.component},
                details={"id": se.id, "component": se.component}
            ))

        # 2. Sequence Events
        for sq in get_session_sequence_events(db, sess.id):
            severity = "INFO" if sq.result in ("VALID", "EXPERIMENT_COMPLETE") else "WARNING"
            sq_data = {
                "id": sq.id,
                "expected_step_number": sq.expected_step_number,
                "expected_step_code": sq.expected_step_code,
                "observed_step_number": sq.observed_step_number,
                "observed_step_code": sq.observed_step_code,
                "confidence": sq.confidence
            }
            timeline_items.append(TimelineEvent(
                timestamp=sq.timestamp,
                type="SEQUENCE",
                event_type=sq.result,
                severity=severity,
                message=sq.message or f"Step validation: {sq.result}",
                category="sequence",
                data=sq_data,
                details=sq_data
            ))

        # 3. Alert Events
        for al in get_session_alert_events(db, sess.id):
            al_data = {
                "id": al.id,
                "alert_type": al.alert_type,
                "severity": al.severity,
                "acknowledged": al.acknowledged,
                "spoken": al.spoken
            }
            timeline_items.append(TimelineEvent(
                timestamp=al.timestamp,
                type="ALERT",
                event_type=al.alert_type,
                severity=al.severity or "INFO",
                message=al.message or "",
                category="alert",
                data=al_data,
                details=al_data
            ))

        # 4. Detection Events
        for de in get_session_detection_events(db, sess.id):
            de_data = {
                "id": de.id,
                "entity_type": de.entity_type,
                "entity_name": de.entity_name,
                "action_code": de.entity_name if de.entity_type == "action" else None,
                "confidence": de.confidence,
                "source": de.source
            }
            timeline_items.append(TimelineEvent(
                timestamp=de.timestamp,
                type="DETECTION",
                event_type=de.entity_type,
                severity="INFO",
                message=f"Detected {de.entity_type} '{de.entity_name}' (conf: {de.confidence or 0.0:.2f})",
                category="detection",
                data=de_data,
                details=de_data
            ))

        # Helper for naive comparison
        def _to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        # Sort chronologically: Oldest -> Newest
        timeline_items.sort(key=lambda item: _to_naive_utc(item.timestamp) or datetime.min)

        filtered = timeline_items

        if event_type:
            et_lower = event_type.lower().strip()
            filtered = [
                item for item in filtered
                if (item.type and item.type.lower() == et_lower)
                or (item.event_type and item.event_type.lower() == et_lower)
                or (item.category and item.category.lower() == et_lower)
            ]

        norm_start = _to_naive_utc(start_time)
        if norm_start:
            filtered = [item for item in filtered if (_to_naive_utc(item.timestamp) or datetime.min) >= norm_start]

        norm_end = _to_naive_utc(end_time)
        if norm_end:
            filtered = [item for item in filtered if (_to_naive_utc(item.timestamp) or datetime.min) <= norm_end]

        if limit is not None and limit > 0:
            filtered = filtered[:limit]

        return SessionTimelineResponse(
            session_id=sess.id,
            session_uuid=sess.session_uuid,
            total_events=len(filtered),
            events=filtered
        )


event_service = EventService()

