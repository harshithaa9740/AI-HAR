"""
Comprehensive Database Layer Test Suite for AURAVISION
Covers the 8 core requirements:
1. Database initialization and migrations.
2. Creating and retrieving a protocol.
3. Creating protocol steps and preserving their order.
4. Creating and updating an experiment session.
5. Persisting detections, validation events, and alerts.
6. Foreign-key and uniqueness constraints.
7. Retrieving session history after restarting the application.
8. Handling invalid data and database errors.
"""
import os
import json
import tempfile
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from app.db.database import Base, init_db
from app.db import models
from app.db.repository import (
    create_experiment,
    get_experiment,
    get_experiment_by_name,
    list_experiments,
    update_experiment,
    delete_experiment,
    create_step,
    get_step,
    get_steps_for_experiment,
    update_step,
    create_session,
    get_session,
    get_session_by_uuid,
    update_session,
    list_sessions,
    create_detection_event,
    get_session_detection_events,
    create_sequence_event,
    get_session_sequence_events,
    create_alert_event,
    get_session_alert_events,
    create_artifact,
    get_artifact,
    get_session_artifacts,
    delete_artifact,
    get_setting,
    set_setting,
    get_all_settings,
    delete_setting,
    ExperimentRepository,
    SessionRepository,
    EventRepository,
    ArtifactRepository,
    SettingRepository
)


