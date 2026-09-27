"""
Unit & Integration Tests for Deterministic Sequence Validator (Step 4)
Covers all 14 mandatory test scenarios.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.main import app
from app.services.sequence_validator import SequenceValidator
from app.services.experiment_service import experiment_service
from app.core.constants import ValidationResult, AlertType, AlertSeverity
from app.db import models
from app.db.repository import EventRepository, SessionRepository

# In-memory test SQLite setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


PROTOCOL_STEPS = [
    {
        "step_number": 1,
        "step_code": "STEP_01",
        "name": "Pick Tool",
        "expected_action": "PICK_TOOL",
        "required_objects": ["tool"],
        "confidence_threshold": 0.70,
        "description": "Retrieve sterilized extraction tool."
    },
    {
        "step_number": 2,
        "step_code": "STEP_02",
        "name": "Open Container",
        "expected_action": "OPEN_CONTAINER",
        "required_objects": ["container"],
        "confidence_threshold": 0.70,
        "description": "Unseal specimen containment vessel."
    },
    {
        "step_number": 3,
        "step_code": "STEP_03",
        "name": "Take Sample",
        "expected_action": "TAKE_SAMPLE",
        "required_objects": ["sample"],
        "confidence_threshold": 0.70,
        "description": "Extract sample core."
    },
    {
        "step_number": 4,
        "step_code": "STEP_04",
        "name": "Place Sample",
        "expected_action": "PLACE_SAMPLE",
        "required_objects": ["sample", "container"],
        "confidence_threshold": 0.70,
        "description": "Transfer sample into chamber."
    },
    {
        "step_number": 5,
        "step_code": "STEP_05",
        "name": "Close Container",
        "expected_action": "CLOSE_CONTAINER",
        "required_objects": ["container"],
        "confidence_threshold": 0.70,
        "description": "Reseal specimen containment vessel."
    }
]


# =====================================================================
# TEST 1 — NORMAL SEQUENCE
# =====================================================================
def test_1_normal_sequence():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_normal_seq"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    r1 = validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    assert r1.result == ValidationResult.VALID.value
    assert r1.next_step_number == 2
    assert not r1.completed

    r2 = validator.validate_action("OPEN_CONTAINER", confidence=0.92, observed_objects=["container"], session_id=session_id)
    assert r2.result == ValidationResult.VALID.value
    assert r2.next_step_number == 3
    assert not r2.completed

    r3 = validator.validate_action("TAKE_SAMPLE", confidence=0.91, observed_objects=["sample"], session_id=session_id)
    assert r3.result == ValidationResult.VALID.value
    assert r3.next_step_number == 4
    assert not r3.completed

    r4 = validator.validate_action("PLACE_SAMPLE", confidence=0.94, observed_objects=["sample", "container"], session_id=session_id)
    assert r4.result == ValidationResult.VALID.value
    assert r4.next_step_number == 5
    assert not r4.completed

    r5 = validator.validate_action("CLOSE_CONTAINER", confidence=0.98, observed_objects=["container"], session_id=session_id)
    assert r5.result == ValidationResult.EXPERIMENT_COMPLETE.value
    assert r5.completed is True


# =====================================================================
# TEST 2 — SKIPPED STEP
# =====================================================================
def test_2_skipped_step():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_skip"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    # Step 1: PICK_TOOL -> VALID
    r1 = validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    assert r1.result == ValidationResult.VALID.value

    # Skip Step 2 and perform Step 3: TAKE_SAMPLE
    r2 = validator.validate_action("TAKE_SAMPLE", confidence=0.90, observed_objects=["sample"], session_id=session_id)
    assert r2.result == ValidationResult.STEP_SKIPPED.value
    assert r2.expected_step_number == 2
    assert r2.expected_step_code == "STEP_02"
    assert r2.expected_action == "OPEN_CONTAINER"
    assert r2.observed_action == "TAKE_SAMPLE"
    assert not r2.completed

    # State remains on OPEN_CONTAINER
    state = validator.get_state(session_id)
    assert state.current_step_number == 2
    assert state.expected_action == "OPEN_CONTAINER"


# =====================================================================
# TEST 3 — OUT OF SEQUENCE
# =====================================================================
def test_3_out_of_sequence():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_oos"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    # Step 1 -> Step 2
    validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    validator.validate_action("OPEN_CONTAINER", confidence=0.92, observed_objects=["container"], session_id=session_id)

    # Currently expecting Step 3 (TAKE_SAMPLE). Observed Step 1 (PICK_TOOL)
    r3 = validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    assert r3.result == ValidationResult.OUT_OF_SEQUENCE.value
    assert r3.expected_step_number == 3
    assert r3.expected_step_code == "STEP_03"
    assert r3.expected_action == "TAKE_SAMPLE"
    assert r3.observed_action == "PICK_TOOL"

    # State remains on TAKE_SAMPLE
    state = validator.get_state(session_id)
    assert state.current_step_number == 3
    assert state.expected_action == "TAKE_SAMPLE"


# =====================================================================
# TEST 4 — UNKNOWN ACTION
# =====================================================================
def test_4_unknown_action():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_unknown"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)

    # Unknown action not in protocol
    r_unk = validator.validate_action("DANCE_GESTURE", confidence=0.99, session_id=session_id)
    assert r_unk.result == ValidationResult.UNKNOWN_ACTION.value
    assert r_unk.expected_step_number == 2
    assert r_unk.expected_step_code == "STEP_02"
    assert r_unk.expected_action == "OPEN_CONTAINER"

    # State must not advance
    state = validator.get_state(session_id)
    assert state.current_step_number == 2


# =====================================================================
# TEST 5 — LOW CONFIDENCE
# =====================================================================
def test_5_low_confidence():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_low_conf"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    # Expected: PICK_TOOL, Observed: PICK_TOOL, Confidence: 0.40 < 0.70
    r_low = validator.validate_action("PICK_TOOL", confidence=0.40, observed_objects=["tool"], session_id=session_id)
    assert r_low.result == ValidationResult.VERIFY_REQUIRED.value
    assert r_low.expected_step_number == 1
    assert r_low.confidence == 0.40

    # State must not advance
    state = validator.get_state(session_id)
    assert state.current_step_number == 1


# =====================================================================
# TEST 6 — MISSING REQUIRED OBJECT
# =====================================================================
def test_6_missing_required_object():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_missing_obj"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    # Advance to step 3 (TAKE_SAMPLE, which requires ["sample"])
    validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    validator.validate_action("OPEN_CONTAINER", confidence=0.92, observed_objects=["container"], session_id=session_id)

    # Observed TAKE_SAMPLE with confidence 0.95, but missing observed objects []
    r_no_obj = validator.validate_action("TAKE_SAMPLE", confidence=0.95, observed_objects=[], session_id=session_id)
    assert r_no_obj.result == ValidationResult.VERIFY_REQUIRED.value
    assert "Required object 'sample' was not verified" in r_no_obj.message
    assert not r_no_obj.completed

    # State must not advance
    state = validator.get_state(session_id)
    assert state.current_step_number == 3


# =====================================================================
# TEST 7 — VALID OBJECT VERIFICATION
# =====================================================================
def test_7_valid_object_verification():
    validator = SequenceValidator(confidence_threshold=0.70)
    session_id = "test_valid_obj"
    validator.init_session_state(session_id, "exp_1", PROTOCOL_STEPS)

    # Advance to step 3
    validator.validate_action("PICK_TOOL", confidence=0.95, observed_objects=["tool"], session_id=session_id)
    validator.validate_action("OPEN_CONTAINER", confidence=0.92, observed_objects=["container"], session_id=session_id)

    # Valid TAKE_SAMPLE with observed_objects=["sample"]
    r_valid = validator.validate_action("TAKE_SAMPLE", confidence=0.95, observed_objects=["sample"], session_id=session_id)
    assert r_valid.result == ValidationResult.VALID.value
    assert r_valid.next_step_number == 4

    state = validator.get_state(session_id)
    assert state.current_step_number == 4


# =====================================================================
# TEST 8 — COMPLETION
# =====================================================================
def test_8_completion(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    res1 = experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    assert res1.result == ValidationResult.VALID.value

    res2 = experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.92, observed_objects=["container"])
    assert res2.result == ValidationResult.VALID.value

    res3 = experiment_service.validate_session_action(db_session, session.id, "TAKE_SAMPLE", confidence=0.91, observed_objects=["sample"])
    assert res3.result == ValidationResult.VALID.value

    res4 = experiment_service.validate_session_action(db_session, session.id, "PLACE_SAMPLE", confidence=0.94, observed_objects=["sample", "container"])
    assert res4.result == ValidationResult.VALID.value

    res5 = experiment_service.validate_session_action(db_session, session.id, "CLOSE_CONTAINER", confidence=0.98, observed_objects=["container"])
    assert res5.result == ValidationResult.EXPERIMENT_COMPLETE.value
    assert res5.completed is True

    # Database session state must be COMPLETED
    updated_session = SessionRepository.get_by_id(db_session, session.id)
    assert updated_session.status == "COMPLETED"


# =====================================================================
# TEST 9 — AFTER COMPLETION
# =====================================================================
def test_9_after_completion(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    # Complete all 5 steps
    experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.92, observed_objects=["container"])
    experiment_service.validate_session_action(db_session, session.id, "TAKE_SAMPLE", confidence=0.91, observed_objects=["sample"])
    experiment_service.validate_session_action(db_session, session.id, "PLACE_SAMPLE", confidence=0.94, observed_objects=["sample", "container"])
    experiment_service.validate_session_action(db_session, session.id, "CLOSE_CONTAINER", confidence=0.98, observed_objects=["container"])

    # Send another action after experiment completion
    res_after = experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    assert res_after.result == ValidationResult.EXPERIMENT_COMPLETE.value
    assert res_after.completed is True
    assert "already completed" in res_after.message

    # Session must remain COMPLETED and not restart
    sess = SessionRepository.get_by_id(db_session, session.id)
    assert sess.status == "COMPLETED"


# =====================================================================
# TEST 10 — STATE PERSISTENCE
# =====================================================================
def test_10_state_persistence(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    # Validate step 1
    res1 = experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    assert res1.result == ValidationResult.VALID.value

    # Recreate the validator instance to simulate restart
    new_validator = SequenceValidator(confidence_threshold=0.70)
    experiment_service.validator = new_validator

    # Next action must evaluate against Step 2 from the database
    res2 = experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.92, observed_objects=["container"])
    assert res2.result == ValidationResult.VALID.value
    assert res2.expected_step_number == 2
    assert res2.next_step_number == 3


# =====================================================================
# TEST 11 — EVENT STORAGE
# =====================================================================
def test_11_event_storage(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    experiment_service.validate_session_action(db_session, session.id, "TAKE_SAMPLE", confidence=0.90, observed_objects=["sample"])

    seq_events = EventRepository.get_session_events(db_session, session.id)
    assert len(seq_events) == 2

    # Event 1: VALID
    assert seq_events[0].expected_step_number == 1
    assert seq_events[0].observed_step_number == 1
    assert seq_events[0].result == "VALID"
    assert seq_events[0].confidence == 0.95

    # Event 2: STEP_SKIPPED
    assert seq_events[1].expected_step_number == 2
    assert seq_events[1].observed_step_number == 3
    assert seq_events[1].result == "STEP_SKIPPED"


# =====================================================================
# TEST 12 — ALERT STORAGE
# =====================================================================
def test_12_alert_storage(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    # Step 1: Valid (no error alert)
    experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])

    # Step 2: Skipped step (should create alert)
    experiment_service.validate_session_action(db_session, session.id, "TAKE_SAMPLE", confidence=0.90, observed_objects=["sample"])

    # Low confidence on OPEN_CONTAINER (should create LOW_CONFIDENCE alert)
    experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.40, observed_objects=["container"])

    # Unknown action (should create UNKNOWN_ACTION alert)
    experiment_service.validate_session_action(db_session, session.id, "UNKNOWN_ACTION", confidence=0.95)

    alerts = EventRepository.get_session_alerts(db_session, session.id)
    alert_types = [a.alert_type for a in alerts]

    assert "STEP_SKIPPED" in alert_types
    assert "LOW_CONFIDENCE" in alert_types
    assert "UNKNOWN_ACTION" in alert_types


# =====================================================================
# TEST 13 — VALID EVENTS DO NOT CREATE ERROR ALERTS
# =====================================================================
def test_13_valid_events_do_not_create_error_alerts(db_session):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    # Perform normal valid steps 1, 2, 3
    experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.92, observed_objects=["container"])
    experiment_service.validate_session_action(db_session, session.id, "TAKE_SAMPLE", confidence=0.91, observed_objects=["sample"])

    alerts = EventRepository.get_session_alerts(db_session, session.id)
    error_alerts = [a for a in alerts if a.alert_type in ("STEP_SKIPPED", "OUT_OF_SEQUENCE", "UNKNOWN_ACTION", "LOW_CONFIDENCE", "OBJECT_NOT_DETECTED")]
    assert len(error_alerts) == 0


# =====================================================================
# TEST 14 — RESET
# =====================================================================
def test_14_session_reset(db_session, client):
    exp = experiment_service.seed_default_experiment_if_empty(db_session)
    session = experiment_service.start_session(db_session, exp.id)

    # Advance to step 3
    experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    experiment_service.validate_session_action(db_session, session.id, "OPEN_CONTAINER", confidence=0.92, observed_objects=["container"])

    # Check session state before reset
    res_get = client.get(f"/api/sessions/{session.id}")
    assert res_get.status_code == 200
    assert res_get.json()["current_step_number"] == 3

    # Reset session via API
    res_reset = client.post(f"/api/sessions/{session.id}/reset")
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert reset_data["current_step_number"] == 1
    assert reset_data["current_step_code"] == "STEP_01"
    assert reset_data["status"] in ("ACTIVE", "RUNNING")

    # Verify SystemEvent was created
    sys_events = EventRepository.get_system_events(db_session)
    reset_events = [e for e in sys_events if e.event_type == "SESSION_RESET"]
    assert len(reset_events) > 0

    # Validate step 1 again after reset
    res_restarted = experiment_service.validate_session_action(db_session, session.id, "PICK_TOOL", confidence=0.95, observed_objects=["tool"])
    assert res_restarted.result == ValidationResult.VALID.value
    assert res_restarted.next_step_number == 2
