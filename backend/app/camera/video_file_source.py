"""
Video File Source for AURAVISION Offline System
Reads and decodes local offline video files using OpenCV.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import uuid
import cv2

from app.camera.camera_source import CameraSource
from app.camera.frame_model import Frame
from app.camera.exceptions import InvalidVideoFileError


class VideoFileSource(CameraSource):
    """
    Ingests frames from a local video file via OpenCV.
    Ensures strict local-only filesystem operation and safe error handling.
    """

    def __init__(
        self,
        file_path: str,
        source_id: Optional[str] = None,
        loop: bool = False
    ):
        self.raw_path = file_path
        self.file_path = Path(file_path)
        self.source_id = source_id or f"file-{self.file_path.name}"
        self.loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._fps = 30.0
        self._width = 0
        self._height = 0
        self._total_frames = 0

    def open(self) -> bool:
        """
        Validate file existence and open video capture stream.
        Raises InvalidVideoFileError if missing or invalid.
        """
        # Security validation: Ensure path is local and exists
        if not self.file_path.is_file():
            raise InvalidVideoFileError(f"Video file not found at local path: {self.raw_path}")

        self._cap = cv2.VideoCapture(str(self.file_path))
        if not self._cap.isOpened():
            self._cap = None
            raise InvalidVideoFileError(f"Failed to open video file (unsupported codec or corrupt): {self.raw_path}")

        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_val = self._cap.get(cv2.CAP_PROP_FPS)
        self._fps = fps_val if fps_val > 0 else 30.0
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._frame_count = 0

        return True

    def read_frame(self) -> Optional[Frame]:
        """
        Read the next frame from the video file.
        Loops to beginning if loop=True, else returns None upon EOF.
        """
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame_bgr = self._cap.read()
        if not ret or frame_bgr is None:
            if self.loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame_bgr = self._cap.read()
                if not ret or frame_bgr is None:
                    return None
            else:
                return None

        self._frame_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        frame_id = f"file-frame-{self._frame_count}-{uuid.uuid4().hex[:8]}"
        h, w = frame_bgr.shape[:2]

        return Frame(
            frame_id=frame_id,
            timestamp=now_iso,
            frame_index=self._frame_count,
            width=w,
            height=h,
            source_id=self.source_id,
            data=frame_bgr,
            metadata={
                "source_file": self.file_path.name,
                "fps": self._fps,
                "total_frames": self._total_frames,
                "loop": self.loop
            }
        )

    def release(self) -> None:
        """Release the OpenCV video capture resource."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_opened(self) -> bool:
        """Check if video file capture is open."""
        return self._cap is not None and self._cap.isOpened()

    def get_properties(self) -> Dict[str, Any]:
        """Return video file properties."""
        return {
            "source_type": "file",
            "source_id": self.source_id,
            "file_name": self.file_path.name,
            "width": self._width,
            "height": self._height,
            "fps": self._fps,
            "total_frames": self._total_frames,
            "current_frame": self._frame_count,
            "loop": self.loop,
            "is_opened": self.is_opened()
        }
