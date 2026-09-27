"""
Camera Subsystem Package for AURAVISION Offline System
"""
from app.camera.frame_model import Frame
from app.camera.camera_source import CameraSource
from app.camera.mock_camera import MockCameraSource
from app.camera.video_file_source import VideoFileSource
from app.camera.real_camera import RealCameraSource
from app.camera.frame_processor import FrameProcessor
from app.camera.camera_manager import CameraManager, CameraState, CameraManagerRegistry
from app.camera.exceptions import (
    CameraError,
    CameraNotFoundError,
    CameraSourceError,
    CameraAlreadyRunningError,
    CameraStoppedError,
    InvalidVideoFileError,
    FrameReadError,
)

__all__ = [
    "Frame",
    "CameraSource",
    "MockCameraSource",
    "VideoFileSource",
    "RealCameraSource",
    "FrameProcessor",
    "CameraManager",
    "CameraState",
    "CameraManagerRegistry",
    "CameraError",
    "CameraNotFoundError",
    "CameraSourceError",
    "CameraAlreadyRunningError",
    "CameraStoppedError",
    "InvalidVideoFileError",
    "FrameReadError",
]
