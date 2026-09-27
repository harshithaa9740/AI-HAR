"""
Step 8 Automated Test Suite: AI Inference Pipeline & Real Model Integration Layer
Comprehensive tests verifying:
- AIProvider interface contract and initialization
- MockAIProvider deterministic inference across simulation scenarios
- ObservedAction creation with object evidence preservation and honest confidence
- ModelRegistry provider registration, lookup, and metadata discovery
- InferenceEngine execution latency measurement (inference_time_ms)
- Error containment on invalid/null frames and missing providers
- Standalone /api/inference/frame endpoint
- Model metadata inspection endpoints /api/models and /api/models/active
- Session-scoped inference with validate=false (pure observation)
- Session-scoped inference with validate=true (observation + Sequence Validator protocol progression)
- Full end-to-end pipeline: Frame -> InferenceEngine -> ObservedAction -> SequenceValidator
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal, init_db
from app.core.constants import SessionStatus
from app.camera.frame_model import Frame
from app.camera.mock_camera import MockCameraSource
from app.camera.camera_manager import CameraManagerRegistry
from app.ml.model_provider import AIProvider
from app.ml.mock_provider import MockAIProvider
from app.ml.model_registry import ModelRegistry
from app.ml.inference_engine import InferenceEngine, inference_engine
from app.ml.exceptions import AIInferenceError, InvalidFrameError, ProviderUnavailableError
from app.schemas.detection import ObservedAction, DetectionResult
from app.services.session_service import session_service
from app.services.experiment_service import experiment_service
from app.services.sequence_validator import sequence_validator
from app.services.camera_service import camera_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Ensure clean test environment and reset registry/camera state."""
    init_db()
    CameraManagerRegistry.stop_all()
    ModelRegistry.reset()
    yield
    CameraManagerRegistry.stop_all()
    ModelRegistry.reset()


# ==============================================================================
# 1. AI Provider Interface & MockAIProvider Tests
# ==============================================================================

def test_mock_provider_initialization_and_metadata():
    """Test MockAIProvider initialization, is_ready status, and metadata reporting."""
    provider = MockAIProvider(scenario="NORMAL")
    assert not provider.is_ready()

    assert provider.initialize() is True
    assert provider.is_ready() is True

    info = provider.get_model_info()
    assert info["provider"] == "mock"
    assert info["task"] == "human_activity_recognition"
    assert info["status"] == "development/mock"
    assert info["device"] == "cpu"
    assert info["active_scenario"] == "NORMAL"

    provider.shutdown()
    assert not provider.is_ready()


def test_mock_provider_deterministic_inference():
    """Test deterministic action emission and object evidence for normal protocol sequence."""
    provider = MockAIProvider(scenario="NORMAL")
    provider.initialize()

    # Create dummy synthetic frames for step 1 to 5
    for expected_step, expected_action in [
        (1, "PICK_TOOL"),
        (2, "OPEN_CONTAINER"),
        (3, "TAKE_SAMPLE"),
        (4, "PLACE_SAMPLE"),
        (5, "CLOSE_CONTAINER")
    ]:
        frame = Frame(frame_index=expected_step, source_id="test-cam")
        res = provider.infer(frame)

        assert res["action_code"] == expected_action
        assert res["confidence"] > 0.8
        assert isinstance(res["observed_objects"], list)
        assert len(res["detections"]) >= 0

        # Verify DetectionResult objects
        for det in res["detections"]:
            assert isinstance(det, DetectionResult)
            assert det.confidence > 0.0
            assert det.bounding_box is not None


def test_mock_provider_scenarios():
    """Test scenario switching for SKIPPED_STEP, LOW_CONFIDENCE, and UNKNOWN_ACTION."""
    provider = MockAIProvider(scenario="SKIPPED_STEP")
    provider.initialize()

    # In SKIPPED_STEP, step 2 skips OPEN_CONTAINER and produces TAKE_SAMPLE
    frame_step2 = Frame(frame_index=2, metadata={"step_index": 2})
    res_skip = provider.infer(frame_step2)
    assert res_skip["action_code"] == "TAKE_SAMPLE"

    # LOW_CONFIDENCE scenario
    provider.set_scenario("LOW_CONFIDENCE")
    frame_step1 = Frame(frame_index=1, metadata={"step_index": 1})
    res_low = provider.infer(frame_step1)
    assert res_low["action_code"] == "PICK_TOOL"
    assert res_low["confidence"] < 0.60

    # UNKNOWN_ACTION scenario
    provider.set_scenario("UNKNOWN_ACTION")
    res_unk = provider.infer(frame_step1)
    assert res_unk["action_code"] == "UNKNOWN_ACTION_TEST"




# ==============================================================================
# 2. Model Registry Tests
# ==============================================================================

def test_model_registry_registration_and_lookup():
    """Test ModelRegistry provider registration, active provider selection, and listing."""
    mock_prov = MockAIProvider(scenario="NORMAL")
    ModelRegistry.register_provider("mock_custom", mock_prov)

    retrieved = ModelRegistry.get_provider("mock_custom")
    assert retrieved is mock_prov

    ModelRegistry.set_active_provider("mock_custom")
    active_info = ModelRegistry.get_active_model_info()
    assert active_info["provider"] == "mock"

    models_list = ModelRegistry.list_models()
    assert len(models_list) >= 1

    with pytest.raises(ProviderUnavailableError):
        ModelRegistry.get_provider("non_existent_yolo_provider")


# ==============================================================================
# 3. Inference Engine Tests (Timing, Normalization, Evidence)
# ==============================================================================

