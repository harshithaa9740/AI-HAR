"""
Local Video Capture, Synthetic Frame Generator, and Local Video Recording Service
"""
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np
from app.core.config import settings, RECORDINGS_DIR
from app.core.logging import logger


class VideoService:
    """
    Manages local video ingestion (Webcam, MP4 File, RTSP, or Synthetic Mock Generator)
    and handles offline OpenCV VideoWriter recordings into data/recordings/.
    """

    def __init__(self):
        self.source = settings.VIDEO_SOURCE
        self.is_running = False
        self.is_recording = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.writer: Optional[cv2.VideoWriter] = None
        self.current_recording_path: Optional[str] = None
        self.current_session_id: Optional[str] = None
        
        self.frame_width = settings.VIDEO_FRAME_WIDTH
        self.frame_height = settings.VIDEO_FRAME_HEIGHT
        self.fps = settings.VIDEO_FPS
        self.frame_count = 0
        self.start_time: Optional[float] = None
        
        self._latest_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _open_capture(self):
        if str(self.source).lower() in ("mock", "synthetic", "none"):
            logger.info("Using Synthetic Mock Video Generator (Offline Headless).")
            self.cap = None
            return True

        # Check if source is numeric (webcam index)
        try:
            source_val = int(self.source)
        except ValueError:
            source_val = self.source

        try:
            self.cap = cv2.VideoCapture(source_val)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                logger.info(f"Video capture opened successfully for source: {self.source}")
                return True
        except Exception as e:
            logger.warning(f"Could not open hardware video capture for {self.source}: {e}")

        logger.info("Using Synthetic Mock Video Generator (Offline Headless).")
        self.cap = None
        return True

    def _generate_synthetic_frame(self, frame_idx: int) -> np.ndarray:
        """Generate high-contrast synthetic laboratory camera frame with timestamp and overlay."""
        frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        
        # Laboratory background gradient
        for y in range(self.frame_height):
            v = int(25 + 30 * (y / self.frame_height))
            frame[y, :] = (v, v + 5, v + 10)

        # Draw simulated lab workstation table
        table_top = int(self.frame_height * 0.6)
        cv2.rectangle(frame, (50, table_top), (self.frame_width - 50, self.frame_height - 20), (50, 60, 70), -1)
        cv2.rectangle(frame, (50, table_top), (self.frame_width - 50, self.frame_height - 20), (100, 120, 140), 2)

        # Draw simulated objects on table
        # Tool
        cv2.rectangle(frame, (150, table_top - 40), (250, table_top), (0, 165, 255), -1)
        cv2.putText(frame, "TOOL", (170, table_top - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Container
        cv2.rectangle(frame, (350, table_top - 80), (480, table_top), (0, 200, 100), -1)
        cv2.putText(frame, "CONTAINER", (360, table_top - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Sample Tube
        cv2.rectangle(frame, (580, table_top - 60), (640, table_top), (255, 100, 50), -1)
        cv2.putText(frame, "SAMPLE", (580, table_top - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Chamber
        cv2.rectangle(frame, (750, table_top - 120), (950, table_top), (150, 100, 200), -1)
        cv2.putText(frame, "CHAMBER", (810, table_top - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw animated astronaut hands indicator
        hand_x = int(self.frame_width * (0.3 + 0.2 * np.sin(frame_idx * 0.05)))
        hand_y = int(table_top - 50 + 20 * np.cos(frame_idx * 0.05))
        cv2.circle(frame, (hand_x, hand_y), 25, (0, 255, 255), -1)
        cv2.putText(frame, "ASTRONAUT HAND", (hand_x - 60, hand_y - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # System telemetry banner
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        cv2.putText(frame, f"AURAVISION OFFLINE PAYLOAD CAMERA | {now_str}", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
        cv2.putText(frame, f"STATUS: LIVE | FRAME: {frame_idx} | FPS: {self.fps}", (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        return frame

    def start_capture(self, source: Optional[str] = None, record: bool = True, session_id: Optional[str] = None):
        """Start background frame capture loop and local recording."""
        if self.is_running:
            logger.info("Video capture is already running.")
            return

        self.source = source if source is not None else settings.VIDEO_SOURCE
        self.current_session_id = str(session_id) if session_id is not None else "default"
        self._open_capture()
        self.is_running = True
        self.frame_count = 0
        self.start_time = time.time()
        self._stop_event.clear()

        # Initialize VideoWriter if recording enabled
        if record and settings.VIDEO_RECORDING_ENABLED:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"experiment_{self.current_session_id[:8]}_{timestamp}.mp4"
            out_path = str(RECORDINGS_DIR / filename)
            
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(out_path, fourcc, float(self.fps), (self.frame_width, self.frame_height))
            self.current_recording_path = out_path
            self.is_recording = True
            logger.info(f"Local video recording started at {out_path}")

        # Start capture worker thread
        self._worker_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._worker_thread.start()

    def _capture_loop(self):
        while not self._stop_event.is_set() and self.is_running:
            frame = None
            if self.cap and self.cap.isOpened():
                ret, captured = self.cap.read()
                if ret and captured is not None:
                    frame = cv2.resize(captured, (self.frame_width, self.frame_height))
            
            if frame is None:
                # Fallback to synthetic frame generator
                frame = self._generate_synthetic_frame(self.frame_count)

            self.frame_count += 1
            with self._lock:
                self._latest_frame = frame

            if self.is_recording and self.writer:
                try:
                    self.writer.write(frame)
                except Exception as e:
                    logger.error(f"Error writing video frame: {e}")

            time.sleep(1.0 / self.fps)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def stop_capture(self) -> Dict[str, Any]:
        """Stop capture loop and close writer."""
        self.is_running = False
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

        if self.writer:
            self.writer.release()
            self.writer = None
            self.is_recording = False
            logger.info(f"Local video recording closed: {self.current_recording_path}")

        if self.cap:
            self.cap.release()
            self.cap = None

        duration = time.time() - self.start_time if self.start_time else 0.0
        return {
            "recording_path": self.current_recording_path,
            "duration_seconds": round(duration, 2),
            "frames_recorded": self.frame_count,
            "resolution": f"{self.frame_width}x{self.frame_height}",
            "fps": self.fps
        }

    def get_status(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time if (self.is_running and self.start_time) else 0.0
        current_fps = round(self.frame_count / max(1.0, elapsed), 1) if self.is_running else 0.0
        return {
            "is_running": self.is_running,
            "source": str(self.source),
            "is_recording": self.is_recording,
            "current_recording_path": self.current_recording_path,
            "frames_processed": self.frame_count,
            "fps": current_fps if self.is_running else float(self.fps),
            "resolution": f"{self.frame_width}x{self.frame_height}",
            "streaming_enabled": settings.STREAM_ENABLED
        }


video_service = VideoService()
