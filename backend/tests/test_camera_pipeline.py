"""
Step 7 Automated Test Suite: Real-Time Frame Ingestion & Camera Pipeline
Comprehensive tests verifying:
- MockCameraSource deterministic frame generation, IDs, timestamps, indexing
- VideoFileSource local offline playback, looping, and missing file error handling
- RealCameraSource graceful failure containment when hardware is absent
- FrameProcessor validation, resizing, normalization, and indexing
- CameraManager lifecycle (STARTING, RUNNING, PAUSED, STOPPED, ERROR), thread execution, and FPS pacing
- Bounded Ring Buffer (FRAME_BUFFER_SIZE), newest-frame preference, overflow safety
- Session-scoped Camera isolation and lifecycle synchronization (pause/resume/stop)
- SystemEvent persistence for camera lifecycle transitions
- REST API endpoints for global and session camera controls
- Future AI pipeline interface compatibility (Frame -> MockFrameInferenceEngine -> ObservedAction -> SequenceValidator)
"""
import time
import pytest
import numpy as np
import tempfile
import cv2
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal, init_db
from app.core.constants import SessionStatus, EventType, AlertSeverity
from app.camera.frame_model import Frame
from app.camera.camera_source import CameraSource
from app.camera.mock_camera import MockCameraSource
from app.camera.video_file_source import VideoFileSource
from app.camera.real_camera import RealCameraSource
from app.camera.frame_processor import FrameProcessor
from app.camera.camera_manager import CameraManager, CameraState, CameraManagerRegistry
from app.camera.exceptions import (
    CameraAlreadyRunningError,
    CameraStoppedError,
    CameraSourceError,
    InvalidVideoFileError,
)
from app.services.camera_service import camera_service
from app.services.session_service import session_service
from app.services.experiment_service import experiment_service
from app.services.event_service import event_service
from app.ml.frame_inference_interface import MockFrameInferenceEngine
from app.services.sequence_validator import sequence_validator


@pytest.fixture(autouse=True)
def clean_test_env():
    """Ensure database is initialized and all active camera managers are stopped."""
    init_db()
    CameraManagerRegistry.stop_all()
    yield
    CameraManagerRegistry.stop_all()


# ==============================================================================
# 1. MockCameraSource Tests
# ==============================================================================

def test_mock_camera_startup_and_properties():
    """Test MockCameraSource initialization, open, properties, and release."""
    mock_cam = MockCameraSource(source_id="test-mock", width=320, height=240, fps=15)
    assert not mock_cam.is_opened()
    
    assert mock_cam.open() is True
    assert mock_cam.is_opened() is True

    props = mock_cam.get_properties()
    assert props["source_type"] == "mock"
    assert props["source_id"] == "test-mock"
    assert props["width"] == 320
    assert props["height"] == 240
    assert props["fps"] == 15
    assert props["is_opened"] is True

    mock_cam.release()
    assert not mock_cam.is_opened()


def test_mock_camera_frame_generation_and_indexing():
    """Test deterministic frame generation, unique IDs, timestamps, and indexing."""
    mock_cam = MockCameraSource(width=640, height=480, fps=10)
    mock_cam.open()

    frame1 = mock_cam.read_frame()
    assert frame1 is not None
    assert frame1.frame_index == 1
    assert frame1.width == 640
    assert frame1.height == 480
    assert frame1.data.shape == (480, 640, 3)
    assert frame1.frame_id.startswith("mock-frame-1-")
    assert isinstance(frame1.timestamp, str)

    frame2 = mock_cam.read_frame()
    assert frame2 is not None
    assert frame2.frame_index == 2
    assert frame2.frame_id != frame1.frame_id

    mock_cam.release()
    assert mock_cam.read_frame() is None


# ==============================================================================
# 2. VideoFileSource Tests
# ==============================================================================

def test_video_file_source_missing_file():
    """Test that missing video files raise InvalidVideoFileError."""
    fake_path = "C:/non_existent_folder_xyz/missing_video.mp4"
    source = VideoFileSource(fake_path)
    with pytest.raises(InvalidVideoFileError, match="Video file not found"):
        source.open()


def test_video_file_source_playback_and_loop():
    """Test valid local video creation, offline decoding, and frame reading."""
    # Create a small temporary OpenCV test video (10 frames)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_video_path = tmp.name

    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp_video_path, fourcc, 10.0, (160, 120))
        for i in range(10):
            frame = np.full((120, 160, 3), i * 20, dtype=np.uint8)
            out.write(frame)
        out.release()

        # Test non-looping playback
        source = VideoFileSource(tmp_video_path, loop=False)
        assert source.open() is True
        assert source.is_opened() is True
        props = source.get_properties()
        assert props["source_type"] == "file"
        assert props["width"] == 160
        assert props["height"] == 120

        frames_read = 0
        while True:
            f = source.read_frame()
            if f is None:
                break
            frames_read += 1
            assert f.width == 160
            assert f.height == 120

        assert frames_read == 10
        source.release()
        assert not source.is_opened()

        # Test looping playback
        loop_source = VideoFileSource(tmp_video_path, loop=True)
        loop_source.open()
        # Read 15 frames from 10-frame video
        for idx in range(15):
            f = loop_source.read_frame()
            assert f is not None
            assert f.frame_index == idx + 1
        loop_source.release()

    finally:
        Path(tmp_video_path).unlink(missing_ok=True)


