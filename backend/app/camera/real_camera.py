"""
Real Camera (Webcam/Device) Source for AURAVISION Offline System
Captures live frames from a local hardware camera index using OpenCV.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
import cv2

from app.camera.camera_source import CameraSource
from app.camera.frame_model import Frame
from app.camera.exceptions import CameraSourceError
from app.core.logging import logger


class RealCameraSource(CameraSource):
    """
    Ingests frames from a local physical camera device index (e.g., 0).
    Implements safe hardware opening, graceful degradation, and error containment.
    """

    def __init__(
        self,
        camera_index: int = 0,
        source_id: Optional[str] = None,
        target_fps: int = 30,
        width: Optional[int] = None,
        height: Optional[int] = None
    ):
        self.camera_index = camera_index
        self.source_id = source_id or f"webcam-{camera_index}"
        self.target_fps = target_fps
        self.requested_width = width
        self.requested_height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._actual_width = 0
        self._actual_height = 0

    def open(self) -> bool:
        """
        Attempt to open the local physical camera device.
        Raises CameraSourceError if the device cannot be opened.
        """
        try:
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                self._cap = None
                raise CameraSourceError(
                    f"Physical camera device at index {self.camera_index} is unavailable or disconnected."
                )

            # Apply requested dimensions if provided
            if self.requested_width and self.requested_height:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested_width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested_height)

            self._actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._frame_count = 0
            return True

        except CameraSourceError:
            raise
        except Exception as e:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            raise CameraSourceError(f"Unexpected error opening physical camera {self.camera_index}: {str(e)}")

    def read_frame(self) -> Optional[Frame]:
        """Read a single frame from the live physical camera."""
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame_bgr = self._cap.read()
        if not ret or frame_bgr is None:
            logger.warning(f"Failed to capture frame from webcam index {self.camera_index}")
            return None

        self._frame_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        frame_id = f"webcam-frame-{self._frame_count}-{uuid.uuid4().hex[:8]}"
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
                "camera_index": self.camera_index,
                "fps": self.target_fps
            }
        )

    def release(self) -> None:
        """Release the camera hardware device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_opened(self) -> bool:
        """Check if the physical camera is open."""
        return self._cap is not None and self._cap.isOpened()

    def get_properties(self) -> Dict[str, Any]:
        """Return physical camera properties."""
        return {
            "source_type": "webcam",
            "source_id": self.source_id,
            "camera_index": self.camera_index,
            "width": self._actual_width,
            "height": self._actual_height,
            "fps": self.target_fps,
            "frame_count": self._frame_count,
            "is_opened": self.is_opened()
        }
