"""
Modular Human Activity Recognition (HAR) Engine
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from app.ml.base_detector import BaseActivityRecognizer
from app.ml.mock_activity_model import MockActivityModel
from app.schemas.detection import BoundingBox, PoseResult, ActivityDetection, ObservedAction
from app.core.config import settings
from app.core.logging import logger


class ActivityRecognitionModel(BaseActivityRecognizer):
    """
    Spatiotemporal activity recognizer combining pose keypoints, object interactions,
    and temporal buffer windows.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.MODEL_ACTIVITY_PATH
        self.fallback = MockActivityModel()
        self.is_loaded = False
        self._initialize()

    def _initialize(self):
        if self.model_path and False:  # Placeholder for custom ONNX / PyTorch HAR model weights
            self.is_loaded = True
        else:
            # Running in standard modular mode with mock/heuristic engine
            logger.info("HAR Model using modular heuristic/scenario activity engine.")

    def set_scenario(self, scenario):
        self.fallback.set_scenario(scenario)

    def reset(self):
        self.fallback.reset()

    def recognize_activity(
        self,
        frames: List[np.ndarray],
        detections: List[BoundingBox],
        pose: Optional[PoseResult]
    ) -> ActivityDetection:
        if not self.is_loaded:
            return self.fallback.recognize_activity(frames, detections, pose)

        # Heuristic Spatiotemporal Fusion when real video is active
        # Hand-object proximity heuristic
        if pose and pose.hands_detected and detections:
            detected_labels = [d.label.lower() for d in detections if d.confidence >= settings.OBJECT_CONFIDENCE_THRESHOLD]
            
            if "tool" in detected_labels:
                return ActivityDetection(
                    action="PICK_TOOL",
                    confidence=0.91,
                    objects=["tool"],
                    timestamp=datetime.now(timezone.utc)
                )
            elif "container" in detected_labels and "sample" in detected_labels:
                return ActivityDetection(
                    action="TAKE_SAMPLE",
                    confidence=0.89,
                    objects=["container", "sample"],
                    timestamp=datetime.now(timezone.utc)
                )
            elif "container" in detected_labels:
                return ActivityDetection(
                    action="OPEN_CONTAINER",
                    confidence=0.88,
                    objects=["container"],
                    timestamp=datetime.now(timezone.utc)
                )

        return self.fallback.recognize_activity(frames, detections, pose)

    def predict(
        self,
        frames: Optional[List[np.ndarray]] = None,
        detections: Optional[List[BoundingBox]] = None,
        pose: Optional[PoseResult] = None
    ) -> ObservedAction:
        """Standardized prediction generating ObservedAction."""
        if not self.is_loaded:
            return self.fallback.predict(frames, detections, pose)
        
        legacy = self.recognize_activity(frames or [], detections or [], pose)
        return ObservedAction(
            action_code=legacy.action,
            confidence=legacy.confidence,
            observed_objects=legacy.objects,
            timestamp=legacy.timestamp,
            metadata={"source": "har_model"}
        )

    def observe(self, scenario: Optional[str] = None, step_index: Optional[int] = None) -> Optional[ObservedAction]:
        """Produce deterministic mock observation for a given scenario & step index."""
        return self.fallback.observe(scenario, step_index)

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "ActivityRecognitionModel",
            "type": "ACTIVITY_RECOGNITION",
            "status": "LOADED" if self.is_loaded else "MOCK",
            "backend": "spatiotemporal_fusion_engine",
            "device": "cpu",
            "details": {
                "active_fallback": self.fallback.get_status()
            }
        }

