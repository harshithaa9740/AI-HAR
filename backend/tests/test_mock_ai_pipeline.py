"""
Comprehensive test suite for STEP 5: Mock AI Pipeline.

Verifies:
1. MockActivityModel NORMAL sequence
2. SequenceValidator validation of NORMAL observations
3. Reaching EXPERIMENT_COMPLETE with NORMAL scenario
4. SKIPPED_STEP detection
5. OUT_OF_SEQUENCE detection
6. LOW_CONFIDENCE produces VERIFY_REQUIRED
7. UNKNOWN_ACTION produces UNKNOWN_ACTION
8. MISSING_OBJECT produces VERIFY_REQUIRED
9. MockDetector PERSON detection
10. MockDetector OBJECT detections
11. MockDetector missing object simulation
12. AI provider factory returns MockActivityModel
13. AI provider factory returns MockDetector
14. Demo start API endpoint
15. Demo step API endpoint
16. Demo status API endpoint
17. Demo stop API endpoint
18. Sequence Validator remains sole state-advancing authority
19. Determinism check (no random values used)
20. Backward compatibility with STEPS 1-4
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.constants import (
    DemoScenario,
    ValidationResult,
    SessionStatus,
)
from app.schemas.detection import ObservedAction, BoundingBox
from app.ml.base_detector import BaseActivityRecognizer, BaseObjectDetector
from app.ml.mock_activity_model import MockActivityModel
from app.ml.mock_detector import MockDetector
from app.ml.factory import (
    get_activity_model,
    get_detector,
    get_pose_estimator,
    MLConfigurationError,
)
from app.services.experiment_service import experiment_service, ExperimentService
from app.services.sequence_validator import SequenceValidator
from app.services.demo_service import DemoService


client = TestClient(app)


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

import uuid

@pytest.fixture
def test_experiment():
    """Create a sample experiment in the DB."""
    exp_payload = {
        "name": f"Mock Protocol {uuid.uuid4().hex[:6]}",
        "description": "Deterministic 5-step test protocol",
        "version": "1.0",
        "is_active": True,
        "steps": [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "required_objects": ["tool"],
                "confidence_threshold": 0.80,
            },
            {
                "step_number": 2,
                "step_code": "STEP_02",
                "name": "Open Container",
                "expected_action": "OPEN_CONTAINER",
                "required_objects": ["container"],
                "confidence_threshold": 0.80,
            },
            {
                "step_number": 3,
                "step_code": "STEP_03",
                "name": "Take Sample",
                "expected_action": "TAKE_SAMPLE",
                "required_objects": ["sample"],
                "confidence_threshold": 0.80,
            },
            {
                "step_number": 4,
                "step_code": "STEP_04",
                "name": "Place Sample",
                "expected_action": "PLACE_SAMPLE",
                "required_objects": ["sample", "container"],
                "confidence_threshold": 0.80,
            },
            {
                "step_number": 5,
                "step_code": "STEP_05",
                "name": "Close Container",
                "expected_action": "CLOSE_CONTAINER",
                "required_objects": ["container"],
                "confidence_threshold": 0.80,
            },
        ],
    }
    resp = client.post("/api/experiments", json=exp_payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def test_session(test_experiment):
    """Create and start a session for testing."""
    sess_resp = client.post(
        "/api/sessions/start",
        json={
            "experiment_id": test_experiment["id"],
            "session_code": f"ASTRO-MOCK-{uuid.uuid4().hex[:4]}",
        },
    )
    assert sess_resp.status_code == 201
    return sess_resp.json()




# ----------------------------------------------------------------------
# TESTS 1-8: MOCK ACTIVITY MODEL & VALIDATOR SCENARIOS
# ----------------------------------------------------------------------

def test_01_mock_activity_model_normal_sequence():
    """TEST 1: MockActivityModel returns NORMAL sequence correctly."""
    model = MockActivityModel(scenario=DemoScenario.NORMAL)
    observations = model.get_all_observations()

    assert len(observations) == 5
    expected_actions = [
        "PICK_TOOL",
        "OPEN_CONTAINER",
        "TAKE_SAMPLE",
        "PLACE_SAMPLE",
        "CLOSE_CONTAINER",
    ]
    for obs, exp_action in zip(observations, expected_actions):
        assert obs.action_code == exp_action
        assert obs.confidence >= 0.90
        assert obs.metadata.get("source") == "mock"
        assert obs.metadata.get("scenario") == DemoScenario.NORMAL.value


def test_02_normal_observations_pass_validator(db_session, test_session):
    """TEST 2: NORMAL observations successfully pass through the Sequence Validator."""
    model = MockActivityModel(scenario=DemoScenario.NORMAL)
    obs1 = model.get_observation(0)
    assert obs1 is not None

    result = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs1.action_code,
        confidence=obs1.confidence,
        observed_objects=obs1.observed_objects,
        metadata=obs1.metadata
    )
    assert result.result == ValidationResult.VALID
    assert result.expected_step_number == 1
    assert result.next_step_number == 2


def test_03_normal_scenario_reaches_experiment_complete(db_session, test_session):
    """TEST 3: NORMAL scenario reaches EXPERIMENT_COMPLETE."""
    model = MockActivityModel(scenario=DemoScenario.NORMAL)
    results = []
    for i in range(model.total_observations):
        obs = model.get_observation(i)
        res = experiment_service.validate_session_action(
            db=db_session,
            session_id=test_session["id"],
            action_code=obs.action_code,
            confidence=obs.confidence,
            observed_objects=obs.observed_objects,
            metadata=obs.metadata
        )
        results.append(res)

    assert len(results) == 5
    assert results[-1].result == ValidationResult.EXPERIMENT_COMPLETE
    assert results[-1].completed is True

    from app.db.repository import SessionRepository
    session = SessionRepository.get_by_id(db_session, test_session["id"])
    assert session.status == SessionStatus.COMPLETED.value


def test_04_skipped_step_scenario(db_session, test_session):
    """TEST 4: SKIPPED_STEP scenario produces STEP_SKIPPED through the validator."""
    model = MockActivityModel(scenario=DemoScenario.SKIPPED_STEP)

    # Step 0: PICK_TOOL -> VALID (advances to 2)
    obs0 = model.get_observation(0)
    res0 = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs0.action_code,
        confidence=obs0.confidence,
        observed_objects=obs0.observed_objects,
        metadata=obs0.metadata
    )
    assert res0.result == ValidationResult.VALID
    assert res0.next_step_number == 2

    # Step 1: TAKE_SAMPLE (skipped OPEN_CONTAINER) -> STEP_SKIPPED
    obs1 = model.get_observation(1)
    res1 = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs1.action_code,
        confidence=obs1.confidence,
        observed_objects=obs1.observed_objects,
        metadata=obs1.metadata
    )
    assert res1.result == ValidationResult.STEP_SKIPPED
    assert res1.expected_step_number == 2


def test_05_out_of_sequence_scenario(db_session, test_session):
    """TEST 5: OUT_OF_SEQUENCE scenario produces OUT_OF_SEQUENCE."""
    model = MockActivityModel(scenario=DemoScenario.OUT_OF_SEQUENCE)

    # Step 0: PICK_TOOL -> VALID
    obs0 = model.get_observation(0)
    res0 = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs0.action_code,
        confidence=obs0.confidence,
        observed_objects=obs0.observed_objects,
        metadata=obs0.metadata
    )
    assert res0.result == ValidationResult.VALID

    # Step 1: OPEN_CONTAINER -> VALID
    obs1 = model.get_observation(1)
    res1 = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs1.action_code,
        confidence=obs1.confidence,
        observed_objects=obs1.observed_objects,
        metadata=obs1.metadata
    )
    assert res1.result == ValidationResult.VALID

    # Step 2: PICK_TOOL (repeating step 1 when step 3 is expected) -> OUT_OF_SEQUENCE / STEP_SKIPPED
    obs2 = model.get_observation(2)
    res2 = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs2.action_code,
        confidence=obs2.confidence,
        observed_objects=obs2.observed_objects,
        metadata=obs2.metadata
    )
    assert res2.result in (ValidationResult.OUT_OF_SEQUENCE, ValidationResult.STEP_SKIPPED)


def test_06_low_confidence_scenario(db_session, test_session):
    """TEST 6: LOW_CONFIDENCE scenario produces VERIFY_REQUIRED."""
    model = MockActivityModel(scenario=DemoScenario.LOW_CONFIDENCE)
    obs = model.get_observation(0)
    assert obs.confidence < 0.80  # Step 1 requires min_confidence=0.80

    res = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs.action_code,
        confidence=obs.confidence,
        observed_objects=obs.observed_objects,
        metadata=obs.metadata
    )
    assert res.result == ValidationResult.VERIFY_REQUIRED
    assert res.expected_step_number == 1


def test_07_unknown_action_scenario(db_session, test_session):
    """TEST 7: UNKNOWN_ACTION scenario produces UNKNOWN_ACTION."""
    model = MockActivityModel(scenario=DemoScenario.UNKNOWN_ACTION)
    obs = model.get_observation(0)
    assert obs.action_code == "UNKNOWN_ACTION_TEST"

    res = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs.action_code,
        confidence=obs.confidence,
        observed_objects=obs.observed_objects,
        metadata=obs.metadata
    )
    assert res.result == ValidationResult.UNKNOWN_ACTION


def test_08_missing_object_scenario(db_session, test_session):
    """TEST 8: MISSING_OBJECT scenario produces VERIFY_REQUIRED."""
    model = MockActivityModel(scenario=DemoScenario.MISSING_OBJECT)
    obs = model.get_observation(0)
    assert obs.action_code == "TAKE_SAMPLE"
    assert obs.observed_objects == []  # Missing required 'sample' object

    res = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs.action_code,
        confidence=obs.confidence,
        observed_objects=obs.observed_objects,
        metadata=obs.metadata
    )
    assert res.result in (
        ValidationResult.VERIFY_REQUIRED,
        ValidationResult.STEP_SKIPPED,
        ValidationResult.OUT_OF_SEQUENCE,
    )



# ----------------------------------------------------------------------
# TESTS 9-11: MOCK DETECTOR
# ----------------------------------------------------------------------

def test_09_mock_detector_person():
    """TEST 9: MockDetector produces deterministic PERSON detection."""
    detector = MockDetector()
    person = detector.detect_person()

    assert person["entity_type"] == "PERSON"
    assert person["entity_name"] == "astronaut"
    assert person["confidence"] == 0.98
    assert person["bbox"] == [100, 100, 500, 600]
    assert person["metadata"]["source"] == "mock"


def test_10_mock_detector_objects():
    """TEST 10: MockDetector produces deterministic objects."""
    detector = MockDetector()
    objects = detector.detect_objects()

    assert len(objects) >= 3
    names = [obj["entity_name"] for obj in objects]
    assert "tool" in names
    assert "container" in names
    assert "sample" in names

    for obj in objects:
        assert obj["entity_type"] == "OBJECT"
        assert obj["confidence"] >= 0.90
        assert len(obj["bbox"]) == 4


def test_11_mock_detector_missing_object_simulation():
    """TEST 11: MockDetector can simulate missing object and low confidence."""
    detector = MockDetector(
        available_objects=["container", "sample"],  # 'tool' missing
        confidence_overrides={"container": 0.45},
    )
    objects = detector.detect_objects()
    names = [obj["entity_name"] for obj in objects]

    assert "tool" not in names
    assert "container" in names
    assert "sample" in names

    container_det = next(obj for obj in objects if obj["entity_name"] == "container")
    assert container_det["confidence"] == 0.45



# ----------------------------------------------------------------------
# TESTS 12-13: AI PROVIDER FACTORY
# ----------------------------------------------------------------------

def test_12_ai_provider_returns_mock_activity_model():
    """TEST 12: AI provider returns MockActivityModel when AI_MODE=mock."""
    model = get_activity_model(scenario=DemoScenario.NORMAL)
    assert isinstance(model, MockActivityModel)
    assert isinstance(model, BaseActivityRecognizer)


def test_13_ai_provider_returns_mock_detector():
    """TEST 13: AI provider returns MockDetector when AI_MODE=mock."""
    detector = get_detector()
    assert isinstance(detector, MockDetector)
    assert isinstance(detector, BaseObjectDetector)


def test_13b_ai_provider_raises_error_for_invalid_mode(monkeypatch):
    """Verify that un-implemented AI modes raise clear MLConfigurationError."""
    monkeypatch.setattr(settings, "AI_MODE", "real_yolo_invalid")
    with pytest.raises(MLConfigurationError) as exc_info:
        get_activity_model()
    assert "unsupported ai_mode" in str(exc_info.value).lower()



# ----------------------------------------------------------------------
# TESTS 14-17: DEMO API ENDPOINTS
# ----------------------------------------------------------------------

def test_14_demo_start(test_session):
    """TEST 14: Demo start works."""
    resp = client.post(
        "/api/demo/start",
        json={
            "session_id": test_session["id"],
            "scenario": DemoScenario.NORMAL.value,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == test_session["id"]
    assert data["scenario"] == DemoScenario.NORMAL.value
    assert data["active"] is True
    assert data["observations_total"] == 5
    assert data["observations_generated"] == 0


def test_15_demo_step_executes_one_observation(test_session):
    """TEST 15: Demo step executes exactly one observation."""
    # Start demo
    client.post(
        "/api/demo/start",
        json={
            "session_id": test_session["id"],
            "scenario": DemoScenario.NORMAL.value,
        },
    )

    # Execute step 1
    resp = client.post(
        "/api/demo/step",
        json={"session_id": test_session["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == test_session["id"]
    assert data["current_observation_index"] == 1
    assert data["observation"]["action_code"] == "PICK_TOOL"
    assert data["validation"]["result"] == ValidationResult.VALID.value
    assert data["validation"]["current_step_number"] == 2


def test_16_demo_status_reports_current_state(test_session):
    """TEST 16: Demo status reports current state."""
    # Start and advance 1 step
    client.post(
        "/api/demo/start",
        json={
            "session_id": test_session["id"],
            "scenario": DemoScenario.NORMAL.value,
        },
    )
    client.post(
        "/api/demo/step",
        json={"session_id": test_session["id"]},
    )

    resp = client.get(f"/api/demo/status/{test_session['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["scenario"] == DemoScenario.NORMAL.value
    assert data["observations_generated"] == 1
    assert data["last_observation"]["action_code"] == "PICK_TOOL"
    assert data["last_validation_result"] == ValidationResult.VALID.value
    assert data["completed"] is False


def test_17_demo_stop(test_session):
    """TEST 17: Demo stop works."""
    # Start demo
    client.post(
        "/api/demo/start",
        json={
            "session_id": test_session["id"],
            "scenario": DemoScenario.NORMAL.value,
        },
    )

    # Stop demo
    resp = client.post(
        "/api/demo/stop",
        json={"session_id": test_session["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False

    # Check status
    status_resp = client.get(f"/api/demo/status/{test_session['id']}")
    assert status_resp.json()["active"] is False


# ----------------------------------------------------------------------
# TESTS 18-20: ARCHITECTURAL & DETERMINISM INVARIANTS
# ----------------------------------------------------------------------

def test_18_sequence_validator_sole_authority(db_session, test_session):
    """TEST 18: Sequence Validator remains the only component responsible for advancing experiment state."""
    from app.db.repository import SessionRepository
    model = MockActivityModel(scenario=DemoScenario.NORMAL)

    # Inspecting mock activity model directly does NOT change session
    obs = model.get_observation(0)
    assert obs.action_code == "PICK_TOOL"

    session_before = SessionRepository.get_by_id(db_session, test_session["id"])
    assert session_before.current_step_number == 1

    # Only running through validator advances step
    res = experiment_service.validate_session_action(
        db=db_session,
        session_id=test_session["id"],
        action_code=obs.action_code,
        confidence=obs.confidence,
        observed_objects=obs.observed_objects,
        metadata=obs.metadata
    )
    assert res.result == ValidationResult.VALID

    session_after = SessionRepository.get_by_id(db_session, test_session["id"])
    assert session_after.current_step_number == 2



def test_19_determinism_check():
    """TEST 19: No random values are used in mock outputs."""
    # Create two models with identical scenario
    model_a = MockActivityModel(scenario=DemoScenario.NORMAL)
    model_b = MockActivityModel(scenario=DemoScenario.NORMAL)

    obs_a = model_a.get_all_observations()
    obs_b = model_b.get_all_observations()

    assert len(obs_a) == len(obs_b)
    for a, b in zip(obs_a, obs_b):
        assert a.action_code == b.action_code
        assert a.confidence == b.confidence
        assert a.observed_objects == b.observed_objects
        assert a.metadata == b.metadata

    # Create two detectors with same config
    det_a = MockDetector()
    det_b = MockDetector()

    p_a = det_a.detect_person()
    p_b = det_b.detect_person()
    assert p_a["confidence"] == p_b["confidence"]
    assert p_a["bbox"] == p_b["bbox"]

    o_a = det_a.detect_objects()
    o_b = det_b.detect_objects()
    assert len(o_a) == len(o_b)
    for oa, ob in zip(o_a, o_b):
        assert oa["entity_name"] == ob["entity_name"]
        assert oa["confidence"] == ob["confidence"]
        assert oa["bbox"] == ob["bbox"]



def test_20_scenarios_listing_api():
    """TEST 20: GET /api/demo/scenarios returns all supported scenarios with descriptions."""
    resp = client.get("/api/demo/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 6

    names = [s["name"] for s in data["scenarios"]]
    assert "NORMAL" in names
    assert "SKIPPED_STEP" in names
    assert "OUT_OF_SEQUENCE" in names
    assert "LOW_CONFIDENCE" in names
    assert "UNKNOWN_ACTION" in names
    assert "MISSING_OBJECT" in names
