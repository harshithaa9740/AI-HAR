"""
SQLAlchemy Database Models for AURAVISION Offline System
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.orm import relationship
from app.db.database import Base


def generate_uuid() -> str:
    """Generate a unique UUIDv4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class Experiment(Base):
    """
    Experiment Definition Model.
    Represents an astronaut payload/experiment protocol.
    """
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), default="1.0", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    steps = relationship(
        "ExperimentStep",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ExperimentStep.step_number"
    )
    sessions = relationship(
        "ExperimentSession",
        back_populates="experiment",
        cascade="all, delete-orphan"
    )

    # Backward compatibility property
    @property
    def status(self) -> str:
        return "ACTIVE" if self.is_active else "INACTIVE"

    @status.setter
    def status(self, val: str):
        self.is_active = (val.upper() == "ACTIVE")


class ExperimentStep(Base):
    """
    Ordered Experiment Step Model.
    Defines expected sequential actions and required object interactions.
    """
    __tablename__ = "experiment_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False)
    step_code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    expected_action = Column(String(100), nullable=False)
    required_objects = Column(Text, default="[]", nullable=False)  # JSON-encoded list
    confidence_threshold = Column(Float, default=0.70, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationship
    experiment = relationship("Experiment", back_populates="steps")

    # Backward compatibility aliases
    @property
    def action_code(self) -> str:
        return self.expected_action

    @action_code.setter
    def action_code(self, val: str):
        self.expected_action = val

    @property
    def display_name(self) -> str:
        return self.name

    @display_name.setter
    def display_name(self, val: str):
        self.name = val

    @property
    def expected_objects(self) -> str:
        return self.required_objects

    @expected_objects.setter
    def expected_objects(self, val: str):
        self.required_objects = val


class ExperimentSession(Base):
    """
    Experiment Execution Session Model.
    Tracks a live or completed astronaut experiment run.
    """
    __tablename__ = "experiment_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    session_uuid = Column(String(64), unique=True, default=generate_uuid, nullable=False, index=True)
    status = Column(String(50), default="CREATED", nullable=False)  # CREATED, RUNNING, PAUSED, COMPLETED, STOPPED, ERROR
    started_at = Column(DateTime, default=None, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    current_step_number = Column(Integer, nullable=True, default=1)
    current_step_code = Column(String(50), nullable=True)
    expected_next_step = Column(String(100), nullable=True)
    recording_path = Column(String(500), nullable=True)
    stream_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    experiment = relationship("Experiment", back_populates="sessions")
    detections = relationship("DetectionEvent", back_populates="session", cascade="all, delete-orphan")
    sequence_events = relationship("SequenceEvent", back_populates="session", cascade="all, delete-orphan")
    alerts = relationship("AlertEvent", back_populates="session", cascade="all, delete-orphan")
    system_events = relationship("SystemEvent", back_populates="session", cascade="all, delete-orphan")

    # Backward compatibility aliases
    @property
    def session_code(self) -> str:
        return self.session_uuid

    @session_code.setter
    def session_code(self, val: str):
        self.session_uuid = val

    @property
    def current_step(self) -> int:
        return self.current_step_number or 1

    @current_step.setter
    def current_step(self, val: int):
        self.current_step_number = val


class DetectionEvent(Base):
    """
    AI Perception & Detection Observation Event.
    Stores bounding boxes, recognized actions, objects, and astronaut body/hand telemetry.
    """
    __tablename__ = "detection_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    frame_number = Column(Integer, nullable=True)
    entity_type = Column(String(50), nullable=False)  # PERSON, OBJECT, ACTION, HAND
    entity_name = Column(String(100), nullable=False)  # astronaut, tool, sample, PICK_TOOL
    confidence = Column(Float, nullable=True)
    bbox = Column(Text, nullable=True)  # SQLite-compatible JSON format
    source = Column(String(100), nullable=True)  # camera_0, yolo, mock, etc.
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="detections")

    # Property alias for metadata attribute access
    @property
    def metadata_payload(self) -> str:
        return self.metadata_json

    @metadata_payload.setter
    def metadata_payload(self, val: str):
        self.metadata_json = val


class SequenceEvent(Base):
    """
    Sequence Validation Event Model.
    Records the outcome of deterministic step validation against the protocol state machine.
    """
    __tablename__ = "sequence_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    expected_step_number = Column(Integer, nullable=True)
    expected_step_code = Column(String(50), nullable=True)
    observed_step_number = Column(Integer, nullable=True)
    observed_step_code = Column(String(50), nullable=True)
    result = Column(String(50), nullable=False)  # VALID, STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, VERIFY_REQUIRED, EXPERIMENT_COMPLETE
    confidence = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="sequence_events")

    # Backward compatibility properties
    @property
    def expected_step(self) -> int:
        return self.expected_step_number

    @property
    def observed_step(self) -> int:
        return self.observed_step_number

    @property
    def reason(self) -> str:
        return self.message


class AlertEvent(Base):
    """
    Alert Event Model.
    Records warnings, auditory alerts, critical deviations, and system alerts.
    """
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    alert_type = Column(String(50), nullable=False)  # STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, LOW_CONFIDENCE, OBJECT_NOT_DETECTED, EXPERIMENT_COMPLETE, SYSTEM_ERROR, STEP_COMPLETED
    severity = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, CRITICAL
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    spoken = Column(Boolean, default=False, nullable=False)
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="alerts")


class SystemEvent(Base):
    """
    System Lifecycle & Diagnostics Event Model.
    Records system startup, shutdown, database events, model loading, and errors.
    """
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    event_type = Column(String(50), nullable=False)  # SESSION_CREATED, SESSION_STARTED, etc.
    severity = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    component = Column(String(50), nullable=True)  # session, validator, database, video, system, api
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="system_events")

