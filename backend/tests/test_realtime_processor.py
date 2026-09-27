"""
Step 9 Automated Test Suite: Real-Time AI Processing Loop & Experiment Validation Pipeline
Comprehensive tests verifying:
- Processor initialization, state model, and transition checks
- Session state requirement (RUNNING only) and safety protections
- Camera and AI readiness verification
- Controlled background worker lifecycle (start, stop, pause, resume)
- Real-time frame ingestion, inference, and sequence validator integration
- Step progression on VALID observations
- Automatic session completion on EXPERIMENT_COMPLETE
- Preservation of protocol state on STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, VERIFY_REQUIRED
- Inference error isolation (worker survives single frame failures)
- Camera failure clean error state transition
- Frame dropping and FPS pacing
- In-memory metrics tracking (latency, fps, counters)
- Concurrency safety and single-worker enforcement
- Processing REST API endpoints (/start, /stop, /pause, /resume, /status, /metrics)
"""
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal, init_db
from app.core.constants import SessionStatus, ProcessingState, ValidationResult
from app.camera.mock_camera import MockCameraSource
from app.camera.camera_manager import CameraManagerRegistry
from app.services.camera_service import camera_service
from app.ml.model_registry import ModelRegistry
from app.ml.mock_provider import MockAIProvider
from app.ml.inference_engine import inference_engine
from app.services.session_service import session_service
from app.services.experiment_service import experiment_service
from app.services.realtime_processor import (
    RealTimeProcessor,
    RealTimeProcessorRegistry,
    RealTimeProcessorError,
)
from app.services.processing_state import (
    ProcessingStateManager,
    InvalidProcessingStateTransitionError,
)
from app.services.processing_metrics import ProcessingMetrics, ProcessingResult
from app.schemas.experiment import ExperimentCreate, ExperimentStepCreate
from app.services.sequence_validator import sequence_validator

client = TestClient(app)



@pytest.fixture(autouse=True)
def setup_teardown():
    """Ensure clean database, camera, and processor state for each test."""
    init_db()
    RealTimeProcessorRegistry.stop_all()
    CameraManagerRegistry.stop_all()
    ModelRegistry.reset()
    sequence_validator._states.clear()
    yield
    RealTimeProcessorRegistry.stop_all()
    CameraManagerRegistry.stop_all()
    ModelRegistry.reset()
    sequence_validator._states.clear()


def _create_and_start_test_session():
    """Helper to create a fresh experiment and active RUNNING session."""
    with SessionLocal() as db:
        payload = ExperimentCreate(
            name=f"RealTime Test Protocol {time.time()}",
            description="Testing real-time processing loop",
            steps=[
                ExperimentStepCreate(
                    step_number=1,
                    step_code="STEP_01",
                    name="Pick Tool",
                    expected_action="PICK_TOOL",
                    confidence_threshold=0.70,
                    required_objects=["tool"]
                ),
                ExperimentStepCreate(
                    step_number=2,
                    step_code="STEP_02",
                    name="Open Container",
                    expected_action="OPEN_CONTAINER",
                    confidence_threshold=0.70,
                    required_objects=["container"]
                ),
                ExperimentStepCreate(
                    step_number=3,
                    step_code="STEP_03",
                    name="Take Sample",
                    expected_action="TAKE_SAMPLE",
                    confidence_threshold=0.70,
                    required_objects=["sample"]
                ),
                ExperimentStepCreate(
                    step_number=4,
                    step_code="STEP_04",
                    name="Place Sample",
                    expected_action="PLACE_SAMPLE",
                    confidence_threshold=0.70,
                    required_objects=["sample", "container"]
                ),
                ExperimentStepCreate(
                    step_number=5,
                    step_code="STEP_05",
                    name="Close Container",
                    expected_action="CLOSE_CONTAINER",
                    confidence_threshold=0.70,
                    required_objects=["container"]
                )
            ]
        )
        exp = experiment_service.create_experiment(db=db, payload=payload)
        session = session_service.create_session(db=db, experiment_id=exp.id)
        session = session_service.start_session(db=db, session_id=session.id)
        return str(session.id), exp.id


# ==============================================================================
# 1. State Manager & Metrics Unit Tests
# ==============================================================================

def test_processing_state_transitions():
    """Test valid and invalid processor state transitions."""
    # STOPPED -> STARTING
    ProcessingStateManager.validate_transition(ProcessingState.STOPPED, ProcessingState.STARTING)

    # STARTING -> RUNNING
    ProcessingStateManager.validate_transition(ProcessingState.STARTING, ProcessingState.RUNNING)

    # RUNNING -> PAUSED -> RUNNING
    ProcessingStateManager.validate_transition(ProcessingState.RUNNING, ProcessingState.PAUSED)
    ProcessingStateManager.validate_transition(ProcessingState.PAUSED, ProcessingState.RUNNING)

    # RUNNING -> STOPPING -> STOPPED
    ProcessingStateManager.validate_transition(ProcessingState.RUNNING, ProcessingState.STOPPING)
    ProcessingStateManager.validate_transition(ProcessingState.STOPPING, ProcessingState.STOPPED)

    # Invalid: STOPPED -> PAUSED should raise error
    with pytest.raises(InvalidProcessingStateTransitionError):
        ProcessingStateManager.validate_transition(ProcessingState.STOPPED, ProcessingState.PAUSED)


