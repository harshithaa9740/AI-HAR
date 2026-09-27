"""
Camera Service for AURAVISION Offline System
Coordinates camera source creation, manager lifecycle, buffer reads, and system event logging.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.camera.camera_source import CameraSource
from app.camera.mock_camera import MockCameraSource
from app.camera.video_file_source import VideoFileSource
from app.camera.real_camera import RealCameraSource
from app.camera.frame_processor import FrameProcessor
from app.camera.camera_manager import CameraManager, CameraState, CameraManagerRegistry
from app.camera.frame_model import Frame
from app.camera.exceptions import (
    CameraError,
    CameraSourceError,
    CameraAlreadyRunningError,
    CameraStoppedError,
    InvalidVideoFileError,
)
from app.core.config import settings
from app.core.constants import EventType, AlertSeverity
from app.core.logging import logger
from app.services.event_service import event_service
from app.db.database import SessionLocal


class CameraService:
    """
    High-level service orchestrating camera source lifecycle and session integration.
    """

    @staticmethod
    def create_source(
        source_type: Optional[str] = None,
        camera_index: Optional[int] = None,
        file_path: Optional[str] = None,
        target_fps: Optional[int] = None,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        loop: bool = False
    ) -> CameraSource:
        """
        Factory method to instantiate a CameraSource based on type.
        Supports: 'mock', 'file', 'webcam'.
        """
        stype = (source_type or settings.CAMERA_SOURCE).lower().strip()
        fps = target_fps or settings.TARGET_FPS
        w = frame_width or settings.FRAME_WIDTH
        h = frame_height or settings.FRAME_HEIGHT

        if stype == "mock":
            return MockCameraSource(
                source_id="mock-camera",
                width=w,
                height=h,
                fps=fps
            )
        elif stype in ("file", "video"):
            vpath = file_path or settings.VIDEO_FILE_PATH
            if not vpath:
                raise InvalidVideoFileError("No video file path provided for video file source.")
            return VideoFileSource(
                file_path=vpath,
                source_id=f"file-source",
                loop=loop
            )
        elif stype in ("webcam", "camera", "real"):
            idx = camera_index if camera_index is not None else settings.CAMERA_INDEX
            return RealCameraSource(
                camera_index=idx,
                source_id=f"webcam-{idx}",
                target_fps=fps,
                width=w,
                height=h
            )
        else:
            raise ValueError(f"Unsupported camera source type: '{stype}'. Use 'mock', 'file', or 'webcam'.")

    @classmethod
    def start_global_camera(
        cls,
        source_type: Optional[str] = None,
        camera_index: Optional[int] = None,
        file_path: Optional[str] = None,
        target_fps: Optional[int] = None,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        buffer_size: Optional[int] = None,
        loop: bool = False,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Start the global/standalone camera manager."""
        mgr = CameraManagerRegistry.get_global_manager()

        if mgr.is_running():
            raise CameraAlreadyRunningError("Global camera is already running.")

        fps = target_fps or settings.TARGET_FPS
        buf_size = buffer_size or settings.FRAME_BUFFER_SIZE
        w = frame_width or settings.FRAME_WIDTH
        h = frame_height or settings.FRAME_HEIGHT

        source = cls.create_source(
            source_type=source_type,
            camera_index=camera_index,
            file_path=file_path,
            target_fps=fps,
            frame_width=w,
            frame_height=h,
            loop=loop
        )

        processor = FrameProcessor(
            target_width=w,
            target_height=h,
            target_fps=fps
        )

        mgr.source = source
        mgr.processor = processor
        mgr.target_fps = fps
        mgr.buffer_size = buf_size

        try:
            mgr.start()
            cls._log_event(
                event_type=EventType.CAMERA_STARTED.value,
                message=f"Global camera pipeline started with source '{source.get_properties().get('source_type')}'",
                db=db
            )
            cls._log_event(
                event_type=EventType.FRAME_SOURCE_OPENED.value,
                message=f"Frame source opened: {source.get_properties().get('source_id')}",
                db=db
            )
            return mgr.status()
        except Exception as e:
            cls._log_event(
                event_type=EventType.CAMERA_ERROR.value,
                message=f"Global camera failed to start: {str(e)}",
                severity=AlertSeverity.CRITICAL.value,
                db=db
            )
            raise

    @classmethod
    def stop_global_camera(cls, db: Optional[Session] = None) -> Dict[str, Any]:
        """Stop the global camera manager."""
        mgr = CameraManagerRegistry.get_global_manager()
        mgr.stop()
        cls._log_event(
            event_type=EventType.CAMERA_STOPPED.value,
            message="Global camera pipeline stopped",
            db=db
        )
        cls._log_event(
            event_type=EventType.FRAME_SOURCE_CLOSED.value,
            message="Frame source closed",
            db=db
        )
        return mgr.status()

    @classmethod
    def get_global_status(cls) -> Dict[str, Any]:
        """Get the status of the global camera manager."""
        mgr = CameraManagerRegistry.get_global_manager()
        return mgr.status()

    @classmethod
    def read_global_frame(cls) -> Optional[Frame]:
        """Read latest preprocessed frame from global camera buffer."""
        mgr = CameraManagerRegistry.get_global_manager()
        return mgr.read()

    # ==========================================
    # Session-Scoped Operations
    # ==========================================

    @classmethod
    def start_session_camera(
        cls,
        session_id: str,
        source_type: Optional[str] = None,
        camera_index: Optional[int] = None,
        file_path: Optional[str] = None,
        target_fps: Optional[int] = None,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
        buffer_size: Optional[int] = None,
        loop: bool = False,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Start or initialize a session-isolated camera manager."""
        fps = target_fps or settings.TARGET_FPS
        buf_size = buffer_size or settings.FRAME_BUFFER_SIZE
        w = frame_width or settings.FRAME_WIDTH
        h = frame_height or settings.FRAME_HEIGHT

        source = cls.create_source(
            source_type=source_type,
            camera_index=camera_index,
            file_path=file_path,
            target_fps=fps,
            frame_width=w,
            frame_height=h,
            loop=loop
        )

        mgr = CameraManagerRegistry.get_or_create_for_session(
            session_id=session_id,
            source=source,
            target_fps=fps,
            buffer_size=buf_size,
            target_width=w,
            target_height=h
        )

        if mgr.is_running():
            raise CameraAlreadyRunningError(f"Camera manager for session '{session_id}' is already running.")

        # Update source in case it changed
        mgr.set_source(source)

        try:
            mgr.start()
            cls._log_event(
                event_type=EventType.CAMERA_STARTED.value,
                message=f"Session camera started with source '{source.get_properties().get('source_type')}'",
                session_id=session_id,
                db=db
            )
            cls._log_event(
                event_type=EventType.FRAME_SOURCE_OPENED.value,
                message=f"Session frame source opened: {source.get_properties().get('source_id')}",
                session_id=session_id,
                db=db
            )
            return mgr.status()
        except Exception as e:
            cls._log_event(
                event_type=EventType.CAMERA_ERROR.value,
                message=f"Session camera failed to start: {str(e)}",
                severity=AlertSeverity.CRITICAL.value,
                session_id=session_id,
                db=db
            )
            raise

    @classmethod
    def stop_session_camera(cls, session_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Stop and release camera resources for a session."""
        mgr = CameraManagerRegistry.get_for_session(session_id)
        if mgr is None:
            return {
                "state": CameraState.STOPPED.value,
                "session_id": str(session_id),
                "target_fps": settings.TARGET_FPS,
                "buffer_size": settings.FRAME_BUFFER_SIZE,
                "buffered_frames": 0,
                "total_frames_ingested": 0,
                "uptime_seconds": 0.0,
                "last_error": None,
                "source": None
            }

        mgr.stop()
        cls._log_event(
            event_type=EventType.CAMERA_STOPPED.value,
            message=f"Session camera stopped for session '{session_id}'",
            session_id=session_id,
            db=db
        )
        cls._log_event(
            event_type=EventType.FRAME_SOURCE_CLOSED.value,
            message=f"Session frame source closed for session '{session_id}'",
            session_id=session_id,
            db=db
        )
        status_dict = mgr.status()
        CameraManagerRegistry.remove_for_session(session_id)
        return status_dict

    @classmethod
    def get_session_status(cls, session_id: str) -> Dict[str, Any]:
        """Get the current camera status for a session."""
        mgr = CameraManagerRegistry.get_for_session(session_id)
        if mgr is None:
            return {
                "state": CameraState.STOPPED.value,
                "session_id": str(session_id),
                "target_fps": settings.TARGET_FPS,
                "buffer_size": settings.FRAME_BUFFER_SIZE,
                "buffered_frames": 0,
                "total_frames_ingested": 0,
                "uptime_seconds": 0.0,
                "last_error": None,
                "source": None
            }
        return mgr.status()

    @classmethod
    def read_session_frame(cls, session_id: str) -> Optional[Frame]:
        """Read the newest frame from the session-scoped camera buffer."""
        mgr = CameraManagerRegistry.get_for_session(session_id)
        if mgr is None or not mgr.is_running():
            raise CameraStoppedError(f"No active camera running for session '{session_id}'.")
        return mgr.read()

    @staticmethod
    def _log_event(
        event_type: str,
        message: str,
        severity: str = AlertSeverity.INFO.value,
        session_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> None:
        """Internal helper to record camera system events."""
        try:
            if db is not None:
                event_service.record_system_event(
                    db=db,
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    component="camera",
                    session_id=session_id
                )
            else:
                with SessionLocal() as local_db:
                    event_service.record_system_event(
                        db=local_db,
                        event_type=event_type,
                        message=message,
                        severity=severity,
                        component="camera",
                        session_id=session_id
                    )
        except Exception as e:
            logger.warning(f"Failed to record camera system event: {e}")


camera_service = CameraService()