# ==============================================================================
# 3. RealCameraSource Error Containment Tests
# ==============================================================================

def test_real_camera_source_unavailable_error():
    """Test RealCameraSource graceful handling when physical device is absent (index 999)."""
    cam = RealCameraSource(camera_index=999)
    with pytest.raises(CameraSourceError, match="unavailable or disconnected"):
        cam.open()
    assert not cam.is_opened()
    assert cam.read_frame() is None


# ==============================================================================
# 4. FrameProcessor Tests
# ==============================================================================

def test_frame_processor_resizing_and_validation():
    """Test FrameProcessor validation, canonical resizing, and RGB normalization."""
    proc = FrameProcessor(target_width=320, target_height=240, normalize_rgb=True, target_fps=10)

    # 1. Invalid frame
    assert proc.validate_frame(None) is False
    with pytest.raises(ValueError):
        proc.process(None)

    # 2. Valid frame resizing
    raw_img = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = Frame(width=640, height=480, data=raw_img, frame_index=1)
    
    processed = proc.process(frame)
    assert processed.width == 320
    assert processed.height == 240
    assert processed.data.shape == (240, 320, 3)
    assert processed.metadata["processed"] is True
    assert processed.metadata["processed_index"] == 1
    assert processed.metadata["normalized_rgb"] is True


# ==============================================================================
# 5. CameraManager Lifecycle & Bounded Buffer Tests
# ==============================================================================

def test_camera_manager_lifecycle():
    """Test CameraManager start, status, pause, resume, read, and stop."""
    mock_src = MockCameraSource(width=320, height=240, fps=20)
    mgr = CameraManager(source=mock_src, target_fps=20, buffer_size=5)

    assert mgr.state == CameraState.STOPPED
    with pytest.raises(CameraStoppedError):
        mgr.read()

    mgr.start()
    assert mgr.state == CameraState.RUNNING
    assert mgr.is_running() is True

    # Double start error
    with pytest.raises(CameraAlreadyRunningError):
        mgr.start()

    # Wait for background thread to ingest a few frames
    time.sleep(0.25)

    frame = mgr.read()
    assert frame is not None
    assert isinstance(frame, Frame)
    assert frame.frame_index >= 1

    # Pause
    mgr.pause()
    assert mgr.state == CameraState.PAUSED
    assert mgr.is_paused() is True

    # Resume
    mgr.resume()
    assert mgr.state == CameraState.RUNNING

    # Stop
    mgr.stop()
    assert mgr.state == CameraState.STOPPED
    assert not mgr.is_running()


def test_camera_manager_bounded_buffer_and_newest_preference():
    """Test bounded ring buffer size limit (5) and drop of older frames."""
    mock_src = MockCameraSource(width=160, height=120, fps=30)
    mgr = CameraManager(source=mock_src, target_fps=30, buffer_size=5)
    mgr.start()

    # Ingest for 0.4 seconds (> 10 frames)
    time.sleep(0.4)

    status = mgr.status()
    assert status["buffered_frames"] <= 5
    assert status["total_frames_ingested"] >= 5

    latest_frame = mgr.read()
    assert latest_frame is not None
    # Index should be recent (e.g. >= 5)
    assert latest_frame.frame_index >= 5

    mgr.stop()


# ==============================================================================
# 6. Session Camera Integration & Isolation Tests
# ==============================================================================

def test_session_camera_lifecycle_and_isolation():
    """Test session-scoped camera start, status, pause/resume sync, and stop."""
    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.start_session(db, experiment_id=exp.id)
        s_id = str(session.id)



        # 1. Start session camera
        start_status = camera_service.start_session_camera(
            session_id=s_id,
            source_type="mock",
            target_fps=15,
            buffer_size=5,
            db=db
        )
        assert start_status["state"] == "RUNNING"
        assert start_status["session_id"] == s_id

        time.sleep(0.2)
        frame = camera_service.read_session_frame(s_id)
        assert frame is not None
        assert frame.width == 640

        # Verify session manager is isolated from global manager
        global_mgr = CameraManagerRegistry.get_global_manager()
        assert global_mgr.state == CameraState.STOPPED

        # 2. Pause session -> pauses camera
        session_service.pause_session(db, session.id)
        session_cam = CameraManagerRegistry.get_for_session(s_id)
        assert session_cam is not None
        assert session_cam.state == CameraState.PAUSED

        # 3. Resume session -> resumes camera
        session_service.resume_session(db, session.id)
        assert session_cam.state == CameraState.RUNNING

        # 4. Stop session -> stops and releases camera
        session_service.stop_session(db, session.id)
        assert CameraManagerRegistry.get_for_session(s_id) is None

        # Verify SystemEvents recorded
        sys_events = event_service.get_session_system_events(db, session.id)
        event_types = [e.event_type for e in sys_events]
        assert EventType.CAMERA_STARTED.value in event_types
        assert EventType.FRAME_SOURCE_OPENED.value in event_types
        assert EventType.CAMERA_STOPPED.value in event_types
        assert EventType.FRAME_SOURCE_CLOSED.value in event_types