def test_inference_engine_execution_and_timing():
    """Test InferenceEngine execution, timing measurement, and ObservedAction formatting."""
    engine = InferenceEngine()

    raw_data = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = Frame(frame_id="frame-100", frame_index=1, data=raw_data, source_id="mock-src")

    observed_action, detections = engine.infer(frame, scenario_override="NORMAL")

    assert isinstance(observed_action, ObservedAction)
    assert observed_action.action_code == "PICK_TOOL"
    assert observed_action.confidence > 0.8
    assert "tool" in observed_action.observed_objects

    # Verify timing and metadata
    assert "inference_time_ms" in observed_action.metadata
    assert observed_action.metadata["inference_time_ms"] >= 0.0
    assert observed_action.metadata["source_frame_id"] == "frame-100"
    assert observed_action.metadata["model_name"] is not None

    assert len(detections) >= 1
    assert detections[0].class_name in observed_action.observed_objects


def test_inference_engine_invalid_frame_error():
    """Test that passing None frame raises InvalidFrameError."""
    engine = InferenceEngine()
    with pytest.raises(InvalidFrameError):
        engine.infer(None)


# ==============================================================================
# 4. REST API Endpoint Tests
# ==============================================================================

def test_api_standalone_frame_inference():
    """Test POST /api/inference/frame endpoint."""
    payload = {
        "scenario": "NORMAL",
        "step_index": 1
    }
    res = client.post("/api/inference/frame", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["action_code"] == "PICK_TOOL"
    assert data["confidence"] > 0.8
    assert "tool" in data["observed_objects"]
    assert "inference_time_ms" in data["metadata"]


def test_api_models_inspection_endpoints():
    """Test GET /api/models and GET /api/models/active endpoints."""
    res_active = client.get("/api/models/active")
    assert res_active.status_code == 200
    active_data = res_active.json()
    assert active_data["provider"] == "mock"
    assert active_data["status"] == "development/mock"

    res_list = client.get("/api/models")
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)


# ==============================================================================
# 5. Session-Scoped Inference & Optional Validation Tests
# ==============================================================================

def test_session_inference_without_validation():
    """Test POST /api/sessions/{id}/inference/frame with validate=false."""
    with SessionLocal() as db:
        from app.db.repository import get_experiment_by_name
        exp = get_experiment_by_name(db, "Sample Handling Protocol") or experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.start_session(db, experiment_id=exp.id)
        s_id = str(session.id)

    res = client.post(f"/api/sessions/{s_id}/inference/frame?validate=false")
    assert res.status_code == 200
    data = res.json()

    assert data["session_id"] == s_id
    assert data["observation"]["action_code"] == "PICK_TOOL"
    assert data["validation"] is None  # No validation when validate=false


def test_session_inference_with_validation_advances_step():
    """Test POST /api/sessions/{id}/inference/frame with validate=true advances protocol."""
    with SessionLocal() as db:
        from app.db.repository import get_experiment_by_name
        exp = get_experiment_by_name(db, "Sample Handling Protocol") or experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.start_session(db, experiment_id=exp.id)
        s_id = str(session.id)
        assert session.current_step_number == 1

    # Step 1: PICK_TOOL -> VALID, advances to Step 2
    res_1 = client.post(f"/api/sessions/{s_id}/inference/frame?validate=true", json={"scenario": "NORMAL"})
    assert res_1.status_code == 200
    data_1 = res_1.json()

    assert data_1["observation"]["action_code"] == "PICK_TOOL"
    assert data_1["validation"] is not None
    assert data_1["validation"]["result"] == "VALID"
    assert data_1["validation"]["next_step_number"] == 2

    # Verify session step advanced in DB
    with SessionLocal() as db:
        updated_sess = session_service.get_session(db, s_id)
        assert updated_sess.current_step_number == 2


def test_session_inference_stopped_session_error():
    """Test that stopped sessions reject frame inference with 400 Bad Request."""
    with SessionLocal() as db:
        from app.db.repository import get_experiment_by_name
        exp = get_experiment_by_name(db, "Sample Handling Protocol") or experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.start_session(db, experiment_id=exp.id)
        session_service.stop_session(db, session.id)
        s_id = str(session.id)

    res = client.post(f"/api/sessions/{s_id}/inference/frame")
    assert res.status_code == 400


# ==============================================================================
# 6. End-to-End Pipeline Bridge (Frame -> Inference -> Action -> Validator)
# ==============================================================================

def test_e2e_full_protocol_execution_through_inference_pipeline():
    """
    Simulate full astronaut experiment execution through the complete pipeline:
    Camera Frame -> InferenceEngine -> ObservedAction -> SequenceValidator -> Session Completion
    """
    with SessionLocal() as db:
        from app.db.repository import get_experiment_by_name
        exp = get_experiment_by_name(db, "Sample Handling Protocol") or experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.start_session(db, experiment_id=exp.id)
        steps = experiment_service.get_experiment_steps(db, exp.id)
        s_id = str(session.id)


    camera = MockCameraSource(source_id="astronaut-cam", width=640, height=480, fps=10)
    camera.open()
    engine = InferenceEngine()

    for step_num in range(1, 6):
        frame = camera.read_frame()
        assert frame is not None

        # 1. AI Inference
        action, detections = engine.infer(frame, scenario_override="NORMAL")
        assert action.confidence > 0.8

        # 2. Sequence Validation
        val_outcome = sequence_validator.validate_observation(
            observation=action,
            session_id=session.id,
            steps=steps
        )
        assert val_outcome.result in ("VALID", "EXPERIMENT_COMPLETE")

    # Final step should complete the experiment
    assert val_outcome.experiment_complete is True
    camera.release()
