"""
SQLAlchemy Database Models for AURAVISION Offline System
Comprehensive, normalized schema for Space Station BAS Experiment Validation.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.database import Base


def generate_uuid() -> str:
    """Generate a unique UUIDv4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


# =====================================================================
# 1. EXPERIMENT PROTOCOLS (experiments)
# =====================================================================

class Experiment(Base):
    """
    Experiment Protocol Definition Model.
    Represents an astronaut payload/experiment protocol with strict step sequences.
    """
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
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


# Alias for explicit protocol terminology
ExperimentProtocol = Experiment


# =====================================================================
# 2. PROTOCOL STEPS (experiment_steps)
# =====================================================================

class ExperimentStep(Base):
    """
    Ordered Experiment Protocol Step Model.
    Defines expected sequential actions, required objects, and timing rules.
    """
    __tablename__ = "experiment_steps"
    __table_args__ = (
        UniqueConstraint("experiment_id", "step_number", name="uq_step_protocol_number"),
        Index("ix_step_experiment_number", "experiment_id", "step_number"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    step_code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    expected_action = Column(String(100), nullable=False)
    required_objects = Column(Text, default="[]", nullable=False)  # JSON-encoded list
    confidence_threshold = Column(Float, default=0.70, nullable=False)
    validation_rules = Column(Text, nullable=True)  # JSON-encoded custom rules/constraints
    expected_duration_seconds = Column(Integer, nullable=True)  # Nominal step execution time
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationship
    experiment = relationship("Experiment", back_populates="steps")
    detections = relationship("DetectionEvent", back_populates="protocol_step")
    validation_events = relationship("SequenceEvent", back_populates="protocol_step")

    # Compatibility aliases
    @property
    def protocol_id(self) -> int:
        return self.experiment_id

    @protocol_id.setter
    def protocol_id(self, val: int):
        self.experiment_id = val

    @property
    def expected_activity(self) -> str:
        return self.expected_action

    @expected_activity.setter
    def expected_activity(self, val: str):
        self.expected_action = val

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


# Alias for explicit protocol step terminology
ProtocolStep = ExperimentStep


# =====================================================================
# 3. EXPERIMENT SESSIONS (experiment_sessions)
# =====================================================================

class ExperimentSession(Base):
    """
    Experiment Execution Session Model.
    Tracks a live or completed astronaut experiment procedure run.
    """
    __tablename__ = "experiment_sessions"
    __table_args__ = (
        Index("ix_session_exp_created", "experiment_id", "created_at"),
        Index("ix_session_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    session_uuid = Column(String(64), unique=True, default=generate_uuid, nullable=False, index=True)
    session_name = Column(String(255), nullable=True)
    status = Column(String(50), default="CREATED", nullable=False)  # CREATED, RUNNING, PAUSED, COMPLETED, STOPPED, ERROR
    started_at = Column(DateTime, default=None, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    current_step_number = Column(Integer, nullable=True, default=1)
    current_step_code = Column(String(50), nullable=True)
    expected_next_step = Column(String(100), nullable=True)
    operator_label = Column(String(100), nullable=True, default="Astronaut Specialist")
    notes = Column(Text, nullable=True)
    recording_path = Column(String(500), nullable=True)
    stream_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=True)

    # Relationships
    experiment = relationship("Experiment", back_populates="sessions")
    detections = relationship("DetectionEvent", back_populates="session", cascade="all, delete-orphan")
    sequence_events = relationship("SequenceEvent", back_populates="session", cascade="all, delete-orphan")
    alerts = relationship("AlertEvent", back_populates="session", cascade="all, delete-orphan")
    system_events = relationship("SystemEvent", back_populates="session", cascade="all, delete-orphan")
    artifacts = relationship("SessionArtifact", back_populates="session", cascade="all, delete-orphan")

    # Backward compatibility aliases
    @property
    def protocol_id(self) -> int:
        return self.experiment_id

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


# =====================================================================
# 4. ACTIVITY DETECTIONS (detection_events)
# =====================================================================

class DetectionEvent(Base):
    """
    AI Perception & Activity Detection Model.
    Stores bounding boxes, recognized actions, objects, and astronaut body/hand telemetry.
    """
    __tablename__ = "detection_events"
    __table_args__ = (
        Index("ix_detection_session_time", "session_id", "timestamp"),
        Index("ix_detection_entity", "entity_type", "entity_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    protocol_step_id = Column(Integer, ForeignKey("experiment_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    frame_number = Column(Integer, nullable=True)
    start_time_ms = Column(Float, nullable=True)
    end_time_ms = Column(Float, nullable=True)
    entity_type = Column(String(50), nullable=False)  # PERSON, OBJECT, ACTION, HAND
    entity_name = Column(String(100), nullable=False)  # astronaut, tool, sample, PICK_TOOL
    confidence = Column(Float, nullable=True)
    bbox = Column(Text, nullable=True)  # SQLite-compatible JSON format
    source = Column(String(100), nullable=True)  # camera_0, yolo, mock, etc.
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationships
    session = relationship("ExperimentSession", back_populates="detections")
    protocol_step = relationship("ExperimentStep", back_populates="detections")

    # Property aliases
    @property
    def activity_label(self) -> str:
        return self.entity_name

    @property
    def action_code(self) -> str:
        return self.entity_name

    @property
    def label(self) -> str:
        return self.entity_name

    @property
    def detected_at(self) -> datetime:
        return self.timestamp

    @property
    def source_camera(self) -> Optional[str]:
        return self.source

    @property
    def metadata_payload(self) -> str:
        return self.metadata_json

    @metadata_payload.setter
    def metadata_payload(self, val: str):
        self.metadata_json = val


# Alias for explicit activity detection terminology
ActivityDetection = DetectionEvent


# =====================================================================
# 5. VALIDATION EVENTS (sequence_events)
# =====================================================================

class SequenceEvent(Base):
    """
    Protocol Sequence Validation Event Model.
    Records deterministic step validation outcomes against the protocol state machine.
    """
    __tablename__ = "sequence_events"
    __table_args__ = (
        Index("ix_sequence_session_time", "session_id", "timestamp"),
        Index("ix_sequence_result", "result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    protocol_step_id = Column(Integer, ForeignKey("experiment_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=True)  # STEP_VALIDATED, STEP_SKIPPED, OUT_OF_SEQUENCE, etc.
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    expected_step_number = Column(Integer, nullable=True)
    expected_step_code = Column(String(50), nullable=True)
    observed_step_number = Column(Integer, nullable=True)
    observed_step_code = Column(String(50), nullable=True)
    result = Column(String(50), nullable=False)  # VALID, STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, VERIFY_REQUIRED, EXPERIMENT_COMPLETE
    confidence = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationships
    session = relationship("ExperimentSession", back_populates="sequence_events")
    protocol_step = relationship("ExperimentStep", back_populates="validation_events")
    alerts = relationship("AlertEvent", back_populates="validation_event")

    # Compatibility properties
    @property
    def occurred_at(self) -> datetime:
        return self.timestamp

    @property
    def expected_activity(self) -> Optional[str]:
        return self.expected_step_code

    @property
    def observed_activity(self) -> Optional[str]:
        return self.observed_step_code

    @property
    def expected_step(self) -> Optional[int]:
        return self.expected_step_number

    @property
    def observed_step(self) -> Optional[int]:
        return self.observed_step_number

    @property
    def reason(self) -> Optional[str]:
        return self.message


# Alias for explicit validation event terminology
ValidationEvent = SequenceEvent


# =====================================================================
# 6. ALERTS (alert_events)
# =====================================================================

class AlertEvent(Base):
    """
    Alert Event Model.
    Records visual warnings, auditory alerts, critical deviations, and system notifications.
    """
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_session_time", "session_id", "timestamp"),
        Index("ix_alert_severity", "severity"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    validation_event_id = Column(Integer, ForeignKey("sequence_events.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, LOW_CONFIDENCE, etc.
    severity = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, CRITICAL
    category = Column(String(50), default="protocol", nullable=False)  # protocol, hardware, ai, security
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    spoken = Column(Boolean, default=False, nullable=False)
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationships
    session = relationship("ExperimentSession", back_populates="alerts")
    validation_event = relationship("SequenceEvent", back_populates="alerts")

    # Compatibility properties
    @property
    def created_at(self) -> datetime:
        return self.timestamp


# Alias for explicit alert terminology
Alert = AlertEvent


# =====================================================================
# 7. SESSION ARTIFACTS (session_artifacts)
# =====================================================================

class SessionArtifact(Base):
    """
    Session Artifact Model.
    Stores references to local files generated during experiment runs:
    MP4 video recordings, JSONL audit streams, TXT compliance logs, snapshots.
    """
    __tablename__ = "session_artifacts"
    __table_args__ = (
        Index("ix_artifact_session_type", "session_id", "artifact_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False)  # recording, log_txt, log_jsonl, snapshot, export
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)  # video/mp4, text/plain, application/x-ndjson
    file_size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="artifacts")


# =====================================================================
# 8. SYSTEM SETTINGS (system_settings)
# =====================================================================

class SystemSetting(Base):
    """
    Persistent System Setting Model.
    Stores runtime parameters, AI confidence thresholds, and camera preferences offline.
    Never stores secrets, passwords, or credentials.
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=False)  # JSON or string representation
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


# =====================================================================
# 9. SYSTEM EVENTS (system_events)
# =====================================================================

class SystemEvent(Base):
    """
    System Lifecycle & Diagnostics Event Model.
    Records system startup, shutdown, database events, model loading, and errors.
    """
    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_event_time", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("experiment_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    event_type = Column(String(50), nullable=False)  # SESSION_CREATED, SESSION_STARTED, etc.
    severity = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    component = Column(String(50), nullable=True)  # session, validator, database, video, system, api
    metadata_json = Column("metadata", Text, default="{}", nullable=False)

    # Relationship
    session = relationship("ExperimentSession", back_populates="system_events")