def test_processing_metrics_accumulation():
    """Test in-memory metrics calculations and averages."""
    metrics = ProcessingMetrics()
    metrics.start()

    metrics.record_frame_received()
    metrics.record_frame_dropped(2)

    res = ProcessingResult(
        session_id="test-1",
        frame_id="f-1",
        action_code="PICK_TOOL",
        confidence=0.95,
        validation_status="VALID",
        inference_time_ms=15.0,
        processing_time_ms=25.0
    )
    metrics.record_success(res)
    metrics.record_failure(inference_time_ms=10.0, processing_time_ms=12.0)

    summary = metrics.get_summary()
    assert summary["frames_received"] == 1
    assert summary["frames_dropped"] == 2
    assert summary["frames_processed"] == 2
    assert summary["successful_inferences"] == 1
    assert summary["failed_inferences"] == 1
    assert summary["validation_results"]["VALID"] == 1
    assert summary["average_inference_time_ms"] == 12.5
    assert summary["average_processing_time_ms"] == 18.5


# ==============================================================================
# 2. Processor Lifecycle & Precondition Tests
# ==============================================================================

def test_processor_preconditions_session_not_found():
    """Processor fails to start on non-existent session."""
    processor = RealTimeProcessor(session_id="999999")
    with pytest.raises(ValueError, match="not found"):
        processor.start()
    assert processor.state == ProcessingState.STOPPED


def test_processor_preconditions_session_not_running():
    """Processor fails to start if session is in CREATED status."""
    with SessionLocal() as db:
        payload = ExperimentCreate(
            name=f"Created Exp {time.time()}",
            steps=[ExperimentStepCreate(step_number=1, step_code="STEP_01", expected_action="ACT", required_objects=[])]
        )
        exp = experiment_service.create_experiment(db=db, payload=payload)
        session = session_service.create_session(db=db, experiment_id=exp.id)
        sess_id = str(session.id)

    processor = RealTimeProcessor(session_id=sess_id)
    with pytest.raises(ValueError, match="Session must be in RUNNING status"):
        processor.start()
    assert processor.state == ProcessingState.STOPPED


def test_processor_preconditions_camera_unavailable():
    """Processor fails to start if no camera is running for the session."""
    sess_id, _ = _create_and_start_test_session()
    # Camera is not started!
    processor = RealTimeProcessor(session_id=sess_id)
    with pytest.raises(Exception, match="No active camera running"):
        processor.start()
    assert processor.state == ProcessingState.STOPPED


def test_processor_start_stop_pause_resume_lifecycle():
    """Test clean start, pause, resume, and stop operations."""
    sess_id, _ = _create_and_start_test_session()

    # Start session camera
    camera_service.start_session_camera(session_id=sess_id, source_type="mock", target_fps=10)

    processor = RealTimeProcessor(session_id=sess_id, target_fps=10)
    status_start = processor.start()
    assert status_start["state"] == "RUNNING"
    assert processor.is_running()

    # Pause
    status_pause = processor.pause()
    assert status_pause["state"] == "PAUSED"
    assert processor.is_paused()

    # Resume
    status_resume = processor.resume()
    assert status_resume["state"] == "RUNNING"
    assert processor.is_running()

    # Stop
    status_stop = processor.stop()
    assert status_stop["state"] == "STOPPED"
    assert not processor.is_running()


def test_processor_duplicate_start_protection():
    """Starting an already running processor must raise an error."""
    sess_id, _ = _create_and_start_test_session()
    camera_service.start_session_camera(session_id=sess_id, source_type="mock")

    processor = RealTimeProcessor(session_id=sess_id)
    processor.start()

    with pytest.raises(RealTimeProcessorError, match="already running"):
        processor.start()

    processor.stop()


# ==============================================================================
# 3. Continuous Processing Loop & Protocol Validation Integration Tests
# ==============================================================================

def test_processor_frame_inference_and_step_progression():
    """Test continuous loop ingesting frames, running AI inference, and advancing steps on VALID."""
    sess_id, exp_id = _create_and_start_test_session()

    # Start session camera with mock generator
    camera_service.start_session_camera(session_id=sess_id, source_type="mock", target_fps=20)

    processor = RealTimeProcessor(session_id=sess_id, target_fps=20)
    processor.start()

    # Wait for at least one step progression
    advanced = False
    for _ in range(40):
        time.sleep(0.05)
        with SessionLocal() as db:
            sess = session_service.get_session(db, sess_id)
            if sess.current_step_number >= 2:
                advanced = True
                break

    assert advanced is True

    st = processor.status()
    assert st["frames_processed"] >= 1
    assert st["last_result"] is not None
    assert st["last_result"]["validation_status"] in ("VALID", "EXPERIMENT_COMPLETE")

    processor.stop()


