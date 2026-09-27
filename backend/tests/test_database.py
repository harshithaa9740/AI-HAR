"""
Unit and Integration Tests for AURAVISION SQLite Database Layer
Covers all 12 mandatory test cases specified in STEP 2.
"""
import os
import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from app.db.database import Base, init_db
from app.db import models
from app.db.repository import (
    create_experiment,
    get_experiment,
    list_experiments,
    update_experiment,
    get_experiment_by_name,
    create_step,
    get_steps_for_experiment,
    create_session,
    get_session,
    get_session_by_uuid,
    update_session,
    list_sessions_for_experiment,
    create_detection_event,
    create_sequence_event,
    create_alert_event,
    create_system_event,
    get_session_detection_events,
    get_session_sequence_events,
    get_session_alert_events,
    get_system_events,
    ExperimentRepository,
    SessionRepository,
    EventRepository
)


@pytest.fixture(scope="function")
def test_db():
    """Create an isolated in-memory SQLite database with foreign keys enabled."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


# =====================================================================
# TEST 1: Create database successfully.
# =====================================================================
def test_1_create_database_successfully():
    """Verify that the database engine initializes and tables are created."""
    engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=engine)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in result]
        
        assert "experiments" in table_names
        assert "experiment_steps" in table_names
        assert "experiment_sessions" in table_names
        assert "detection_events" in table_names
        assert "sequence_events" in table_names
        assert "alert_events" in table_names
        assert "system_events" in table_names


# =====================================================================
# TEST 2: Create an experiment.
# =====================================================================
def test_2_create_experiment(test_db: Session):
    """Verify creating and retrieving an experiment."""
    exp = create_experiment(
        db=test_db,
        name="Mineral Analysis Protocol",
        description="Spectroscopic scanning of regolith samples.",
        version="1.0",
        is_active=True
    )

    assert exp.id is not None
    assert isinstance(exp.id, int)
    assert exp.name == "Mineral Analysis Protocol"
    assert exp.description == "Spectroscopic scanning of regolith samples."
    assert exp.version == "1.0"
    assert exp.is_active is True
    assert exp.created_at is not None
    assert exp.updated_at is not None


# =====================================================================
# TEST 3: Create multiple ordered experiment steps.
# =====================================================================
def test_3_create_multiple_ordered_experiment_steps(test_db: Session):
    """Verify creating ordered steps with explicit sequence numbering."""
    exp = create_experiment(db=test_db, name="Payload Calibration")

    s1 = create_step(
        db=test_db,
        experiment_id=exp.id,
        step_number=1,
        step_code="STEP_01",
        name="Power On Spectrometer",
        expected_action="POWER_ON",
        description="Switch main sensor rack to active.",
        required_objects=["spectrometer", "switch"],
        confidence_threshold=0.80
    )

    s2 = create_step(
        db=test_db,
        experiment_id=exp.id,
        step_number=2,
        step_code="STEP_02",
        name="Load Reference Sample",
        expected_action="LOAD_SAMPLE",
        description="Insert calibration tile into test slot.",
        required_objects=["sample", "tray"],
        confidence_threshold=0.75
    )

    s3 = create_step(
        db=test_db,
        experiment_id=exp.id,
        step_number=3,
        step_code="STEP_03",
        name="Seal Chamber",
        expected_action="SEAL_CHAMBER",
        description="Engage pneumatic lock.",
        required_objects=["chamber"],
        confidence_threshold=0.70
    )

    steps = get_steps_for_experiment(test_db, exp.id)
    assert len(steps) == 3
    assert [s.step_number for s in steps] == [1, 2, 3]
    assert [s.step_code for s in steps] == ["STEP_01", "STEP_02", "STEP_03"]
    assert [s.expected_action for s in steps] == ["POWER_ON", "LOAD_SAMPLE", "SEAL_CHAMBER"]
    assert json.loads(s1.required_objects) == ["spectrometer", "switch"]


# =====================================================================
# TEST 4: Create an experiment session.
# =====================================================================
def test_4_create_experiment_session(test_db: Session):
    """Verify creating and updating an experiment session."""
    exp = create_experiment(db=test_db, name="Sample Session Experiment")
    
    session = create_session(
        db=test_db,
        experiment_id=exp.id,
        session_uuid="SESSION-TEST-UUID-001",
        status="CREATED",
        stream_enabled=False,
        current_step_number=1,
        current_step_code="STEP_01"
    )

    assert session.id is not None
    assert isinstance(session.id, int)
    assert session.experiment_id == exp.id
    assert session.session_uuid == "SESSION-TEST-UUID-001"
    assert session.status == "CREATED"
    assert session.current_step_number == 1
    assert session.current_step_code == "STEP_01"
    assert session.created_at is not None

    # Update session status
    updated = update_session(
        db=test_db,
        session_id=session.id,
        status="RUNNING",
        current_step_number=2,
        current_step_code="STEP_02"
    )
    assert updated.status == "RUNNING"
    assert updated.current_step_number == 2


# =====================================================================
# TEST 5: Create detection events.
# =====================================================================
def test_5_create_detection_events(test_db: Session):
    """Verify recording perception layer detection events."""
    exp = create_experiment(db=test_db, name="Perception Experiment")
    session = create_session(db=test_db, experiment_id=exp.id)

    event1 = create_detection_event(
        db=test_db,
        session_id=session.id,
        frame_number=104,
        entity_type="OBJECT",
        entity_name="tool",
        confidence=0.92,
        bbox={"x1": 100, "y1": 150, "x2": 220, "y2": 300},
        source="yolo",
        metadata={"camera_id": 0}
    )

    event2 = create_detection_event(
        db=test_db,
        session_id=session.id,
        frame_number=105,
        entity_type="ACTION",
        entity_name="PICK_TOOL",
        confidence=0.88,
        source="activity_model",
        metadata={"hand": "right"}
    )

    detections = get_session_detection_events(test_db, session.id)
    assert len(detections) == 2
    assert detections[0].entity_name == "tool"
    assert detections[0].confidence == 0.92
    assert detections[1].entity_type == "ACTION"
    assert detections[1].entity_name == "PICK_TOOL"


# =====================================================================
# TEST 6: Create sequence events.
# =====================================================================
def test_6_create_sequence_events(test_db: Session):
    """Verify recording sequence validator validation events."""
    exp = create_experiment(db=test_db, name="Sequence Test Experiment")
    session = create_session(db=test_db, experiment_id=exp.id)

    seq1 = create_sequence_event(
        db=test_db,
        session_id=session.id,
        result="VALID",
        expected_step_number=1,
        expected_step_code="STEP_01",
        observed_step_number=1,
        observed_step_code="STEP_01",
        confidence=0.95,
        message="Step 1 completed correctly."
    )

    seq2 = create_sequence_event(
        db=test_db,
        session_id=session.id,
        result="OUT_OF_SEQUENCE",
        expected_step_number=2,
        expected_step_code="STEP_02",
        observed_step_number=4,
        observed_step_code="STEP_04",
        confidence=0.85,
        message="Observed step 4 when step 2 was expected."
    )

    events = get_session_sequence_events(test_db, session.id)
    assert len(events) == 2
    assert events[0].result == "VALID"
    assert events[1].result == "OUT_OF_SEQUENCE"
    assert events[1].expected_step_number == 2
    assert events[1].observed_step_number == 4


# =====================================================================
# TEST 7: Create alert events.
# =====================================================================
def test_7_create_alert_events(test_db: Session):
    """Verify recording and querying alert events."""
    exp = create_experiment(db=test_db, name="Alerts Test Experiment")
    session = create_session(db=test_db, experiment_id=exp.id)

    alert1 = create_alert_event(
        db=test_db,
        session_id=session.id,
        alert_type="STEP_SKIPPED",
        severity="WARNING",
        message="Warning: Step 2 was skipped by the astronaut.",
        spoken=True,
        acknowledged=False
    )

    alert2 = create_alert_event(
        db=test_db,
        session_id=session.id,
        alert_type="LOW_CONFIDENCE",
        severity="INFO",
        message="Low detection confidence on sample container.",
        spoken=False,
        acknowledged=True
    )

    alerts = get_session_alert_events(test_db, session.id)
    assert len(alerts) == 2
    assert alerts[0].alert_type == "STEP_SKIPPED"
    assert alerts[0].severity == "WARNING"
    assert alerts[0].spoken is True
    assert alerts[1].acknowledged is True


# =====================================================================
# TEST 8: Create system events.
# =====================================================================
def test_8_create_system_events(test_db: Session):
    """Verify recording and querying system lifecycle events."""
    e1 = create_system_event(
        db=test_db,
        event_type="DATABASE_INITIALIZED",
        severity="INFO",
        message="SQLite offline database tables verified.",
        component="database"
    )

    e2 = create_system_event(
        db=test_db,
        event_type="MODEL_LOADED",
        severity="INFO",
        message="Mock Activity Recognition model initialized.",
        component="ai_pipeline",
        metadata={"mode": "mock"}
    )

    system_events = get_system_events(test_db)
    assert len(system_events) >= 2
    types = [e.event_type for e in system_events]
    assert "DATABASE_INITIALIZED" in types
    assert "MODEL_LOADED" in types


# =====================================================================
# TEST 9: Retrieve experiment with its steps.
# =====================================================================
def test_9_retrieve_experiment_with_steps(test_db: Session):
    """Verify relationship loading of Experiment with ordered ExperimentStep records."""
    exp = create_experiment(
        db=test_db,
        name="Astronaut Sample Protocol Alpha",
        description="5-step sample handling verification."
    )

    for i in range(1, 6):
        create_step(
            db=test_db,
            experiment_id=exp.id,
            step_number=i,
            step_code=f"STEP_0{i}",
            name=f"Action Step {i}",
            expected_action=f"ACTION_{i}",
            description=f"Description for step {i}"
        )

    # Fetch through ORM relationship
    fetched_exp = get_experiment(test_db, exp.id)
    assert fetched_exp is not None
    assert len(fetched_exp.steps) == 5
    assert [s.step_number for s in fetched_exp.steps] == [1, 2, 3, 4, 5]
    assert fetched_exp.steps[0].step_code == "STEP_01"
    assert fetched_exp.steps[4].step_code == "STEP_05"


# =====================================================================
# TEST 10: Retrieve session with related events.
# =====================================================================
def test_10_retrieve_session_with_related_events(test_db: Session):
    """Verify relationship traversal from ExperimentSession to Detections, Sequences, and Alerts."""
    exp = create_experiment(db=test_db, name="Relational Session Test")
    session = create_session(db=test_db, experiment_id=exp.id, session_uuid="REL-SESS-99")

    # Add detection
    create_detection_event(test_db, session_id=session.id, entity_type="OBJECT", entity_name="sample")
    
    # Add sequence event
    create_sequence_event(test_db, session_id=session.id, result="VALID", expected_step_number=1)
    
    # Add alert
    create_alert_event(test_db, session_id=session.id, alert_type="INFO", message="Ready")

    fetched = get_session_by_uuid(test_db, "REL-SESS-99")
    assert fetched is not None
    assert len(fetched.detections) == 1
    assert len(fetched.sequence_events) == 1
    assert len(fetched.alerts) == 1
    assert fetched.detections[0].entity_name == "sample"
    assert fetched.sequence_events[0].result == "VALID"
    assert fetched.alerts[0].message == "Ready"


# =====================================================================
# TEST 11: Database initialization does not delete existing records.
# =====================================================================
def test_11_database_init_idempotency_preserves_data(tmp_path):
    """Verify that calling init_db multiple times does not delete or overwrite data."""
    db_file = tmp_path / "idempotency_test.db"
    file_engine = create_engine(f"sqlite:///{db_file}")

    # First init
    init_db(target_engine=file_engine)
    FileSessionLocal = sessionmaker(bind=file_engine)

    # Insert an experiment
    with FileSessionLocal() as s1:
        create_experiment(s1, name="Persistent Experiment", version="2.0")

    # Second init (should be safe and idempotent)
    init_db(target_engine=file_engine)

    # Verify data is still intact
    with FileSessionLocal() as s2:
        exp = get_experiment_by_name(s2, "Persistent Experiment")
        assert exp is not None
        assert exp.version == "2.0"

    file_engine.dispose()


# =====================================================================
# TEST 12: Relationships and foreign keys work correctly.
# =====================================================================
def test_12_relationships_and_foreign_keys_cascade(test_db: Session):
    """Verify foreign key enforcement and cascade deletion on Experiment and Session."""
    exp = create_experiment(db=test_db, name="Cascade Test Experiment")
    
    # Create step
    step = create_step(
        db=test_db,
        experiment_id=exp.id,
        step_number=1,
        step_code="STEP_01",
        name="Step 1",
        expected_action="ACTION_1"
    )
    
    # Create session
    session = create_session(db=test_db, experiment_id=exp.id)
    
    # Create child events
    create_detection_event(test_db, session_id=session.id, entity_type="OBJECT", entity_name="box")
    create_sequence_event(test_db, session_id=session.id, result="VALID")
    create_alert_event(test_db, session_id=session.id, alert_type="TEST", message="Test")

    assert test_db.query(models.ExperimentStep).count() == 1
    assert test_db.query(models.ExperimentSession).count() == 1
    assert test_db.query(models.DetectionEvent).count() == 1
    assert test_db.query(models.SequenceEvent).count() == 1
    assert test_db.query(models.AlertEvent).count() == 1

    # Deleting the experiment should cascade delete steps, sessions, and session events
    test_db.delete(exp)
    test_db.commit()

    assert test_db.query(models.Experiment).count() == 0
    assert test_db.query(models.ExperimentStep).count() == 0
    assert test_db.query(models.ExperimentSession).count() == 0
    assert test_db.query(models.DetectionEvent).count() == 0
    assert test_db.query(models.SequenceEvent).count() == 0
    assert test_db.query(models.AlertEvent).count() == 0
