"""
Camera Manager for AURAVISION Offline System
Controls the lifecycle, thread execution, bounded ring buffer, and FPS rate-limiting for camera sources.
"""
import time
import threading
from collections import deque
from typing import Optional, Dict, Any, Deque
from enum import Enum

from app.camera.camera_source import CameraSource
from app.camera.mock_camera import MockCameraSource
from app.camera.video_file_source import VideoFileSource
from app.camera.real_camera import RealCameraSource
from app.camera.frame_model import Frame
from app.camera.frame_processor import FrameProcessor
from app.camera.exceptions import (
    CameraAlreadyRunningError,
    CameraStoppedError,
    CameraSourceError,
    CameraError,
)
from app.core.logging import logger


class CameraState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class CameraManager:
    """
    Manages the lifecycle of a camera source, runs a background reader thread,
    enforces FPS pacing, applies preprocessing, and maintains a bounded frame buffer.
    """

    def __init__(
        self,
        source: Optional[CameraSource] = None,
        processor: Optional[FrameProcessor] = None,
        target_fps: int = 10,
        buffer_size: int = 5,
        session_id: Optional[str] = None
    ):
        self.source = source
        self.target_fps = max(1, target_fps)
        self.buffer_size = max(1, buffer_size)
        self.session_id = session_id
        self.processor = processor or FrameProcessor(target_fps=self.target_fps)

        self._state: CameraState = CameraState.STOPPED
        self._buffer: Deque[Frame] = deque(maxlen=self.buffer_size)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._last_error: Optional[str] = None
        self._total_frames_ingested = 0
        self._start_time: Optional[float] = None

    @property
    def state(self) -> CameraState:
        with self._lock:
            return self._state

    def is_running(self) -> bool:
        with self._lock:
            return self._state in (CameraState.RUNNING, CameraState.PAUSED)

    def is_paused(self) -> bool:
        with self._lock:
            return self._state == CameraState.PAUSED

    def set_source(self, source: CameraSource) -> None:
        """Assign or update the camera source (only allowed when stopped)."""
        with self._lock:
            if self._state not in (CameraState.STOPPED, CameraState.ERROR):
                raise CameraAlreadyRunningError("Cannot set camera source while camera is running.")
            self.source = source

    def start(self) -> None:
        """
        Open the source and start background frame acquisition loop.
        """
        with self._lock:
            if self._state in (CameraState.RUNNING, CameraState.STARTING):
                raise CameraAlreadyRunningError("Camera manager is already running.")

            if self.source is None:
                raise CameraSourceError("No camera source configured to start.")

            self._state = CameraState.STARTING
            self._last_error = None

        try:
            opened = self.source.open()
            if not opened or not self.source.is_opened():
                raise CameraSourceError("Source open() returned False or failed to open.")
        except Exception as e:
            with self._lock:
                self._state = CameraState.ERROR
                self._last_error = str(e)
            logger.error(f"Failed to open camera source: {e}")
            raise CameraSourceError(f"Failed to open camera source: {e}")

        with self._lock:
            self._stop_event.clear()
            self._pause_event.clear()
            self._buffer.clear()
            self._total_frames_ingested = 0
            self._start_time = time.time()
            self._state = CameraState.RUNNING

            self._thread = threading.Thread(
                target=self._capture_loop,
                name=f"CameraWorker-{self.session_id or 'global'}",
                daemon=True
            )
            self._thread.start()

        logger.info(f"Camera manager started successfully (session: {self.session_id}).")

    def _capture_loop(self) -> None:
        """Background thread loop capturing frames at target FPS rate."""
        frame_interval = 1.0 / self.target_fps

        while not self._stop_event.is_set():
            loop_start = time.perf_counter()

            # Handle pause state
            if self._pause_event.is_set():
                time.sleep(0.05)
                continue

            try:
                raw_frame = self.source.read_frame() if self.source else None
                if raw_frame is not None:
                    # Preprocess frame
                    processed_frame = self.processor.process(raw_frame)
                    with self._lock:
                        self._buffer.append(processed_frame)
                        self._total_frames_ingested += 1
                else:
                    # If reading returned None (e.g. video EOF and not looping)
                    time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error reading/processing frame in camera worker: {e}")
                with self._lock:
                    self._last_error = str(e)
                    self._state = CameraState.ERROR
                break

            elapsed = time.perf_counter() - loop_start
            sleep_needed = max(0.0, frame_interval - elapsed)
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    def pause(self) -> None:
        """Pause frame ingestion."""
        with self._lock:
            if self._state != CameraState.RUNNING:
                return
            self._pause_event.set()
            self._state = CameraState.PAUSED
        logger.info(f"Camera manager paused (session: {self.session_id}).")

    def resume(self) -> None:
        """Resume frame ingestion from paused state."""
        with self._lock:
            if self._state != CameraState.PAUSED:
                return
            self._pause_event.clear()
            self._state = CameraState.RUNNING
        logger.info(f"Camera manager resumed (session: {self.session_id}).")

    def read(self) -> Optional[Frame]:
        """
        Retrieve the latest frame from the bounded buffer.
        Returns the newest Frame, or None if buffer is empty.
        """
        with self._lock:
            if self._state == CameraState.STOPPED:
                raise CameraStoppedError("Cannot read frame: Camera is stopped.")
            if not self._buffer:
                return None
            # Return newest frame (rightmost in deque)
            return self._buffer[-1]

    def stop(self) -> None:
        """
        Stop the capture loop and cleanly release source hardware/file handles.
        """
        with self._lock:
            if self._state == CameraState.STOPPED:
                return
            self._state = CameraState.STOPPED

        self._stop_event.set()
        self._pause_event.clear()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        if self.source is not None:
            try:
                self.source.release()
            except Exception as e:
                logger.warning(f"Error releasing camera source: {e}")

        logger.info(f"Camera manager stopped (session: {self.session_id}).")

    def status(self) -> Dict[str, Any]:
        """Return comprehensive status and health metrics."""
        with self._lock:
            current_state = self._state.value
            buf_len = len(self._buffer)
            total_frames = self._total_frames_ingested
            last_err = self._last_error
            uptime = (time.time() - self._start_time) if (self._start_time and self._state == CameraState.RUNNING) else 0.0

        source_info = self.source.get_properties() if self.source else None

        return {
            "state": current_state,
            "session_id": self.session_id,
            "target_fps": self.target_fps,
            "buffer_size": self.buffer_size,
            "buffered_frames": buf_len,
            "total_frames_ingested": total_frames,
            "uptime_seconds": round(uptime, 2),
            "last_error": last_err,
            "source": source_info
        }

    def get_source_info(self) -> Optional[Dict[str, Any]]:
        """Return the source properties if available."""
        return self.source.get_properties() if self.source else None


