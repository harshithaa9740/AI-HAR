"""
Modular YOLO Object Detector Adapter with Graceful Fallback
"""
from typing import List, Dict, Any, Optional
import os
import numpy as np
from app.ml.base_detector import BaseObjectDetector
from app.ml.mock_detector import MockObjectDetector
from app.schemas.detection import BoundingBox
from app.core.config import settings
from app.core.logging import logger


class YOLOObjectDetector(BaseObjectDetector):
    """
    Adapter for YOLOv8/v11 models.
    Falls back gracefully to MockObjectDetector if weights or ultralytics library are missing.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.MODEL_OBJECT_PATH
        self.model = None
        self.is_loaded = False
        self.fallback = MockObjectDetector()
        self._initialize()

    def _initialize(self):
        if not self.model_path or not os.path.exists(self.model_path):
            logger.info("YOLO model weights not found at path; using MockObjectDetector fallback.")
            return

        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.is_loaded = True
            logger.info(f"Loaded YOLO model from {self.model_path}")
        except ImportError:
            logger.warning("Ultralytics package is not installed; continuing in Mock mode.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}; falling back to Mock.")

    def detect(self, frame: np.ndarray) -> List[BoundingBox]:
        if not self.is_loaded or self.model is None:
            return self.fallback.detect(frame)

        try:
            results = self.model(frame, verbose=False)
            boxes: List[BoundingBox] = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    label = self.model.names[cls_id] if hasattr(self.model, "names") else str(cls_id)
                    conf = float(box.conf[0].item())
                    xyxy = [int(v) for v in box.xyxy[0].tolist()]
                    boxes.append(BoundingBox(
                        label=label,
                        confidence=conf,
                        bbox=(xyxy[0], xyxy[1], xyxy[2], xyxy[3])
                    ))
            return boxes
        except Exception as e:
            logger.error(f"Error during YOLO inference: {e}")
            return self.fallback.detect(frame)

    def get_status(self) -> Dict[str, Any]:
        if self.is_loaded:
            return {
                "name": "YOLOObjectDetector",
                "type": "OBJECT_DETECTION",
                "status": "LOADED",
                "backend": "ultralytics_yolo",
                "device": "cpu/cuda",
                "details": {"model_path": self.model_path}
            }
        return self.fallback.get_status()
