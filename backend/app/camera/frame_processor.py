"""
Frame Preprocessor for AURAVISION Offline System
Performs basic frame validation, dimension normalization, color space conversion, and indexing.
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import numpy as np
import cv2

from app.camera.frame_model import Frame


class FrameProcessor:
    """
    Lightweight, modular preprocessor for standardizing incoming frames before AI perception.
    
    Responsibilities:
    - Frame validation (dimensions, channel check)
    - Optional resizing to canonical resolution (target_width x target_height)
    - Basic color-space normalization (e.g., ensure standard 3-channel RGB or BGR)
    - Timestamp & frame metadata enrichment
    
    NOTE:
    Does NOT perform object detection, pose estimation, action recognition, or sequence validation.
    """

    def __init__(
        self,
        target_width: int = 640,
        target_height: int = 480,
        normalize_rgb: bool = False,
        target_fps: int = 10
    ):
        self.target_width = target_width
        self.target_height = target_height
        self.normalize_rgb = normalize_rgb
        self.target_fps = target_fps
        self._processed_count = 0

    def validate_frame(self, frame: Frame) -> bool:
        """
        Validate that the frame contains valid structure and non-empty image data if present.
        """
        if frame is None:
            return False
        if frame.data is not None:
            if not isinstance(frame.data, np.ndarray):
                return False
            if frame.data.size == 0:
                return False
            if len(frame.data.shape) not in (2, 3):
                return False
        return True

    def process(self, frame: Frame) -> Frame:
        """
        Preprocess an ingested Frame and return a standardized, AI-ready Frame.
        """
        if not self.validate_frame(frame):
            raise ValueError(f"Invalid frame received by FrameProcessor: {frame}")

        self._processed_count += 1
        processed_data = frame.data
        cur_w, cur_h = frame.width, frame.height

        if processed_data is not None:
            # 1. Resize if target dimensions differ
            h, w = processed_data.shape[:2]
            if (w != self.target_width or h != self.target_height) and self.target_width > 0 and self.target_height > 0:
                processed_data = cv2.resize(
                    processed_data,
                    (self.target_width, self.target_height),
                    interpolation=cv2.INTER_LINEAR
                )
                cur_w, cur_h = self.target_width, self.target_height

            # 2. Color space conversion if requested (BGR to RGB)
            if self.normalize_rgb and len(processed_data.shape) == 3 and processed_data.shape[2] == 3:
                processed_data = cv2.cvtColor(processed_data, cv2.COLOR_BGR2RGB)

        # 3. Clone or update metadata
        enriched_metadata = dict(frame.metadata)
        enriched_metadata.update({
            "processed": True,
            "processed_index": self._processed_count,
            "normalized_rgb": self.normalize_rgb,
            "target_fps": self.target_fps,
            "processed_timestamp": datetime.now(timezone.utc).isoformat()
        })

        return Frame(
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
            frame_index=frame.frame_index,
            width=cur_w,
            height=cur_h,
            source_id=frame.source_id,
            data=processed_data,
            metadata=enriched_metadata
        )

    def get_stats(self) -> Dict[str, Any]:
        """Return frame processor statistics."""
        return {
            "processed_count": self._processed_count,
            "target_width": self.target_width,
            "target_height": self.target_height,
            "normalize_rgb": self.normalize_rgb,
            "target_fps": self.target_fps
        }