@pytest.fixture(scope="function")
def isolated_db():
    """Create a completely isolated in-memory SQLite database with foreign keys enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(target_engine=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# =====================================================================
# 1. Database initialization and migrations
# =====================================================================

def test_01_database_initialization_and_migrations():
    """Verify that init_db creates all 8 required tables and migrates schema columns."""
    engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=engine)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in result]

        # Verify all core entities exist
        assert "experiments" in table_names
        assert "experiment_steps" in table_names
        assert "experiment_sessions" in table_names
        assert "detection_events" in table_names
        assert "sequence_events" in table_names
        assert "alert_events" in table_names
        assert "session_artifacts" in table_names
        assert "system_settings" in table_names
        assert "system_events" in table_names

        # Verify migrated columns on experiment_sessions
        session_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(experiment_sessions)").fetchall()]
        assert "session_name" in session_cols
        assert "operator_label" in session_cols
        assert "notes" in session_cols
        assert "updated_at" in session_cols

        # Verify migrated columns on experiment_steps
        step_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(experiment_steps)").fetchall()]
        assert "validation_rules" in step_cols
        assert "expected_duration_seconds" in step_cols

        # Verify migrated columns on detection_events
        det_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(detection_events)").fetchall()]
        assert "protocol_step_id" in det_cols
        assert "start_time_ms" in det_cols
        assert "end_time_ms" in det_cols

        # Verify migrated columns on sequence_events
        seq_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sequence_events)").fetchall()]
        assert "protocol_step_id" in seq_cols
        assert "event_type" in seq_cols

        # Verify migrated columns on alert_events
        alert_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alert_events)").fetchall()]
        assert "validation_event_id" in alert_cols
        assert "category" in alert_cols


# =====================================================================
# 2. Creating and retrieving a protocol
# =====================================================================

def test_02_create_and_retrieve_protocol(isolated_db: Session):
    """Verify creating, querying, and updating an experiment protocol."""
    proto = create_experiment(
        db=isolated_db,
        name="BAS-CRYSTAL-901",
        description="Microgravity protein crystal growth validation.",
        version="2.1.0",
        is_active=True
    )
    assert proto.id is not None
    assert proto.name == "BAS-CRYSTAL-901"
    assert proto.version == "2.1.0"
    assert proto.is_active is True
    assert proto.created_at is not None

    # Retrieve by ID
    fetched = get_experiment(isolated_db, proto.id)
    assert fetched is not None
    assert fetched.name == "BAS-CRYSTAL-901"

    # Retrieve by unique name
    fetched_by_name = get_experiment_by_name(isolated_db, "BAS-CRYSTAL-901")
    assert fetched_by_name is not None
    assert fetched_by_name.id == proto.id

    # Update protocol attributes
    updated = update_experiment(
        isolated_db,
        proto.id,
        description="Updated protein crystallization procedure.",
        version="2.2.0"
    )
    assert updated.description == "Updated protein crystallization procedure."
    assert updated.version == "2.2.0"


# =====================================================================
# 3. Creating protocol steps and preserving their order
# =====================================================================

def test_03_create_protocol_steps_and_preserve_order(isolated_db: Session):
    """Verify creating protocol steps inserted in arbitrary order and retrieved in strict step order."""
    proto = create_experiment(isolated_db, name="BAS-CHEM-ORDER-TEST")

    # Insert steps intentionally out of sequential order: 3, 1, 4, 2, 5
    create_step(
        db=isolated_db,
        experiment_id=proto.id,
        step_number=3,
        step_code="STEP_03",
        name="Take Sample",
        expected_action="TAKE_SAMPLE",
        expected_duration_seconds=45,
        required_objects=["pipette", "vial"]
    )
    create_step(
        db=isolated_db,
        experiment_id=proto.id,
        step_number=1,
        step_code="STEP_01",
        name="Pick Tool",
        expected_action="PICK_TOOL",
        expected_duration_seconds=15,
        required_objects=["pipette"]
    )
    create_step(
        db=isolated_db,
        experiment_id=proto.id,
        step_number=4,
        step_code="STEP_04",
        name="Place Sample",
        expected_action="PLACE_SAMPLE",
        expected_duration_seconds=30,
        required_objects=["sample", "reaction_plate"]
    )
    create_step(
        db=isolated_db,
        experiment_id=proto.id,
        step_number=2,
        step_code="STEP_02",
        name="Open Container",
        expected_action="OPEN_CONTAINER",
        expected_duration_seconds=20,
        required_objects=["vial"]
    )
    create_step(
        db=isolated_db,
        experiment_id=proto.id,
        step_number=5,
        step_code="STEP_05",
        name="Seal Container",
        expected_action="SEAL_CONTAINER",
        expected_duration_seconds=25,
        required_objects=["vial_lid"],
        validation_rules={"hermetic_seal_required": True}
    )

    steps = get_steps_for_experiment(isolated_db, proto.id)
    assert len(steps) == 5
    # Strict sequential ordering guaranteed
    assert [s.step_number for s in steps] == [1, 2, 3, 4, 5]
    assert [s.expected_action for s in steps] == [
        "PICK_TOOL",
        "OPEN_CONTAINER",
        "TAKE_SAMPLE",
        "PLACE_SAMPLE",
        "SEAL_CONTAINER"
    ]
    # Check aliases and extended fields
    assert steps[0].expected_activity == "PICK_TOOL"
    assert steps[0].protocol_id == proto.id
    assert steps[0].expected_duration_seconds == 15
    assert json.loads(steps[4].validation_rules) == {"hermetic_seal_required": True}


# =====================================================================
# 4. Creating and updating an experiment session
# =====================================================================

def test_04_create_and_update_experiment_session(isolated_db: Session):
    """Verify full session lifecycle states: CREATED -> RUNNING -> PAUSED -> COMPLETED."""
    proto = create_experiment(isolated_db, name="BAS-SESSION-LIFECYCLE")

    session = create_session(
        db=isolated_db,
        experiment_id=proto.id,
        session_uuid="SES-ISRO-2026-TEST",
        session_name="ISS Flight Session Alpha",
        status="CREATED",
        operator_label="Payload Specialist Sharma",
        notes="Pre-flight equipment check nominal"
    )

    assert session.id is not None
    assert session.session_uuid == "SES-ISRO-2026-TEST"
    assert session.session_name == "ISS Flight Session Alpha"
    assert session.operator_label == "Payload Specialist Sharma"
    assert session.status == "CREATED"
    assert session.current_step_number == 1

    # Transition to RUNNING
    start_time = datetime.now(timezone.utc)
    updated = update_session(
        isolated_db,
        session.id,
        status="RUNNING",
        started_at=start_time,
        notes="Astronaut initiated experiment sequence"
    )
    assert updated.status == "RUNNING"
    assert updated.started_at is not None
    assert updated.started_at.year == start_time.year
    assert updated.notes == "Astronaut initiated experiment sequence"

    # Transition to PAUSED
    paused = update_session(isolated_db, session.id, status="PAUSED", current_step_number=2)
    assert paused.status == "PAUSED"
    assert paused.current_step_number == 2

    # Transition to COMPLETED
    end_time = datetime.now(timezone.utc)
    completed = update_session(isolated_db, session.id, status="COMPLETED", ended_at=end_time)
    assert completed.status == "COMPLETED"
    assert completed.ended_at is not None


# =====================================================================
# 5. Persisting detections, validation events, and alerts
# =====================================================================

def test_05_persisting_detections_validation_events_and_alerts(isolated_db: Session):
    """Verify persisting AI perception detections, sequence outcomes, and alerts with foreign keys."""
    proto = create_experiment(isolated_db, name="BAS-TELEMETRY-TEST")
    step = create_step(
        isolated_db,
        experiment_id=proto.id,
        step_number=1,
        step_code="STEP_01",
        name="Pick Pipette",
        expected_action="PICK_TOOL"
    )
    session = create_session(isolated_db, experiment_id=proto.id)

    # 1. Activity Detection
    det = create_detection_event(
        db=isolated_db,
        session_id=session.id,
        protocol_step_id=step.id,
        entity_type="ACTION",
        entity_name="PICK_TOOL",
        confidence=0.965,
        frame_number=120,
        start_time_ms=4000.0,
        end_time_ms=4500.0,
        source="yolo_mediapipe",
        metadata={"hand_velocity_ms": 0.28, "joint_count": 33}
    )
    assert det.id is not None
    assert det.activity_label == "PICK_TOOL"
    assert det.confidence == 0.965
    assert det.start_time_ms == 4000.0
    assert det.protocol_step_id == step.id

    # 2. Sequence Validation Event
    seq = create_sequence_event(
        db=isolated_db,
        session_id=session.id,
        protocol_step_id=step.id,
        result="VALID",
        event_type="STEP_VALIDATED",
        expected_step_number=1,
        expected_step_code="STEP_01",
        observed_step_number=1,
        observed_step_code="STEP_01",
        confidence=0.965,
        message="Step 1 successfully confirmed by AI HAR.",
        metadata={"source": "realtime_processor"}
    )
    assert seq.id is not None
    assert seq.result == "VALID"
    assert seq.event_type == "STEP_VALIDATED"
    assert seq.protocol_step_id == step.id

    # 3. Alert Event referencing the validation event
    alert = create_alert_event(
        db=isolated_db,
        session_id=session.id,
        validation_event_id=seq.id,
        alert_type="STEP_VALIDATED",
        severity="INFO",
        category="protocol",
        message="Auditory confirmation: Step 1 validated.",
        spoken=True,
        acknowledged=True
    )
    assert alert.id is not None
    assert alert.validation_event_id == seq.id
    assert alert.category == "protocol"
    assert alert.spoken is True

    # Check session query helpers
    detections = get_session_detection_events(isolated_db, session.id)
    assert len(detections) == 1
    sequences = get_session_sequence_events(isolated_db, session.id)
    assert len(sequences) == 1
    alerts = get_session_alert_events(isolated_db, session.id)
    assert len(alerts) == 1


# =====================================================================
# 6. Foreign-key and uniqueness constraints
# =====================================================================

def test_06_foreign_key_and_uniqueness_constraints(isolated_db: Session):
    """Verify that SQLite foreign keys and unique constraints are strictly enforced."""
    proto = create_experiment(isolated_db, name="BAS-CONSTRAINTS-TEST")

    # 1. Foreign Key Constraint: Session with nonexistent experiment_id must fail
    with pytest.raises(IntegrityError):
        create_session(isolated_db, experiment_id=999999)
    isolated_db.rollback()

    # 2. Uniqueness Constraint: Duplicate protocol name must fail
    with pytest.raises(IntegrityError):
        create_experiment(isolated_db, name="BAS-CONSTRAINTS-TEST")
    isolated_db.rollback()

    # 3. Uniqueness Constraint: Duplicate step number within the same protocol must fail
    create_step(
        isolated_db,
        experiment_id=proto.id,
        step_number=1,
        step_code="STEP_01",
        name="Step One",
        expected_action="ACTION_A"
    )
    with pytest.raises(IntegrityError):
        create_step(
            isolated_db,
            experiment_id=proto.id,
            step_number=1,  # Duplicate step_number for proto.id
            step_code="STEP_01_DUP",
            name="Step One Duplicate",
            expected_action="ACTION_B"
        )
    isolated_db.rollback()


# =====================================================================
# 7. Retrieving session history after restarting the application
# =====================================================================

def test_07_retrieving_session_history_after_restart():
    """Verify that data persists on disk and is completely restored upon engine shutdown and restart."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Phase A: Initial engine creation and data insertion
        engine1 = create_engine(f"sqlite:///{db_path}")
        init_db(target_engine=engine1)
        SessionMaker1 = sessionmaker(bind=engine1)

        with SessionMaker1() as db1:
            proto = create_experiment(db1, name="PERSISTENCE-TEST-PROTOCOL", version="1.0.0")
            step = create_step(db1, proto.id, 1, "STEP_01", "Tool Acquisition", "PICK_TOOL")
            session = create_session(db1, proto.id, session_uuid="PERSISTENT-SES-777", session_name="Persisted Session")
            create_detection_event(db1, session.id, "ACTION", "PICK_TOOL", 0.95)
            create_sequence_event(db1, session.id, "VALID", event_type="STEP_VALIDATED", message="Step validated successfully")
            create_alert_event(db1, session.id, "STEP_VALIDATED", "Step completed", severity="INFO")
            create_artifact(db1, session.id, "recording", "/data/recordings/test.mp4", "test.mp4", "video/mp4", 102400)
            set_setting(db1, "active_profile", "microgravity_mode")

        # Dispose first engine completely (simulate application shutdown)
        engine1.dispose()

        # Phase B: Brand new engine instance pointing to the same SQLite file (simulate restart)
        engine2 = create_engine(f"sqlite:///{db_path}")
        init_db(target_engine=engine2)
        SessionMaker2 = sessionmaker(bind=engine2)

        with SessionMaker2() as db2:
            # Query back protocol
            restored_proto = get_experiment_by_name(db2, "PERSISTENCE-TEST-PROTOCOL")
            assert restored_proto is not None
            assert restored_proto.version == "1.0.0"

            # Query back session
            restored_session = get_session_by_uuid(db2, "PERSISTENT-SES-777")
            assert restored_session is not None
            assert restored_session.session_name == "Persisted Session"

            # Query back detections
            dets = get_session_detection_events(db2, restored_session.id)
            assert len(dets) == 1
            assert dets[0].entity_name == "PICK_TOOL"
            assert dets[0].confidence == 0.95

            # Query back sequence events
            seqs = get_session_sequence_events(db2, restored_session.id)
            assert len(seqs) == 1
            assert seqs[0].result == "VALID"

            # Query back alerts
            alerts = get_session_alert_events(db2, restored_session.id)
            assert len(alerts) == 1
            assert alerts[0].message == "Step completed"

            # Query back artifacts
            artifacts = get_session_artifacts(db2, restored_session.id)
            assert len(artifacts) == 1
            assert artifacts[0].file_name == "test.mp4"
            assert artifacts[0].file_size_bytes == 102400

            # Query back persistent settings
            setting_val = get_setting(db2, "active_profile")
            assert setting_val == "microgravity_mode"

        engine2.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


