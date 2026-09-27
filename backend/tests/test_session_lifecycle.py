"""
AURAVISION - STEP 6 TEST SUITE: Session & Event Management
Tests session lifecycle state machine, transitions, event persistence, unified timeline, and REST endpoints.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.core.constants import SessionStatus, EventType, AlertSeverity, ValidationResult
from app.services.session_service import (
    session_service,
    InvalidStateTransitionError,
    SessionNotFoundError,
    ExperimentNotFoundError
)
from app.services.event_service import event_service
from app.services.experiment_service import experiment_service
from app.services.sequence_validator import sequence_validator

client = TestClient(app)


# =====================================================================
# SECTION 1: SESSION LIFECYCLE STATE MACHINE (TESTS 1 - 13)
# =====================================================================

def test_01_create_session_defaults_to_created_status(db_session):
    """Creating a session puts it in CREATED status with started_at=None, ended_at=None."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)

    assert sess.id is not None
    assert sess.status == SessionStatus.CREATED.value
    assert sess.started_at is None
    assert sess.ended_at is None
    assert sess.current_step_number == 1
    assert sess.experiment_id == exp.id


def test_02_start_session_transitions_created_to_running(db_session):
    """Starting a session transitions CREATED -> RUNNING and records started_at."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    
    started_sess = session_service.start_session(db_session, session_id=sess.id)
    assert started_sess.status == SessionStatus.RUNNING.value
    assert started_sess.started_at is not None
    assert started_sess.ended_at is None


def test_03_pause_session_transitions_running_to_paused(db_session):
    """Pausing a running session transitions RUNNING -> PAUSED."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    paused_sess = session_service.pause_session(db_session, session_id=sess.id, reason="Crew rest")
    assert paused_sess.status == SessionStatus.PAUSED.value
    assert paused_sess.ended_at is None


def test_04_resume_session_transitions_paused_to_running(db_session):
    """Resuming a paused session transitions PAUSED -> RUNNING."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.pause_session(db_session, session_id=sess.id)

    resumed_sess = session_service.resume_session(db_session, session_id=sess.id)
    assert resumed_sess.status == SessionStatus.RUNNING.value


def test_05_stop_session_from_running(db_session):
    """Stopping a RUNNING session transitions to STOPPED and sets ended_at."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    stopped_sess = session_service.stop_session(db_session, session_id=sess.id, reason="Manual abort")
    assert stopped_sess.status == SessionStatus.STOPPED.value
    assert stopped_sess.ended_at is not None


def test_06_stop_session_from_paused(db_session):
    """Stopping a PAUSED session transitions to STOPPED and sets ended_at."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.pause_session(db_session, session_id=sess.id)

    stopped_sess = session_service.stop_session(db_session, session_id=sess.id, reason="Aborted while paused")
    assert stopped_sess.status == SessionStatus.STOPPED.value
    assert stopped_sess.ended_at is not None


def test_07_cannot_resume_or_start_completed_session(db_session):
    """COMPLETED sessions cannot transition to RUNNING or PAUSED."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.complete_session(db_session, session_id=sess.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.start_session(db_session, session_id=sess.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.resume_session(db_session, session_id=sess.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.pause_session(db_session, session_id=sess.id)


def test_08_cannot_resume_or_start_stopped_session(db_session):
    """STOPPED sessions cannot transition to RUNNING or PAUSED."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.stop_session(db_session, session_id=sess.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.start_session(db_session, session_id=sess.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.resume_session(db_session, session_id=sess.id)


def test_09_validator_completion_sets_status_completed(db_session):
    """Validating through all steps marks session as COMPLETED via validator integration."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    # Execute all 5 steps of Sample Experiment
    experiment_service.validate_session_action(db_session, sess.id, "PICK_TOOL", 0.95, ["tool"])
    experiment_service.validate_session_action(db_session, sess.id, "OPEN_CONTAINER", 0.92, ["container"])
    experiment_service.validate_session_action(db_session, sess.id, "TAKE_SAMPLE", 0.94, ["sample"])
    experiment_service.validate_session_action(db_session, sess.id, "PLACE_SAMPLE", 0.91, ["sample", "container"])
    res5 = experiment_service.validate_session_action(db_session, sess.id, "CLOSE_CONTAINER", 0.93, ["container"])

    assert res5.result == ValidationResult.EXPERIMENT_COMPLETE.value
    assert res5.completed is True

    # Reload session from db
    refreshed_sess = session_service.get_session(db_session, sess.id)
    assert refreshed_sess.status == SessionStatus.COMPLETED.value
    assert refreshed_sess.ended_at is not None



