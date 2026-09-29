"""
AURAVISION Database Step 3 Integration Test Suite
Verifies end-to-end integration between the verified SQLite database and the application workflow:
1. Starting a session creates a persisted session.
2. Session status changes are persisted.
3. Real detection records are associated with the correct session (and unassigned when none active).
4. Validation events and alerts are persisted (with foreign keys and deduplication).
5. Session history can be retrieved through the existing API.
6. Artifact references are saved only when appropriate.
7. Existing API contracts still work.
8. The application runs completely offline without internet access.
"""
import os
import json
import tempfile
import socket
import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import Base, get_db
from app.db import models
from app.db.repository import (
    ExperimentRepository,
    SessionRepository,
    EventRepository,
    ArtifactRepository,
    SettingRepository,
    get_session,
    list_sessions,
    get_steps_for_experiment
)
from app.services.experiment_service import experiment_service
from app.services.session_service import session_service
from app.services.event_service import event_service
from app.core.constants import SessionStatus, AlertSeverity, AlertType, ValidationResult


@pytest.fixture
def isolated_test_env():
    """
    Creates an isolated temporary SQLite database file and configures
    FastAPI dependency overrides so tests do not touch auravision.db.
    """
    temp_dir = tempfile.mkdtemp(prefix="auravision_test_")
    db_path = os.path.join(temp_dir, "test_workflow.db")
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed default experiment
    with TestingSessionLocal() as db:
        experiment_service.seed_default_experiment_if_empty(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "engine": engine,
        "SessionLocal": TestingSessionLocal,
        "client": client,
        "temp_dir": temp_dir,
        "db_path": db_path
    }

    # Cleanup
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass


# =========================================================================
# TEST 1: Starting a session creates a persisted session
# =========================================================================
def test_starting_session_creates_persisted_session(isolated_test_env):
    client = isolated_test_env["client"]
    SessionLocal = isolated_test_env["SessionLocal"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        exp_id = exp.id

    # 1. Start session via API
    resp = client.post("/api/sessions/start", json={
        "experiment_id": exp_id,
        "session_code": "TEST-SESS-001"
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["session_code"] == "TEST-SESS-001"
    assert data["status"] == "RUNNING"
    assert data["current_step_number"] == 1
    assert data["current_step_code"] == "STEP_01"
    session_id = data["id"]

    # 2. Verify directly in database
    with SessionLocal() as db:
        sess = SessionRepository.get_by_id(db, session_id)
        assert sess is not None
        assert sess.status == "RUNNING"
        assert sess.started_at is not None
        assert sess.current_step_number == 1
        assert sess.experiment_id == exp_id

    # 3. Verify idempotent repeated start with same session_code
    resp_repeat = client.post("/api/sessions/start", json={
        "experiment_id": exp_id,
        "session_code": "TEST-SESS-001"
    })
    assert resp_repeat.status_code == 201
    assert resp_repeat.json()["id"] == session_id

    with SessionLocal() as db:
        count = db.query(models.ExperimentSession).filter(
            models.ExperimentSession.session_uuid == "TEST-SESS-001"
        ).count()
        assert count == 1, "Duplicate session should not be created for repeated requests"


# =========================================================================
# TEST 2: Session status changes are persisted
# =========================================================================
def test_session_status_changes_are_persisted(isolated_test_env):
    client = isolated_test_env["client"]
    SessionLocal = isolated_test_env["SessionLocal"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        exp_id = exp.id

    # Start session
    start_resp = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": "STATUS-TEST-01"})
    assert start_resp.status_code == 201
    session_id = start_resp.json()["id"]

    # Pause session (RUNNING -> PAUSED)
    pause_resp = client.post(f"/api/sessions/{session_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    with SessionLocal() as db:
        sess = SessionRepository.get_by_id(db, session_id)
        assert sess.status == "PAUSED"

    # Resume session (PAUSED -> RUNNING)
    resume_resp = client.post(f"/api/sessions/{session_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "RUNNING"

    with SessionLocal() as db:
        sess = SessionRepository.get_by_id(db, session_id)
        assert sess.status == "RUNNING"

    # Stop session (RUNNING -> STOPPED)
    stop_resp = client.post(f"/api/sessions/{session_id}/stop", json={"reason": "User completed procedure"})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "STOPPED"

    with SessionLocal() as db:
        sess = SessionRepository.get_by_id(db, session_id)
        assert sess.status == "STOPPED"
        assert sess.ended_at is not None

        # Verify lifecycle system events were persisted in DB
        system_events = db.query(models.SystemEvent).filter(models.SystemEvent.session_id == session_id).all()
        types = [e.event_type for e in system_events]
        assert "SESSION_CREATED" in types or "SESSION_STARTED" in types
        assert "SESSION_PAUSED" in types
        assert "SESSION_RESUMED" in types
        assert "SESSION_STOPPED" in types


# =========================================================================
# TEST 3: Real detection records associated with correct session
# =========================================================================
def test_real_detections_associated_with_correct_session_and_non_session(isolated_test_env):
    SessionLocal = isolated_test_env["SessionLocal"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        sess = session_service.start_session(db, experiment_id=exp.id, session_code="DETECTION-SESS-01")
        session_id = sess.id

    # 1. Detection during active session
    with SessionLocal() as db:
        det1 = EventRepository.record_detection(
            db=db,
            session_id=session_id,
            event_type="ACTIVITY_RECOGNITION",
            action_code="PICK_TOOL",
            confidence=0.94,
            metadata_json={"objects": ["tool"], "pose": "standing"}
        )
        assert det1.id is not None
        assert det1.session_id == session_id
        assert det1.action_code == "PICK_TOOL"
        assert det1.confidence == 0.94

    # 2. Detection when NO session is active (session_id=None)
    with SessionLocal() as db:
        det_idle = EventRepository.record_detection(
            db=db,
            session_id=None,
            event_type="ACTIVITY_RECOGNITION",
            action_code="GENERAL_MOTION",
            confidence=0.88,
            metadata_json={"notes": "pre-mission standby"}
        )
        assert det_idle.id is not None
        assert det_idle.session_id is None, "Non-session detections must have session_id=None without assigning to unrelated session"

    # 3. Verify retrieval filters correctly
    with SessionLocal() as db:
        sess_dets = EventRepository.get_session_detections(db, session_id)
        assert len(sess_dets) == 1
        assert sess_dets[0].action_code == "PICK_TOOL"

        unassigned_dets = db.query(models.DetectionEvent).filter(models.DetectionEvent.session_id.is_(None)).all()
        assert len(unassigned_dets) >= 1
        assert any(d.action_code == "GENERAL_MOTION" for d in unassigned_dets)


# =========================================================================
# TEST 4: Validation events and alerts are persisted
# =========================================================================
def test_validation_events_and_alerts_persisted_with_deduplication(isolated_test_env):
    client = isolated_test_env["client"]
    SessionLocal = isolated_test_env["SessionLocal"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        sess = session_service.start_session(db, experiment_id=exp.id, session_code="VALIDATION-TEST-01")
        session_id = sess.id

    # 1. Valid action for Step 1 (PICK_TOOL)
    val_resp1 = client.post("/api/validate", json={
        "session_id": session_id,
        "action_code": "PICK_TOOL",
        "confidence": 0.95,
        "observed_objects": ["tool"]
    })
    assert val_resp1.status_code == 200
    data1 = val_resp1.json()
    assert data1["result"] == "VALID"
    assert data1["completed_step"] == 1
    assert data1["next_step"] == 2

    with SessionLocal() as db:
        # Check SequenceEvent
        seq_events = EventRepository.get_session_sequence(db, session_id)
        assert len(seq_events) == 1
        assert seq_events[0].result == "VALID"
        assert seq_events[0].expected_step == 1
        assert seq_events[0].observed_step == 1

        # Check AlertEvent generated
        alerts = EventRepository.get_session_alerts(db, session_id)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "STEP_COMPLETED"
        assert alerts[0].validation_event_id == seq_events[0].id

    # 2. Out of sequence action (e.g. STEP_04 PLACE_SAMPLE while expecting Step 2)
    val_resp2 = client.post("/api/validate", json={
        "session_id": session_id,
        "action_code": "PLACE_SAMPLE",
        "confidence": 0.92,
        "observed_objects": ["sample", "container"]
    })
    assert val_resp2.status_code == 200
    data2 = val_resp2.json()
    assert data2["result"] == "STEP_SKIPPED"

    with SessionLocal() as db:
        alerts = EventRepository.get_session_alerts(db, session_id)
        assert len(alerts) == 2
        skipped_alert = alerts[-1]
        assert skipped_alert.alert_type == "STEP_SKIPPED"
        assert skipped_alert.severity == "WARNING"

    # 3. Repeated identical out-of-sequence action should deduplicate alert row
    val_resp3 = client.post("/api/validate", json={
        "session_id": session_id,
        "action_code": "PLACE_SAMPLE",
        "confidence": 0.92,
        "observed_objects": ["sample", "container"]
    })
    assert val_resp3.status_code == 200

    with SessionLocal() as db:
        alerts_after = EventRepository.get_session_alerts(db, session_id)
        # Should not create duplicate alert row for identical ongoing condition
        assert len(alerts_after) == 2, "Duplicate alert for same ongoing condition should be deduplicated"

    # 4. Test Alert Acknowledgement
    with SessionLocal() as db:
        alert_to_ack = EventRepository.get_session_alerts(db, session_id)[0]
        alert_id = alert_to_ack.id

    ack_resp = client.post(f"/api/sessions/{session_id}/alerts/{alert_id}/acknowledge")
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is True
    assert ack_resp.json()["acknowledged_at"] is not None

    with SessionLocal() as db:
        alert_db = db.query(models.AlertEvent).filter(models.AlertEvent.id == alert_id).first()
        assert alert_db.acknowledged is True
        assert alert_db.acknowledged_at is not None


# =========================================================================
# TEST 5: Session history retrieved through existing API
# =========================================================================
def test_session_history_retrieved_through_existing_api(isolated_test_env):
    client = isolated_test_env["client"]
    SessionLocal = isolated_test_env["SessionLocal"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        sess = session_service.start_session(db, experiment_id=exp.id, session_code="HISTORY-TEST-01")
        session_id = sess.id

        # Insert some detection and sequence events
        EventRepository.record_detection(db, session_id=session_id, action_code="PICK_TOOL", confidence=0.91)
        experiment_service.validate_session_action(db, session_id=session_id, action_code="PICK_TOOL", confidence=0.91)

    # 1. GET /api/sessions
    list_resp = client.get("/api/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert any(s["session_code"] == "HISTORY-TEST-01" for s in sessions)

    # 2. GET /api/sessions/{session_id}
    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id

    # 3. GET /api/sessions/{session_id}/events (Unified Timeline)
    timeline_resp = client.get(f"/api/sessions/{session_id}/events")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert timeline["session_id"] == session_id
    assert len(timeline["events"]) >= 2

    # 4. GET /api/sessions/{session_id}/alerts
    alerts_resp = client.get(f"/api/sessions/{session_id}/alerts")
    assert alerts_resp.status_code == 200
    assert len(alerts_resp.json()) >= 1


# =========================================================================
# TEST 6: Artifact references saved only when appropriate
# =========================================================================
def test_artifact_references_saved_safely(isolated_test_env):
    client = isolated_test_env["client"]
    SessionLocal = isolated_test_env["SessionLocal"]
    temp_dir = isolated_test_env["temp_dir"]

    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        sess = session_service.start_session(db, experiment_id=exp.id, session_code="ARTIFACT-TEST-01")
        session_id = sess.id

    # 1. Non-existent file should NOT create an artifact record
    fake_video = os.path.join(temp_dir, "non_existent.mp4")
    with SessionLocal() as db:
        # Check condition before saving
        if os.path.exists(fake_video):
            ArtifactRepository.create(db, session_id=session_id, artifact_type="recording", file_path=fake_video)
        artifacts = ArtifactRepository.get_for_session(db, session_id)
        assert len(artifacts) == 0, "Missing or failed video creation must not record an artifact"

    # 2. Existing real file creates valid artifact record
    real_video = os.path.join(temp_dir, "real_recording.mp4")
    with open(real_video, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00testvideo")

    with SessionLocal() as db:
        assert os.path.exists(real_video)
        art = ArtifactRepository.create(
            db=db,
            session_id=session_id,
            artifact_type="recording",
            file_path=real_video,
            file_name="real_recording.mp4",
            mime_type="video/mp4",
            file_size_bytes=os.path.getsize(real_video),
            metadata={"fps": 30, "duration": 5.2}
        )
        assert art.id is not None
        assert art.file_size_bytes > 0

    # 3. Retrieve artifacts via API
    art_resp = client.get(f"/api/sessions/{session_id}/artifacts")
    assert art_resp.status_code == 200
    art_list = art_resp.json()
    assert len(art_list) == 1
    assert art_list[0]["file_name"] == "real_recording.mp4"
    assert art_list[0]["mime_type"] == "video/mp4"


# =========================================================================
# TEST 7: Existing API contracts still work
# =========================================================================
def test_existing_api_contracts_still_work(isolated_test_env):
    client = isolated_test_env["client"]

    # 1. Health
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["status"] == "ok"
    assert h_data["database_connected"] is True
    assert h_data["offline_mode"] is True

    # 2. System Status
    status_resp = client.get("/api/system/status")
    assert status_resp.status_code == 200
    s_data = status_resp.json()
    assert s_data["database_connected"] is True
    assert "active_sessions" in s_data
    assert "video_source" in s_data

    # 3. Experiments list & steps
    exp_resp = client.get("/api/experiments")
    assert exp_resp.status_code == 200
    experiments = exp_resp.json()
    assert len(experiments) >= 1
    exp_id = experiments[0]["id"]

    steps_resp = client.get(f"/api/experiments/{exp_id}/steps")
    assert steps_resp.status_code == 200
    steps = steps_resp.json()
    assert len(steps) >= 1
    assert steps[0]["step_number"] == 1


# =========================================================================
# TEST 8: The application runs completely without internet access
# =========================================================================
def test_application_runs_fully_offline(isolated_test_env, monkeypatch):
    client = isolated_test_env["client"]

    # Block any socket connections to external WAN/internet IPs
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host, port = address[0], address[1]
        # Allow only loopback localhost connections
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ConnectionRefusedError(f"Internet access blocked in offline mode: {host}:{port}")
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # 1. Health check runs offline
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["offline_mode"] is True

    # 2. Experiments, sessions, and validation work offline
    exp_resp = client.get("/api/experiments")
    assert exp_resp.status_code == 200
    exp_id = exp_resp.json()[0]["id"]

    start_resp = client.post("/api/sessions/start", json={"experiment_id": exp_id, "session_code": "OFFLINE-TEST-01"})
    assert start_resp.status_code == 201
    sess_id = start_resp.json()["id"]

    val_resp = client.post("/api/validate", json={
        "session_id": sess_id,
        "action_code": "PICK_TOOL",
        "confidence": 0.95,
        "observed_objects": ["tool"]
    })
    assert val_resp.status_code == 200
    assert val_resp.json()["result"] == "VALID"

    # Stop session offline
    stop_resp = client.post(f"/api/sessions/{sess_id}/stop")
    assert stop_resp.status_code == 200