# =====================================================================
# 8. Handling invalid data and database errors
# =====================================================================

def test_08_handling_invalid_data_and_database_errors(isolated_db: Session):
    """Verify graceful error handling, rollbacks, and repositories for artifacts and settings."""
    # 1. Graceful lookups for nonexistent entities
    assert get_experiment(isolated_db, 999999) is None
    assert get_step(isolated_db, 999999) is None
    assert get_session(isolated_db, "nonexistent-uuid") is None
    assert get_artifact(isolated_db, 999999) is None
    assert get_setting(isolated_db, "nonexistent_key", default="fallback") == "fallback"

    # 2. Artifact repository operations
    proto = create_experiment(isolated_db, name="ARTIFACT-TEST-PROTO")
    session = create_session(isolated_db, proto.id)

    art = create_artifact(
        db=isolated_db,
        session_id=session.id,
        artifact_type="log_jsonl",
        file_path="/data/logs/session_audit.jsonl",
        file_name="session_audit.jsonl",
        mime_type="application/x-ndjson",
        file_size_bytes=4096,
        metadata={"format": "jsonl"}
    )
    assert art.id is not None
    assert art.file_size_bytes == 4096

    artifacts = get_session_artifacts(isolated_db, session.id, artifact_type="log_jsonl")
    assert len(artifacts) == 1

    # Delete artifact
    deleted = delete_artifact(isolated_db, art.id)
    assert deleted is True
    assert get_artifact(isolated_db, art.id) is None

    # 3. System Settings repository operations
    set_setting(isolated_db, "confidence_threshold", 0.85)
    set_setting(isolated_db, "voice_enabled", True)
    set_setting(isolated_db, "camera_config", {"fps": 30, "resolution": "1080p"})

    assert get_setting(isolated_db, "confidence_threshold") == 0.85
    assert get_setting(isolated_db, "voice_enabled") is True
    assert get_setting(isolated_db, "camera_config") == {"fps": 30, "resolution": "1080p"}

    all_s = get_all_settings(isolated_db)
    assert "confidence_threshold" in all_s
    assert "voice_enabled" in all_s
    assert "camera_config" in all_s

    # Delete setting
    assert delete_setting(isolated_db, "voice_enabled") is True
    assert get_setting(isolated_db, "voice_enabled") is None

    # 4. Safe transaction rollback on failure
    # Ensure database session remains healthy after rollback
    with pytest.raises(IntegrityError):
        # Attempt to insert step without required expected_action
        invalid_step = models.ExperimentStep(
            experiment_id=proto.id,
            step_number=99,
            step_code="STEP_99",
            name="Invalid Step",
            expected_action=None  # NOT NULL constraint violation
        )
        isolated_db.add(invalid_step)
        isolated_db.commit()

    isolated_db.rollback()

    # Verify session is still completely operational
    new_step = create_step(isolated_db, proto.id, 99, "STEP_99", "Valid Step", "VALID_ACTION")
    assert new_step.id is not None