def test_10_cannot_pause_created_session(db_session):
    """CREATED sessions cannot be paused without starting first."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)

    with pytest.raises(InvalidStateTransitionError):
        session_service.pause_session(db_session, session_id=sess.id)


def test_11_session_error_state(db_session):
    """Marking a session with error sets status to ERROR and records SystemEvent."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    err_sess = session_service.mark_session_error(db_session, session_id=sess.id, error_message="Sensor offline")
    assert err_sess.status == SessionStatus.ERROR.value
    assert err_sess.ended_at is not None


def test_12_session_reset_resets_step_to_one(db_session):
    """Resetting session resets step progression back to 1 and keeps status RUNNING."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    experiment_service.validate_session_action(db_session, sess.id, "PICK_TOOL", 0.95, ["tool"])
    experiment_service.validate_session_action(db_session, sess.id, "OPEN_CONTAINER", 0.92, ["container"])

    reset_sess = session_service.reset_session(db_session, session_id=sess.id)
    assert reset_sess.current_step_number == 1
    assert reset_sess.current_step_code == "STEP_01"
    assert reset_sess.status == SessionStatus.RUNNING.value


def test_13_invalid_state_transitions_raise_proper_error(db_session):
    """Arbitrary illegal state transitions raise InvalidStateTransitionError."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)

    # CREATED -> RESUME (illegal)
    with pytest.raises(InvalidStateTransitionError):
        session_service.resume_session(db_session, sess.id)

    session_service.start_session(db_session, sess.id)
    session_service.stop_session(db_session, sess.id)

    # STOPPED -> PAUSE (illegal)
    with pytest.raises(InvalidStateTransitionError):
        session_service.pause_session(db_session, sess.id)


# =====================================================================
# SECTION 2: EVENT PERSISTENCE & SYSTEM EVENTS (TESTS 14 - 23)
# =====================================================================

def test_14_session_created_event_recorded(db_session):
    """SESSION_CREATED event is recorded upon session creation."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_CREATED.value for e in sys_events)


def test_15_session_started_event_recorded(db_session):
    """SESSION_STARTED event is recorded upon session start."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_STARTED.value for e in sys_events)


def test_16_session_paused_event_recorded(db_session):
    """SESSION_PAUSED event is recorded upon session pause."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.pause_session(db_session, session_id=sess.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_PAUSED.value for e in sys_events)


def test_17_session_resumed_event_recorded(db_session):
    """SESSION_RESUMED event is recorded upon session resume."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.pause_session(db_session, session_id=sess.id)
    session_service.resume_session(db_session, session_id=sess.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_RESUMED.value for e in sys_events)


def test_18_session_stopped_event_recorded(db_session):
    """SESSION_STOPPED event is recorded upon session stop."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.stop_session(db_session, session_id=sess.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_STOPPED.value for e in sys_events)


def test_19_session_completed_event_recorded(db_session):
    """SESSION_COMPLETED event is recorded upon session completion."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.complete_session(db_session, session_id=sess.id)

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_COMPLETED.value for e in sys_events)


def test_20_session_error_event_recorded(db_session):
    """SESSION_ERROR event is recorded when error state is triggered."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)
    session_service.mark_session_error(db_session, session_id=sess.id, error_message="Vision failure")

    sys_events = event_service.get_system_events(db_session, session_id=sess.id)
    assert any(e.event_type == EventType.SESSION_ERROR.value for e in sys_events)


def test_21_sequence_events_isolated_per_session(db_session):
    """Sequence events are correctly associated with specific session IDs."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess1 = session_service.start_session(db_session, experiment_id=exp.id)
    sess2 = session_service.start_session(db_session, experiment_id=exp.id)

    event_service.record_sequence_event(db_session, session_id=sess1.id, expected_step=1, observed_step=1, result="VALID")
    event_service.record_sequence_event(db_session, session_id=sess2.id, expected_step=1, observed_step=2, result="STEP_SKIPPED")

    s1_events = event_service.get_sequence_events(db_session, session_id=sess1.id)
    s2_events = event_service.get_sequence_events(db_session, session_id=sess2.id)

    assert len(s1_events) == 1
    assert s1_events[0].result == "VALID"
    assert len(s2_events) == 1
    assert s2_events[0].result == "STEP_SKIPPED"