# ==============================================================================
# 7. Camera REST API Endpoint Tests
# ==============================================================================

client = TestClient(app)

def test_api_global_camera_endpoints():
    """Test /api/camera/start, /api/camera/status, /api/camera/frame, and /api/camera/stop."""
    # 1. Initial status -> STOPPED
    res = client.get("/api/camera/status")
    assert res.status_code == 200
    assert res.json()["state"] == "STOPPED"

    # 2. Start global camera
    payload = {
        "source_type": "mock",
        "target_fps": 10,
        "frame_width": 320,
        "frame_height": 240,
        "buffer_size": 5
    }
    res = client.post("/api/camera/start", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "RUNNING"
    assert data["target_fps"] == 10

    # 3. Conflict when already running
    res_conflict = client.post("/api/camera/start", json=payload)
    assert res_conflict.status_code == 409

    # Wait for frames
    time.sleep(0.25)

    # 4. Fetch frame metadata
    res_frame = client.get("/api/camera/frame")
    assert res_frame.status_code == 200
    frame_data = res_frame.json()
    assert "frame_id" in frame_data
    assert "timestamp" in frame_data
    assert frame_data["width"] == 320
    assert frame_data["height"] == 240
    assert "data" not in frame_data  # Ensure no large binary payload in JSON

    # 5. Stop global camera
    res_stop = client.post("/api/camera/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["state"] == "STOPPED"


def test_api_session_scoped_camera_endpoints():
    """Test /api/sessions/{id}/camera/* endpoints."""
    with SessionLocal() as db:
        exp = experiment_service.seed_default_experiment_if_empty(db)
        session = session_service.create_session(db, experiment_id=exp.id)
        s_id = str(session.id)

    # Start session camera
    res = client.post(f"/api/sessions/{s_id}/camera/start", json={"source_type": "mock", "target_fps": 15})
    assert res.status_code == 200
    assert res.json()["state"] == "RUNNING"

    # Check session camera status
    res_st = client.get(f"/api/sessions/{s_id}/camera/status")
    assert res_st.status_code == 200
    assert res_st.json()["state"] == "RUNNING"

    time.sleep(0.2)
    # Get frame
    res_fr = client.get(f"/api/sessions/{s_id}/camera/frame")
    assert res_fr.status_code == 200
    assert res_fr.json()["frame_index"] >= 1

    # Stop session camera
    res_stp = client.post(f"/api/sessions/{s_id}/camera/stop")
    assert res_stp.status_code == 200
    assert res_stp.json()["state"] == "STOPPED"

    # Nonexistent session test
    res_404 = client.post("/api/sessions/99999/camera/start")
    assert res_404.status_code == 404


# ==============================================================================
# 8. Future AI Pipeline Compatibility (Frame -> AI -> Action -> Validator)
# ==============================================================================

def test_future_ai_inference_pipeline_bridge():
    """
    Verify clean compatibility for future AI inference engines:
    Frame -> MockFrameInferenceEngine -> ObservedAction -> SequenceValidator
    """
    with SessionLocal() as db:
        from app.db.repository import create_experiment, create_step
        import uuid
        exp = create_experiment(db, name=f"Test Pipeline Bridge {uuid.uuid4().hex[:6]}")
        create_step(db, experiment_id=exp.id, step_number=1, step_code="STEP_01", name="Pick Tool", expected_action="PICK_TOOL", required_objects=["tool"])
        create_step(db, experiment_id=exp.id, step_number=2, step_code="STEP_02", name="Open Container", expected_action="OPEN_CONTAINER", required_objects=["container"])
        session = session_service.start_session(db, experiment_id=exp.id)
        steps = experiment_service.get_experiment_steps(db, exp.id)

    # 1. Ingest frame from mock source
    mock_source = MockCameraSource(width=640, height=480, fps=10)
    mock_source.open()
    raw_frame = mock_source.read_frame()
    assert raw_frame is not None

    # 2. Preprocess frame
    processor = FrameProcessor(target_width=640, target_height=480)
    ready_frame = processor.process(raw_frame)
    assert ready_frame.metadata["processed"] is True

    # 3. Future AI inference engine consumes Frame and emits ObservedAction
    inf_engine = MockFrameInferenceEngine()
    inf_engine.set_scenario("NORMAL")
    observed_action = inf_engine.infer_action(ready_frame)

    assert observed_action.action_code == "PICK_TOOL"
    assert observed_action.confidence > 0.8
    assert observed_action.metadata["source_frame_id"] == ready_frame.frame_id

    # 4. Sequence Validator validates the observed action
    outcome = sequence_validator.validate_observation(
        observation=observed_action,
        session_id=session.id,
        steps=steps
    )

    assert outcome.result == "VALID"
    assert outcome.expected_step_number == 1
    assert outcome.expected_action == "PICK_TOOL"

    mock_source.release()