# =====================================================================
# 9. Alert acknowledgement and foreign-key linking
# =====================================================================

def test_09_alert_acknowledgement_and_foreign_keys(isolated_db: Session):
    """Verify that alerts link to validation_event_id and support timestamped acknowledgement."""
    from app.db.repository import acknowledge_alert

    proto = create_experiment(isolated_db, name="ALERT-ACK-TEST-PROTO")
    step = create_step(isolated_db, proto.id, 1, "STEP_01", "Action 1", "ACTION_1")
    session = create_session(isolated_db, proto.id)

    # Sequence event
    seq = create_sequence_event(
        isolated_db,
        session_id=session.id,
        protocol_step_id=step.id,
        result="OUT_OF_SEQUENCE",
        message="Step performed out of sequence"
    )

    # Alert linking to sequence event
    alert = create_alert_event(
        isolated_db,
        session_id=session.id,
        validation_event_id=seq.id,
        alert_type="OUT_OF_SEQUENCE",
        severity="WARNING",
        category="protocol",
        message="Protocol deviation alert"
    )

    assert alert.id is not None
    assert alert.validation_event_id == seq.id
    assert alert.acknowledged is False
    assert alert.acknowledged_at is None

    # Acknowledge the alert
    ack_time = datetime.now(timezone.utc)
    ack_alert = acknowledge_alert(isolated_db, alert.id)
    assert ack_alert is not None
    assert ack_alert.acknowledged is True
    assert ack_alert.acknowledged_at is not None
    assert ack_alert.acknowledged_at.year == ack_time.year


