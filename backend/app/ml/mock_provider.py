"""
Mock AI Provider for AURAVISION Offline System
Provides deterministic, offline AI perception without requiring GPU or external model weights.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.ml.model_provider import AIProvider
from app.camera.frame_model import Frame
from app.schemas.detection import DetectionResult, BoundingBox
from app.ml.mock_activity_model import MockActivityModel
from app.ml.mock_detector import MockDetector
from app.ml.exceptions import InvalidFrameError, ModelInitializationError
from app.core.logging import logger


class MockAIProvider(AIProvider):
    """
    Deterministic development and testing AI Provider.
    Implements full AIProvider interface with simulated object detections,
    pose keypoints, and activity classifications.
    """

    def __init__(
        self,
        scenario: str = "NORMAL",
        model_name: str = "auravision-mock-har",
        model_version: str = "0.1.0"
    ):
        self.scenario = scenario
        self.model_name = model_name
        self.model_version = model_version
        self._is_ready = False
        self._activity_model = MockActivityModel()
        self._detector = MockDetector()
        self._step_counter = 0

    def initialize(self) -> bool:
        """Initialize mock model components."""
        self._activity_model.set_scenario(self.scenario)
        self._activity_model.reset()
        self._step_counter = 0
        self._is_ready = True
        logger.info(f"MockAIProvider initialized with scenario '{self.scenario}'.")
        return True

    def set_scenario(self, scenario: str) -> None:
        """Dynamically switch mock simulation scenario."""
        self.scenario = scenario.upper().strip()
        self._activity_model.set_scenario(self.scenario)

    def reset(self) -> None:
        """Reset sequence progression counters."""
        self._activity_model.reset()
        self._step_counter = 0


    def infer(self, frame: Frame) -> Dict[str, Any]:
        """
        Perform mock inference on an incoming frame.
        """
        if not self._is_ready:
            self.initialize()

        if frame is None:
            raise InvalidFrameError("Cannot perform inference on None frame.")

        # Determine step index from frame metadata or internal sequence progression
        if frame.metadata and "step_index" in frame.metadata:
            step_idx = int(frame.metadata["step_index"])
        else:
            self._step_counter += 1
            step_idx = self._step_counter




        # 1. Produce deterministic observation for the step
        obs = self._activity_model.observe(scenario=self.scenario, step_index=step_idx)
        if obs is None:
            action_code = "NOOP"
            confidence = 0.99
            observed_objects: List[str] = []
        else:
            action_code = obs.action_code
            confidence = obs.confidence if obs.confidence is not None else 0.90
            observed_objects = list(obs.observed_objects)

        # 2. Produce simulated detection results with bounding boxes
        detections: List[DetectionResult] = []
        for idx, obj_name in enumerate(observed_objects):
            # Synthetic bounding boxes for evidence preservation
            x1 = 50 + (idx * 120)
            y1 = 60 + (idx * 80)
            x2 = x1 + 100
            y2 = y1 + 100
            detections.append(
                DetectionResult(
                    class_name=obj_name,
                    confidence=round(confidence, 2),
                    bounding_box={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    tracking_id=idx + 1,
                    metadata={"synthetic": True, "source_id": frame.source_id}
                )
            )

        return {
            "action_code": action_code,
            "confidence": confidence,
            "observed_objects": observed_objects,
            "detections": detections,
            "raw_output": {
                "scenario": self.scenario,
                "step_index": step_idx,
                "frame_id": frame.frame_id,
                "source_id": frame.source_id
            }
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return standardized model metadata distinguishing mock from production."""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "provider": "mock",
            "task": "human_activity_recognition",
            "local_path": None,
            "status": "development/mock",
            "device": "cpu",
            "active_scenario": self.scenario,
            "is_ready": self._is_ready
        }

    def shutdown(self) -> None:
        """Clean shutdown of mock provider."""
        self._is_ready = False
        logger.info("MockAIProvider shutdown complete.")

    def is_ready(self) -> bool:
        return self._is_ready