def test_22_alert_events_isolated_per_session(db_session):
    """Alert events are correctly isolated per session."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess1 = session_service.start_session(db_session, experiment_id=exp.id)
    sess2 = session_service.start_session(db_session, experiment_id=exp.id)

    event_service.record_alert_event(db_session, session_id=sess1.id, alert_type="STEP_SKIPPED", severity="WARNING", message="Skip 1")
    event_service.record_alert_event(db_session, session_id=sess2.id, alert_type="LOW_CONFIDENCE", severity="INFO", message="Low conf 2")

    a1 = event_service.get_alerts(db_session, session_id=sess1.id)
    a2 = event_service.get_alerts(db_session, session_id=sess2.id)

    assert len(a1) == 1
    assert a1[0].alert_type == "STEP_SKIPPED"
    assert len(a2) == 1
    assert a2[0].alert_type == "LOW_CONFIDENCE"


def test_23_detection_events_isolated_per_session(db_session):
    """Detection events are correctly isolated per session."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess1 = session_service.start_session(db_session, experiment_id=exp.id)
    sess2 = session_service.start_session(db_session, experiment_id=exp.id)

    event_service.record_detection_event(db_session, session_id=sess1.id, event_type="action", confidence=0.9, action_code="PICK_TOOL")
    event_service.record_detection_event(db_session, session_id=sess2.id, event_type="action", confidence=0.85, action_code="OPEN_CONTAINER")

    d1 = event_service.get_detection_events(db_session, session_id=sess1.id)
    d2 = event_service.get_detection_events(db_session, session_id=sess2.id)

    assert len(d1) == 1
    assert d1[0].entity_name == "PICK_TOOL"
    assert len(d2) == 1
    assert d2[0].entity_name == "OPEN_CONTAINER"


# =====================================================================
# SECTION 3: EVENT TIMELINE & CHRONOLOGICAL ORDER (TESTS 24 - 28)
# =====================================================================

def test_24_timeline_returns_events_in_chronological_order(db_session):
    """Timeline returns unified stream of all event categories sorted ascending."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)
    session_service.start_session(db_session, session_id=sess.id)

    event_service.record_detection_event(db_session, session_id=sess.id, event_type="action", confidence=0.95, action_code="PICK_TOOL")
    event_service.record_sequence_event(db_session, session_id=sess.id, expected_step=1, observed_step=1, result="VALID")
    event_service.record_alert_event(db_session, session_id=sess.id, alert_type="STEP_COMPLETED", severity="INFO", message="Step 1 complete")

    timeline = event_service.get_session_timeline(db_session, session_id=sess.id)
    assert timeline.total_events >= 4  # CREATED, STARTED, DETECTION, SEQUENCE, ALERT
    
    # Check timestamps are monotonically non-decreasing
    timestamps = [e.timestamp for e in timeline.events]
    assert timestamps == sorted(timestamps)


def test_25_timeline_filters_by_session_strictly(db_session):
    """Timeline for Session A never includes events from Session B."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sessA = session_service.start_session(db_session, experiment_id=exp.id)
    sessB = session_service.start_session(db_session, experiment_id=exp.id)

    event_service.record_detection_event(db_session, session_id=sessA.id, event_type="action", confidence=0.99, action_code="UNIQUE_A")
    event_service.record_detection_event(db_session, session_id=sessB.id, event_type="action", confidence=0.99, action_code="UNIQUE_B")

    timelineA = event_service.get_session_timeline(db_session, session_id=sessA.id)
    timelineB = event_service.get_session_timeline(db_session, session_id=sessB.id)

    actionsA = [e.details.get("action_code") or e.details.get("entity_name") for e in timelineA.events]
    actionsB = [e.details.get("action_code") or e.details.get("entity_name") for e in timelineB.events]

    assert "UNIQUE_A" in actionsA
    assert "UNIQUE_B" not in actionsA
    assert "UNIQUE_B" in actionsB
    assert "UNIQUE_A" not in actionsB


def test_26_timeline_event_type_filter(db_session):
    """Filtering timeline by event_type returns only matching event kinds."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.start_session(db_session, experiment_id=exp.id)

    event_service.record_alert_event(db_session, session_id=sess.id, alert_type="STEP_SKIPPED", severity="WARNING", message="Skip detected")
    event_service.record_detection_event(db_session, session_id=sess.id, event_type="action", confidence=0.95, action_code="PICK_TOOL")

    timeline_alerts = event_service.get_session_timeline(db_session, session_id=sess.id, event_type="alert")
    assert all(e.category == "alert" for e in timeline_alerts.events)
    assert len(timeline_alerts.events) >= 1


def test_27_timeline_empty_for_new_session_with_no_extra_events(db_session):
    """New session timeline accurately reports system lifecycle events."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.create_session(db_session, experiment_id=exp.id)

    timeline = event_service.get_session_timeline(db_session, session_id=sess.id)
    assert timeline.total_events == 1
    assert timeline.events[0].category == "system"
    assert timeline.events[0].event_type == "SESSION_CREATED"


def test_28_timeline_time_range_filter(db_session):
    """Filtering timeline by start_time / end_time constrains results correctly."""
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    sess = session_service.start_session(db_session, experiment_id=exp.id)

    past = datetime.now(timezone.utc) - timedelta(hours=2)
    future = datetime.now(timezone.utc) + timedelta(hours=2)

    timeline = event_service.get_session_timeline(db_session, session_id=sess.id, start_time=past, end_time=future)
    assert timeline.total_events >= 1

    # Far future start_time returns 0 events
    far_future = datetime.now(timezone.utc) + timedelta(days=10)
    timeline_empty = event_service.get_session_timeline(db_session, session_id=sess.id, start_time=far_future)
    assert timeline_empty.total_events == 0


