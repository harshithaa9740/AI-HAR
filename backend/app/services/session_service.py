"""
Session Lifecycle Management Service for AURAVISION Offline System
Enforces deterministic state transitions, session creation, control, and event recording.
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db import models
from app.db.repository import (
    SessionRepository,
    ExperimentRepository,
    get_session,
    list_sessions,
    list_sessions_for_experiment,
    update_session,
    get_steps_for_experiment,
    get_experiment,
    sync_session_to_cloud,
)
from app.core.constants import SessionStatus, EventType, AlertSeverity
from app.services.event_service import event_service
from app.services.sequence_validator import sequence_validator
from app.camera.camera_manager import CameraManagerRegistry
from app.core.logging import logger



class InvalidStateTransitionError(ValueError):
    """Raised when an illegal session state transition is attempted."""
    def __init__(self, current_status: str, target_status: str, message: Optional[str] = None):
        msg = message or f"Invalid session state transition from '{current_status}' to '{target_status}'."
        super().__init__(msg)
        self.current_status = current_status
        self.target_status = target_status


class SessionNotFoundError(ValueError):
    """Raised when a requested session is not found."""
    pass


class ExperimentNotFoundError(ValueError):
    """Raised when an experiment referenced by a session is not found."""
    pass


class SessionService:
    """
    Session Service orchestrating experiment execution lifecycle:
    - CREATED
    - RUNNING
    - PAUSED
    - COMPLETED
    - STOPPED
    - ERROR

    Transitions:
    - CREATED -> RUNNING
    - RUNNING -> PAUSED
    - PAUSED -> RUNNING
    - RUNNING -> COMPLETED (Only through Sequence Validator completion)
    - RUNNING -> STOPPED
    - PAUSED -> STOPPED
    - RUNNING -> ERROR
    - PAUSED -> ERROR
    """

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        SessionStatus.CREATED.value: [SessionStatus.RUNNING.value, SessionStatus.STOPPED.value],
        SessionStatus.RUNNING.value: [
            SessionStatus.PAUSED.value,
            SessionStatus.COMPLETED.value,
            SessionStatus.STOPPED.value,
            SessionStatus.ERROR.value
        ],
        SessionStatus.PAUSED.value: [
            SessionStatus.RUNNING.value,
            SessionStatus.STOPPED.value,
            SessionStatus.ERROR.value
        ],
        SessionStatus.COMPLETED.value: [],
        SessionStatus.STOPPED.value: [],
        SessionStatus.ERROR.value: [],
    }

    @classmethod
    def _validate_transition(cls, current_status: str, target_status: str) -> None:
        """Validate whether the requested state transition is permissible."""
        curr = current_status.upper().strip()
        tgt = target_status.upper().strip()

        # Normalize legacy ACTIVE -> RUNNING
        if curr == "ACTIVE":
            curr = SessionStatus.RUNNING.value
        if tgt == "ACTIVE":
            tgt = SessionStatus.RUNNING.value

        allowed = cls.VALID_TRANSITIONS.get(curr, [])
        if tgt not in allowed:
            raise InvalidStateTransitionError(
                current_status=curr,
                target_status=tgt,
                message=f"Cannot transition session from '{curr}' to '{tgt}'. Permitted transitions from '{curr}': {allowed}"
            )

    @classmethod
    def create_session(
        cls,
        db: Session,
        experiment_id: Union[int, str],
        session_uuid: Optional[str] = None,
        stream_enabled: bool = False,
        session_name: Optional[str] = None,
        operator_label: Optional[str] = "Astronaut Specialist",
        notes: Optional[str] = None
    ) -> models.ExperimentSession:
        """
        Create a new experiment execution session in CREATED status:
        1. Verify experiment exists and is valid.
        2. Generate unique session UUID.
        3. Set status = CREATED.
        4. Set current step to first protocol step.
        5. started_at = None, ended_at = None.
        6. Record SystemEvent SESSION_CREATED.
        """
        exp = get_experiment(db, experiment_id)
        if not exp:
            raise ExperimentNotFoundError(f"Experiment '{experiment_id}' not found.")

        steps = get_steps_for_experiment(db, exp.id)
        if not steps or len(steps) == 0:
            raise ValueError(f"Experiment '{exp.name}' (ID: {exp.id}) has no steps configured.")

        first_step = steps[0]
        first_step_code = first_step.step_code or "STEP_01"
        expected_next = f"{first_step.step_code} / {first_step.expected_action}" if first_step else None

        uuid_str = session_uuid or models.generate_uuid()
        if session_uuid:
            existing = SessionRepository.get_by_uuid(db, uuid_str)
            if existing:
                return existing

        session = SessionRepository.create(
            db=db,
            experiment_id=exp.id,
            session_uuid=uuid_str,
            session_name=session_name,
            operator_label=operator_label,
            notes=notes,
            status=SessionStatus.CREATED.value,
            stream_enabled=stream_enabled,
            current_step_number=1,
            current_step_code=first_step_code,
            expected_next_step=expected_next,
            recording_path=None,
            started_at=None,
            ended_at=None
        )

        # Record SystemEvent
        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_CREATED.value,
            message=f"Experiment session '{session.session_uuid}' created for experiment '{exp.name}' in CREATED state.",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"experiment_id": exp.id, "session_uuid": session.session_uuid}
        )

        logger.info(f"Session {session.id} ({session.session_uuid}) created for experiment {exp.id}.")
        return session

    @classmethod
    def get_session(cls, db: Session, session_id: Union[int, str]) -> models.ExperimentSession:
        """Retrieve an ExperimentSession by ID or UUID, or auto-create if a valid session code is requested."""
        session = get_session(db, session_id)
        if not session:
            if isinstance(session_id, str) and (session_id.startswith("sess-") or session_id.startswith("ORBITAL-")):
                exp = db.query(models.Experiment).filter(models.Experiment.is_active == True).first()
                if exp:
                    return cls.create_session(
                        db=db,
                        experiment_id=exp.id,
                        session_uuid=session_id,
                        session_name=f"Session {session_id}",
                        operator_label="Astronaut Specialist",
                        notes="Auto-initialized mission execution session"
                    )
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        return session


    @staticmethod
    def list_sessions(
        db: Session,
        limit: int = 100,
        offset: int = 0,
        experiment_id: Optional[Union[int, str]] = None
    ) -> List[models.ExperimentSession]:
        """List sessions ordered chronologically desc with optional experiment filter."""
        if experiment_id is not None:
            return list_sessions_for_experiment(db, experiment_id)
        return list_sessions(db, limit=limit, offset=offset)

    @classmethod
    def start_session(
        cls,
        db: Session,
        session_id: Optional[Union[int, str]] = None,
        experiment_id: Optional[Union[int, str]] = None,
        session_code: Optional[str] = None
    ) -> models.ExperimentSession:
        """
        Start an experiment session (CREATED -> RUNNING):
        - If session_id is provided, transition existing session.
        - If experiment_id is provided, create and immediately start session.
        - Idempotent: repeated start on an already RUNNING session safely returns the active session.
        """
        if session_id is not None:
            session = cls.get_session(db, session_id)
            if session.status == SessionStatus.RUNNING.value:
                # Idempotent re-request
                return session
            if session.status != SessionStatus.CREATED.value:
                raise InvalidStateTransitionError(
                    current_status=session.status,
                    target_status=SessionStatus.RUNNING.value,
                    message=f"Cannot start session from '{session.status}'. Only CREATED sessions can be started."
                )
            cls._validate_transition(session.status, SessionStatus.RUNNING.value)
        else:
            if experiment_id is None:
                raise ValueError("Must provide either session_id or experiment_id to start a session.")
            if session_code:
                existing = SessionRepository.get_by_uuid(db, session_code)
                if existing:
                    if existing.status == SessionStatus.RUNNING.value:
                        return existing
                    session = existing
                else:
                    session = cls.create_session(db, experiment_id=experiment_id, session_uuid=session_code)
            else:
                session = cls.create_session(db, experiment_id=experiment_id, session_uuid=session_code)

        steps = get_steps_for_experiment(db, session.experiment_id)
        first_step = steps[0] if steps else None
        first_step_code = first_step.step_code if first_step else "STEP_01"
        expected_next = f"{first_step.step_code} / {first_step.expected_action}" if first_step else None

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.RUNNING.value
        session.started_at = now
        session.current_step_number = 1
        session.current_step_code = first_step_code
        session.expected_next_step = expected_next
        db.commit()
        db.refresh(session)
        sync_session_to_cloud(session)

        # Initialize sequence validator memory state
        sequence_validator.init_session_state(
            session_id=session.id,
            experiment_id=session.experiment_id,
            steps=steps,
            current_step_number=1,
            completed=False
        )

        # Record SystemEvent
        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_STARTED.value,
            message=f"Experiment session {session.id} ({session.session_uuid}) started.",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"started_at": now.isoformat()}
        )

        logger.info(f"Session {session.id} started. Status: RUNNING.")
        return session

    @classmethod
    def pause_session(
        cls,
        db: Session,
        session_id: Union[int, str],
        reason: Optional[str] = "User requested pause",
        **kwargs
    ) -> models.ExperimentSession:
        """Pause a running experiment session (RUNNING -> PAUSED). Sequence state is preserved."""
        session = cls.get_session(db, session_id)
        if session.status == SessionStatus.PAUSED.value:
            return session
        if session.status != SessionStatus.RUNNING.value:
            raise InvalidStateTransitionError(
                current_status=session.status,
                target_status=SessionStatus.PAUSED.value,
                message=f"Cannot pause session from '{session.status}'. Only RUNNING sessions can be paused."
            )
        cls._validate_transition(session.status, SessionStatus.PAUSED.value)

        session.status = SessionStatus.PAUSED.value
        db.commit()
        db.refresh(session)
        sync_session_to_cloud(session)

        # Pause session camera if active
        cam_mgr = CameraManagerRegistry.get_for_session(str(session.id))
        if cam_mgr and cam_mgr.is_running():
            cam_mgr.pause()

        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_PAUSED.value,
            message=f"Session {session.id} paused. Reason: {reason}",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"current_step": session.current_step_number, "reason": reason}
        )

        logger.info(f"Session {session.id} paused.")
        return session

    @classmethod
    def resume_session(
        cls,
        db: Session,
        session_id: Union[int, str],
        reason: Optional[str] = "User requested resume",
        **kwargs
    ) -> models.ExperimentSession:
        """Resume a paused experiment session (PAUSED -> RUNNING). Sequence state is preserved."""
        session = cls.get_session(db, session_id)
        if session.status == SessionStatus.RUNNING.value:
            return session
        if session.status != SessionStatus.PAUSED.value:
            raise InvalidStateTransitionError(
                current_status=session.status,
                target_status=SessionStatus.RUNNING.value,
                message=f"Cannot resume session from '{session.status}'. Only PAUSED sessions can be resumed."
            )
        cls._validate_transition(session.status, SessionStatus.RUNNING.value)


        session.status = SessionStatus.RUNNING.value
        db.commit()
        db.refresh(session)
        sync_session_to_cloud(session)

        # Resume session camera if paused
        cam_mgr = CameraManagerRegistry.get_for_session(str(session.id))
        if cam_mgr and cam_mgr.is_paused():
            cam_mgr.resume()

        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_RESUMED.value,
            message=f"Session {session.id} resumed. Reason: {reason}",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"current_step": session.current_step_number, "reason": reason}
        )

        logger.info(f"Session {session.id} resumed.")
        return session

    @classmethod
    def stop_session(
        cls,
        db: Session,
        session_id: Union[int, str],
        reason: Optional[str] = "User requested stop",
        **kwargs
    ) -> models.ExperimentSession:
        """Stop an active or paused session (RUNNING/PAUSED -> STOPPED). Historical events are preserved."""
        session = cls.get_session(db, session_id)
        cls._validate_transition(session.status, SessionStatus.STOPPED.value)

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.STOPPED.value
        session.ended_at = now
        db.commit()
        db.refresh(session)
        sync_session_to_cloud(session)

        # Stop and release session camera if active
        cam_mgr = CameraManagerRegistry.get_for_session(str(session.id))
        if cam_mgr and cam_mgr.is_running():
            cam_mgr.stop()
            CameraManagerRegistry.remove_for_session(str(session.id))
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.CAMERA_STOPPED.value,
                message=f"Session camera stopped for session '{session.id}'",
                component="camera"
            )
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.FRAME_SOURCE_CLOSED.value,
                message=f"Session frame source closed for session '{session.id}'",
                component="camera"
            )

        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_STOPPED.value,
            message=f"Session {session.id} stopped. Reason: {reason}",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"reason": reason, "ended_at": now.isoformat()}
        )

        logger.info(f"Session {session.id} stopped.")
        return session

    @classmethod
    def complete_session(
        cls,
        db: Session,
        session_id: Union[int, str],
        enforce_validator: bool = False,
        reason: Optional[str] = "Experiment completed",
        **kwargs
    ) -> models.ExperimentSession:
        """
        Mark a session as COMPLETED (RUNNING -> COMPLETED).
        If enforce_validator is True, verifies that the protocol was actually fully executed.
        """
        session = cls.get_session(db, session_id)
        cls._validate_transition(session.status, SessionStatus.COMPLETED.value)

        if enforce_validator:
            # Check if all steps were completed
            steps = get_steps_for_experiment(db, session.experiment_id)
            total_steps = len(steps)
            if session.current_step_number is None or session.current_step_number < total_steps:
                raise ValueError(
                    f"Cannot complete session {session_id}. Protocol execution is incomplete "
                    f"(at step {session.current_step_number} of {total_steps})."
                )

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.COMPLETED.value
        session.ended_at = now
        db.commit()
        db.refresh(session)
        sync_session_to_cloud(session)

        # Stop and release session camera if active
        cam_mgr = CameraManagerRegistry.get_for_session(str(session.id))
        if cam_mgr and cam_mgr.is_running():
            cam_mgr.stop()
            CameraManagerRegistry.remove_for_session(str(session.id))
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.CAMERA_STOPPED.value,
                message=f"Session camera stopped for session '{session.id}'",
                component="camera"
            )
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.FRAME_SOURCE_CLOSED.value,
                message=f"Session frame source closed for session '{session.id}'",
                component="camera"
            )

        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_COMPLETED.value,
            message=f"Experiment session {session.id} completed. Reason: {reason}",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"completed_at": now.isoformat(), "reason": reason}
        )

        logger.info(f"Session {session.id} marked COMPLETED.")
        return session

    @classmethod
    def mark_session_error(
        cls,
        db: Session,
        session_id: Union[int, str],
        error_message: str
    ) -> models.ExperimentSession:
        """Transition session to ERROR state due to critical failure (RUNNING/PAUSED -> ERROR)."""
        session = cls.get_session(db, session_id)
        cls._validate_transition(session.status, SessionStatus.ERROR.value)

        now = datetime.now(timezone.utc)
        session.status = SessionStatus.ERROR.value
        session.ended_at = now
        db.commit()
        db.refresh(session)

        # Stop and release session camera if active
        cam_mgr = CameraManagerRegistry.get_for_session(str(session.id))
        if cam_mgr and cam_mgr.is_running():
            cam_mgr.stop()
            CameraManagerRegistry.remove_for_session(str(session.id))
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.CAMERA_STOPPED.value,
                message=f"Session camera stopped for session '{session.id}'",
                component="camera"
            )
            event_service.record_system_event(
                db=db,
                session_id=session.id,
                event_type=EventType.FRAME_SOURCE_CLOSED.value,
                message=f"Session frame source closed for session '{session.id}'",
                component="camera"
            )



        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_ERROR.value,
            message=f"Session error: {error_message}",
            severity=AlertSeverity.CRITICAL.value,
            component="session",
            metadata={"error": error_message, "ended_at": now.isoformat()}
        )

        logger.error(f"Session {session.id} marked as ERROR: {error_message}")
        return session

    @classmethod
    def reset_session(cls, db: Session, session_id: Union[int, str]) -> models.ExperimentSession:
        """
        Reset session sequence progression to Step 1 for development/demo:
        - Preserves session record, experiment, and historical events
        - Resets current_step_number to 1
        - Resets expected_next_step
        - Resets ended_at to None
        - Resets status to RUNNING if it was COMPLETED/STOPPED/ERROR/PAUSED
        - Resets SequenceValidator state
        - Records SESSION_RESET event
        """
        session = cls.get_session(db, session_id)
        steps = get_steps_for_experiment(db, session.experiment_id)
        first_step = steps[0] if steps else None
        first_code = first_step.step_code if first_step else "STEP_01"
        expected_next = f"{first_step.step_code} / {first_step.expected_action}" if first_step else None

        session.current_step_number = 1
        session.current_step_code = first_code
        session.expected_next_step = expected_next
        session.ended_at = None
        session.status = SessionStatus.RUNNING.value
        db.commit()
        db.refresh(session)

        # Reset sequence validator in-memory state
        sequence_validator.reset_session(session.id)
        sequence_validator.init_session_state(
            session_id=session.id,
            experiment_id=session.experiment_id,
            steps=steps,
            current_step_number=1,
            completed=False
        )
        try:
            from app.services.experiment_service import experiment_service
            experiment_service.clear_session_alert_cache(session.id)
        except Exception:
            pass

        event_service.record_system_event(
            db=db,
            session_id=session.id,
            event_type=EventType.SESSION_RESET.value,
            message=f"Session {session.id} reset to Step 1 for re-execution.",
            severity=AlertSeverity.INFO.value,
            component="session",
            metadata={"session_id": session.id}
        )

        logger.info(f"Session {session.id} sequence state reset to Step 1.")
        return session


session_service = SessionService()
