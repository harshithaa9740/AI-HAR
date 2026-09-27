"""
Abstract Base Classes for AI / ML Detectors and Processors
Defines generic interfaces for Object Detection, Pose Estimation, and Activity Recognition.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from app.schemas.detection import BoundingBox, PoseResult, ActivityDetection, ObservedAction


class BaseObjectDetector(ABC):
    """Abstract interface for offline object detection."""

    @abstractmethod
    def detect(self, frame: Optional[np.ndarray] = None) -> List[BoundingBox]:
        """Detect visible objects and entities in a video frame or mock context."""
        pass

    def detect_entities(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Return standardized entity detection records (PERSON, OBJECT)."""
        boxes = self.detect(frame)
        entities = []
        for box in boxes:
            entity_type = "PERSON" if box.label.lower() in ("person", "astronaut", "human") else "OBJECT"
            entities.append({
                "entity_type": entity_type,
                "entity_name": box.label,
                "confidence": box.confidence,
                "bbox": list(box.bbox),
                "metadata": {"source": "detector"}
            })
        return entities

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return model metadata, mode, and health."""
        pass


class BasePoseEstimator(ABC):
    """Abstract interface for offline pose and hand estimation."""

    @abstractmethod
    def estimate_pose(self, frame: Optional[np.ndarray] = None) -> Optional[PoseResult]:
        """Estimate human landmarks and hand positions."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return pose estimator metadata, mode, and health."""
        pass


class BaseActivityRecognizer(ABC):
    """Abstract interface for Human Activity Recognition (HAR)."""

    @abstractmethod
    def predict(
        self,
        frames: Optional[List[np.ndarray]] = None,
        detections: Optional[List[BoundingBox]] = None,
        pose: Optional[PoseResult] = None
    ) -> ObservedAction:
        """Infer and produce a standardized ObservedAction from perception inputs."""
        pass

    @abstractmethod
    def observe(self, scenario: Optional[str] = None, step_index: Optional[int] = None) -> Optional[ObservedAction]:
        """Produce deterministic mock observation for a given scenario & step index."""
        pass

    @abstractmethod
    def recognize_activity(
        self,
        frames: Optional[List[np.ndarray]] = None,
        detections: Optional[List[BoundingBox]] = None,
        pose: Optional[PoseResult] = None
    ) -> ActivityDetection:
        """Legacy compatibility method returning ActivityDetection."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return activity recognizer metadata, mode, and health."""
        pass