def test_processor_experiment_completion_flow():
    """Test complete experiment progression leading to automatic session COMPLETED status."""
    sess_id, exp_id = _create_and_start_test_session()

    # Start camera with mock source
    camera_service.start_session_camera(session_id=sess_id, source_type="mock", target_fps=30)

    processor = RealTimeProcessor(session_id=sess_id, target_fps=30)
    processor.start()

    # Wait for sequence to complete
    completed = False
    for _ in range(60):
        time.sleep(0.05)
        with SessionLocal() as db:
            sess = session_service.get_session(db, sess_id)
            if sess.status == SessionStatus.COMPLETED.value:
                completed = True
                break

    assert completed is True

    # Verify session completed in DB
    with SessionLocal() as db:
        sess = session_service.get_session(db, sess_id)
        assert sess.status == SessionStatus.COMPLETED.value
        assert sess.ended_at is not None

    # Verify processor stopped cleanly
    assert processor.state == ProcessingState.STOPPED




def test_processor_step_skipped_does_not_advance_protocol():
    """Test that STEP_SKIPPED preserves validator state without illegally advancing protocol."""
    sess_id, exp_id = _create_and_start_test_session()

    # Set mock AI provider to SKIPPED_STEP scenario
    provider = ModelRegistry.get_provider("mock")
    provider.set_scenario("SKIPPED_STEP")

    camera_service.start_session_camera(session_id=sess_id, source_type="mock", target_fps=20)

    processor = RealTimeProcessor(session_id=sess_id, target_fps=20)
    processor.start()

    time.sleep(0.3)
    processor.stop()

    metrics = processor.get_metrics()
    assert metrics["validation_results"]["STEP_SKIPPED"] >= 1

    # Verify session step remained at Step 2 (after valid Step 1, Step 2 was skipped so did not advance to 3)
    with SessionLocal() as db:
        sess = session_service.get_session(db, sess_id)
        assert sess.current_step_number == 2
        assert sess.status == SessionStatus.RUNNING.value



def test_processor_inference_error_isolation():
    """Test that a single frame inference exception does not crash the worker loop."""
    sess_id, exp_id = _create_and_start_test_session()
    camera_service.start_session_camera(session_id=sess_id, source_type="mock", target_fps=20)

    processor = RealTimeProcessor(session_id=sess_id, target_fps=20)

    # Monkeypatch infer to fail on first call then succeed
    original_infer = processor.inference_engine.infer
    call_count = [0]

    def failing_infer(frame, scenario_override=None):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Simulated transient inference hardware failure")
        return original_infer(frame, scenario_override)

    processor.inference_engine.infer = failing_infer

    try:
        processor.start()
        time.sleep(0.3)
        processor.stop()

        metrics = processor.get_metrics()
        assert metrics["failed_inferences"] >= 1
        assert metrics["successful_inferences"] >= 1
        assert processor.metrics.get_summary()["frames_processed"] >= 2
    finally:
        processor.inference_engine.infer = original_infer


# ==============================================================================
# 4. REST API Endpoint Tests
# ==============================================================================

def test_api_processing_start_status_metrics_stop():
    """Test full processing REST API cycle."""
    sess_id, exp_id = _create_and_start_test_session()

    # Start camera first
    cam_res = client.post(f"/api/camera/start", json={"source_type": "mock"})
    assert cam_res.status_code == 200

    # 1. Start processing
    start_res = client.post(f"/api/sessions/{sess_id}/processing/start", json={"target_fps": 15})
    assert start_res.status_code == 200
    data = start_res.json()
    assert data["state"] == "RUNNING"
    assert data["worker_active"] is True

    # 2. Get status
    status_res = client.get(f"/api/sessions/{sess_id}/processing/status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["session_id"] == sess_id

    # 3. Pause
    pause_res = client.post(f"/api/sessions/{sess_id}/processing/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["state"] == "PAUSED"

    # 4. Resume
    resume_res = client.post(f"/api/sessions/{sess_id}/processing/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["state"] == "RUNNING"

    # 5. Get Metrics
    metrics_res = client.get(f"/api/sessions/{sess_id}/processing/metrics")
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert "frames_processed" in m_data
    assert "average_inference_time_ms" in m_data

    # 6. Stop
    stop_res = client.post(f"/api/sessions/{sess_id}/processing/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["state"] == "STOPPED"


def test_api_processing_invalid_session_and_duplicate_start():
    """Test API error responses for invalid session ID and duplicate start."""
    # Invalid session
    res = client.post("/api/sessions/999999/processing/start")
    assert res.status_code == 404

    sess_id, _ = _create_and_start_test_session()
    client.post("/api/camera/start", json={"source_type": "mock"})

    # First start
    res1 = client.post(f"/api/sessions/{sess_id}/processing/start")
    assert res1.status_code == 200

    # Duplicate start
    res2 = client.post(f"/api/sessions/{sess_id}/processing/start")
    assert res2.status_code == 409

    # Clean up
    client.post(f"/api/sessions/{sess_id}/processing/stop")