# =====================================================================
# 10. Step duration and custom validation rules persistence
# =====================================================================

def test_10_step_duration_and_validation_rules_persistence(isolated_db: Session):
    """Verify that expected_duration_seconds and validation_rules JSON persist and update cleanly."""
    proto = create_experiment(isolated_db, name="STEP-EXT-TEST-PROTO")
    rules = {"require_glove_verification": True, "tolerance_ms": 500}

    step = create_step(
        isolated_db,
        experiment_id=proto.id,
        step_number=1,
        step_code="STEP_01",
        name="Sterile Handling",
        expected_action="HANDLE_STERILE",
        validation_rules=rules,
        expected_duration_seconds=90
    )

    assert step.id is not None
    assert step.expected_duration_seconds == 90
    assert json.loads(step.validation_rules) == rules

    # Update step rules and duration
    new_rules = {"require_glove_verification": True, "tolerance_ms": 250, "sensor_check": "active"}
    updated = update_step(
        isolated_db,
        step.id,
        expected_duration_seconds=120,
        validation_rules=new_rules
    )

    assert updated.expected_duration_seconds == 120
    assert json.loads(updated.validation_rules) == new_rules


# =====================================================================
# 11. REST API endpoint for alert acknowledgement
# =====================================================================

def test_11_api_alert_acknowledgement_endpoint():
    """Verify POST /api/sessions/{session_id}/alerts/{alert_id}/acknowledge endpoint in isolated DB."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import get_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    init_db(target_engine=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSession() as db:
            proto = create_experiment(db, name="ACK-API-PROTO-UNIQUE")
            create_step(db, proto.id, 1, "STEP_01", "Action 1", "ACTION_1")
            session = create_session(db, proto.id, session_uuid=models.generate_uuid())
            seq = create_sequence_event(db, session.id, "OUT_OF_SEQUENCE")
            alert = create_alert_event(
                db,
                session_id=session.id,
                validation_event_id=seq.id,
                alert_type="STEP_SKIPPED",
                severity="WARNING",
                category="protocol",
                message="Step skipped alert"
            )
            assert alert.acknowledged is False
            sess_id = session.id
            alt_id = alert.id
            seq_id = seq.id

        client = TestClient(app)
        # Call API endpoint
        response = client.post(f"/api/sessions/{sess_id}/alerts/{alt_id}/acknowledge")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == alt_id
        assert data["acknowledged"] is True
        assert data["acknowledged_at"] is not None
        assert data["category"] == "protocol"
        assert data["validation_event_id"] == seq_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass



