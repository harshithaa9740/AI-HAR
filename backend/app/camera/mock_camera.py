"""
Mock Camera Source for AURAVISION Offline System
Generates synthetic, deterministic video frames for offline testing and hardware-free execution.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import numpy as np
import uuid

from app.camera.camera_source import CameraSource
from app.camera.frame_model import Frame


class MockCameraSource(CameraSource):
    """
    Simulated camera source providing synthetic test frames.
    Allows deterministic offline testing without requiring a physical camera or external video file.
    """

    def __init__(
        self,
        source_id: str = "mock-camera",
        width: int = 640,
        height: int = 480,
        fps: int = 10,
        pattern: str = "color_bars"
    ):
        self.source_id = source_id
        self.width = width
        self.height = height
        self.fps = fps
        self.pattern = pattern
        self._is_opened = False
        self._frame_count = 0

    def open(self) -> bool:
        """Open the mock camera source."""
        self._is_opened = True
        return True

    def read_frame(self) -> Optional[Frame]:
        """Generate and return a deterministic synthetic test frame."""
        if not self._is_opened:
            return None

        self._frame_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        frame_id = f"mock-frame-{self._frame_count}-{uuid.uuid4().hex[:8]}"

        # Generate synthetic image data (H, W, 3)
        # Gradient pattern based on frame count for deterministic variety
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        c_val = (self._frame_count * 15) % 255
        img[:, :, 0] = c_val  # Blue channel
        img[:, :, 1] = 128    # Green channel
        img[:, :, 2] = (255 - c_val)  # Red channel

        return Frame(
            frame_id=frame_id,
            timestamp=now_iso,
            frame_index=self._frame_count,
            width=self.width,
            height=self.height,
            source_id=self.source_id,
            data=img,
            metadata={
                "synthetic": True,
                "pattern": self.pattern,
                "configured_fps": self.fps
            }
        )

    def release(self) -> None:
        """Close and release the mock source."""
        self._is_opened = False

    def is_opened(self) -> bool:
        """Check if mock camera is open."""
        return self._is_opened

    def get_properties(self) -> Dict[str, Any]:
        """Return mock camera properties."""
        return {
            "source_type": "mock",
            "source_id": self.source_id,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "pattern": self.pattern,
            "frame_count": self._frame_count,
            "is_opened": self._is_opened
        }
