"""
Pytest Configuration and Shared Test Fixtures for AURAVISION
"""
import pytest
from app.db.database import init_db, SessionLocal
from app.services.experiment_service import experiment_service
from app.core.config import settings


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure SQLite database and default experiment are ready before each test."""
    settings.VIDEO_SOURCE = "mock"
    settings.AI_MODE = "mock"
    settings.ensure_directories()
    init_db()
    with SessionLocal() as db:
        experiment_service.seed_default_experiment_if_empty(db)
    try:
        from app.workers.video_worker import video_worker
        video_worker.stop()
        from app.services.video_service import video_service
        video_service.stop_capture()
        from app.ml.model_registry import ModelRegistry
        p = ModelRegistry.get_provider("mock")
        if not p.is_ready():
            p.initialize()
    except Exception:
        pass
    yield
    try:
        from app.workers.video_worker import video_worker
        video_worker.stop()
        from app.services.video_service import video_service
        video_service.stop_capture()
        from app.camera.camera_manager import CameraManagerRegistry
        CameraManagerRegistry.stop_all()
        from app.services.realtime_processor import RealTimeProcessorRegistry
        RealTimeProcessorRegistry.stop_all()
    except Exception:
        pass


@pytest.fixture
def db_session():
    """Provide a database session fixture for test functions."""
    with SessionLocal() as db:
        yield db