# =====================================================================
# SECTION 4: REST API ENDPOINTS (TESTS 29 - 40)
# =====================================================================

def test_29_api_create_session():
    """POST /api/sessions creates a new session in CREATED status."""
    exp_res = client.get("/api/experiments")
    assert exp_res.status_code == 200
    exp_id = exp_res.json()[0]["id"]

    res = client.post("/api/sessions", json={"experiment_id": exp_id})
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "CREATED"
    assert data["started_at"] is None
    assert data["id"] is not None


def test_30_api_list_sessions():
    """GET /api/sessions lists all execution sessions."""
    res = client.get("/api/sessions")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_31_api_get_session_by_id_and_uuid():
    """GET /api/sessions/{id} works with integer ID and UUID string."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    code = f"TEST-UUID-{uuid.uuid4().hex[:6]}"
    create_res = client.post("/api/sessions", json={"experiment_id": exp_id, "session_code": code})
    sess_id = create_res.json()["id"]

    # By integer ID
    res_id = client.get(f"/api/sessions/{sess_id}")
    assert res_id.status_code == 200
    assert res_id.json()["id"] == sess_id

    # By UUID string
    res_uuid = client.get(f"/api/sessions/{code}")
    assert res_uuid.status_code == 200
    assert res_uuid.json()["session_uuid"] == code


def test_32_api_get_nonexistent_session_404():
    """GET /api/sessions/999999 returns 404 Not Found."""
    res = client.get("/api/sessions/9999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_33_api_start_session():
    """POST /api/sessions/{id}/start starts a CREATED session."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()

    start_res = client.post(f"/api/sessions/{sess['id']}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "RUNNING"
    assert start_res.json()["started_at"] is not None


def test_34_api_pause_session():
    """POST /api/sessions/{id}/pause pauses a RUNNING session."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")

    pause_res = client.post(f"/api/sessions/{sess['id']}/pause", json={"reason": "Astronaut snack break"})
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"


def test_35_api_resume_session():
    """POST /api/sessions/{id}/resume resumes a PAUSED session."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")
    client.post(f"/api/sessions/{sess['id']}/pause")

    resume_res = client.post(f"/api/sessions/{sess['id']}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "RUNNING"


def test_36_api_stop_session():
    """POST /api/sessions/{id}/stop stops a session."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")

    stop_res = client.post(f"/api/sessions/{sess['id']}/stop", json={"reason": "Emergency drill"})
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"
    assert stop_res.json()["ended_at"] is not None


def test_37_api_reset_session():
    """POST /api/sessions/{id}/reset resets the sequence state to step 1."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")

    # Advance
    client.post("/api/validate", json={"session_id": sess["id"], "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})

    reset_res = client.post(f"/api/sessions/{sess['id']}/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["current_step_number"] == 1
    assert reset_res.json()["current_step_code"] == "STEP_01"


def test_38_api_get_timeline_events():
    """GET /api/sessions/{id}/events returns unified timeline response."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")

    events_res = client.get(f"/api/sessions/{sess['id']}/events")
    assert events_res.status_code == 200
    data = events_res.json()
    assert "events" in data
    assert "total_events" in data
    assert data["session_id"] == sess["id"]
    assert data["total_events"] >= 2  # CREATED and STARTED


def test_39_api_get_sub_events_endpoints():
    """GET sub-event endpoints (/sequence-events, /alerts, /detections, /system-events)."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()
    client.post(f"/api/sessions/{sess['id']}/start")

    # Generate sequence & alert event
    client.post("/api/validate", json={"session_id": sess["id"], "action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]})

    seq_res = client.get(f"/api/sessions/{sess['id']}/sequence-events")
    assert seq_res.status_code == 200
    assert len(seq_res.json()) >= 1

    alt_res = client.get(f"/api/sessions/{sess['id']}/alerts")
    assert alt_res.status_code == 200
    assert len(alt_res.json()) >= 1

    sys_res = client.get(f"/api/sessions/{sess['id']}/system-events")
    assert sys_res.status_code == 200
    assert len(sys_res.json()) >= 2


def test_40_api_invalid_transition_returns_400():
    """Illegal state transition via API returns HTTP 400 with descriptive detail."""
    exp_res = client.get("/api/experiments")
    exp_id = exp_res.json()[0]["id"]
    sess = client.post("/api/sessions", json={"experiment_id": exp_id}).json()

    # Try pausing a CREATED session (illegal)
    res_pause = client.post(f"/api/sessions/{sess['id']}/pause")
    assert res_pause.status_code == 400
    detail = res_pause.json()["detail"].lower()
    assert "cannot pause" in detail or "cannot transition" in detail or "invalid" in detail