class CameraManagerRegistry:
    """
    Registry managing session-isolated CameraManager instances and a default singleton.
    Ensures sessions do not unintentionally share mutable camera state.
    """
    _global_manager: Optional[CameraManager] = None
    _session_managers: Dict[str, CameraManager] = {}
    _lock = threading.Lock()

    @classmethod
    def get_global_manager(cls) -> CameraManager:
        with cls._lock:
            if cls._global_manager is None:
                # Default to mock camera
                cls._global_manager = CameraManager(
                    source=MockCameraSource(),
                    target_fps=10,
                    buffer_size=5
                )
            return cls._global_manager

    @classmethod
    def set_global_manager(cls, manager: CameraManager) -> None:
        with cls._lock:
            if cls._global_manager is not None and cls._global_manager.is_running():
                cls._global_manager.stop()
            cls._global_manager = manager

    @classmethod
    def get_for_session(cls, session_id: str) -> Optional[CameraManager]:
        with cls._lock:
            return cls._session_managers.get(str(session_id))

    @classmethod
    def get_or_create_for_session(
        cls,
        session_id: str,
        source: Optional[CameraSource] = None,
        target_fps: int = 10,
        buffer_size: int = 5,
        target_width: int = 640,
        target_height: int = 480
    ) -> CameraManager:
        with cls._lock:
            s_id = str(session_id)
            if s_id not in cls._session_managers:
                src = source or MockCameraSource(source_id=f"session-{s_id}-mock")
                proc = FrameProcessor(
                    target_width=target_width,
                    target_height=target_height,
                    target_fps=target_fps
                )
                cls._session_managers[s_id] = CameraManager(
                    source=src,
                    processor=proc,
                    target_fps=target_fps,
                    buffer_size=buffer_size,
                    session_id=s_id
                )
            return cls._session_managers[s_id]

    @classmethod
    def remove_for_session(cls, session_id: str) -> None:
        with cls._lock:
            s_id = str(session_id)
            mgr = cls._session_managers.pop(s_id, None)
            if mgr is not None and mgr.is_running():
                mgr.stop()

    @classmethod
    def stop_all(cls) -> None:
        with cls._lock:
            if cls._global_manager is not None and cls._global_manager.is_running():
                cls._global_manager.stop()
            for mgr in cls._session_managers.values():
                if mgr.is_running():
                    mgr.stop()
            cls._session_managers.clear()
