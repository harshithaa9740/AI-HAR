"""
Deterministic Mock Object Detector and Pose Estimator for Development & Testing
Produces predictable perception entities (PERSON, OBJECT) without real AI models.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from app.ml.base_detector import BaseObjectDetector, BasePoseEstimator
from app.schemas.detection import BoundingBox, PoseResult, Keypoint


class MockDetector(BaseObjectDetector):
    """
    Deterministic Mock Detector for Development & Testing.
    Simulates PERSON (astronaut) and OBJECT (tool, container, sample) detections.
    """

    DEFAULT_ENTITIES = [
        {
            "entity_type": "PERSON",
            "entity_name": "astronaut",
            "confidence": 0.98,
            "bbox": [100, 100, 500, 600],
            "metadata": {"source": "mock", "role": "operator"}
        },
        {
            "entity_type": "OBJECT",
            "entity_name": "tool",
            "confidence": 0.95,
            "bbox": [150, 300, 250, 450],
            "metadata": {"source": "mock", "state": "available"}
        },
        {
            "entity_type": "OBJECT",
            "entity_name": "container",
            "confidence": 0.93,
            "bbox": [300, 320, 450, 480],
            "metadata": {"source": "mock", "state": "sealed"}
        },
        {
            "entity_type": "OBJECT",
            "entity_name": "sample",
            "confidence": 0.94,
            "bbox": [320, 350, 380, 420],
            "metadata": {"source": "mock", "state": "inside_container"}
        }
    ]

    def __init__(
        self,
        visible_objects: Optional[List[str]] = None,
        include_person: bool = True,
        available_objects: Optional[List[str]] = None,
        confidence_overrides: Optional[Dict[str, float]] = None
    ):
        self.include_person = include_person
        if available_objects is not None:
            self.visible_objects = list(available_objects)
        elif visible_objects is not None:
            self.visible_objects = list(visible_objects)
        else:
            self.visible_objects = ["tool", "container", "sample"]
        self.confidence_overrides: Dict[str, float] = dict(confidence_overrides or {})

    def detect_person(self) -> Dict[str, Any]:
        """Convenience method to retrieve simulated PERSON detection entity."""
        entities = self.detect_entities()
        for e in entities:
            if e["entity_type"] == "PERSON":
                return e
        return {
            "entity_type": "PERSON",
            "entity_name": "astronaut",
            "confidence": 0.98,
            "bbox": [100, 100, 500, 600],
            "metadata": {"source": "mock"}
        }

    def detect_objects(self) -> List[Dict[str, Any]]:
        """Convenience method to retrieve simulated OBJECT detection entities."""
        entities = self.detect_entities()
        return [e for e in entities if e["entity_type"] == "OBJECT"]

    def set_visible_objects(self, objects: List[str]):
        """Configure which object entities are visible in mock detections."""
        self.visible_objects = list(objects)

    def set_confidence_override(self, entity_name: str, confidence: float):
        """Override confidence for a specific entity (e.g. for low-confidence simulation)."""
        self.confidence_overrides[entity_name] = confidence


    def clear_overrides(self):
        """Reset confidence and visibility overrides to defaults."""
        self.visible_objects = ["tool", "container", "sample"]
        self.confidence_overrides.clear()
        self.include_person = True

    def detect_entities(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Return standardized entity detection records (PERSON, OBJECT)."""
        results: List[Dict[str, Any]] = []

        if self.include_person:
            person_conf = self.confidence_overrides.get("astronaut", 0.98)
            results.append({
                "entity_type": "PERSON",
                "entity_name": "astronaut",
                "confidence": person_conf,
                "bbox": [100, 100, 500, 600],
                "metadata": {"source": "mock"}
            })

        object_templates = {
            "tool": {"bbox": [150, 300, 250, 450], "conf": 0.95},
            "container": {"bbox": [300, 320, 450, 480], "conf": 0.93},
            "sample": {"bbox": [320, 350, 380, 420], "conf": 0.94},
            "chamber": {"bbox": [480, 250, 650, 500], "conf": 0.92}
        }

        for obj_name in self.visible_objects:
            tmpl = object_templates.get(obj_name, {"bbox": [200, 200, 300, 300], "conf": 0.90})
            conf = self.confidence_overrides.get(obj_name, tmpl["conf"])
            results.append({
                "entity_type": "OBJECT",
                "entity_name": obj_name,
                "confidence": conf,
                "bbox": tmpl["bbox"],
                "metadata": {"source": "mock"}
            })

        return results

    def detect(self, frame: Optional[np.ndarray] = None) -> List[BoundingBox]:
        """Return BoundingBox schemas for detected objects."""
        entities = self.detect_entities(frame)
        return [
            BoundingBox(
                label=e["entity_name"],
                confidence=e["confidence"],
                bbox=tuple(e["bbox"])
            )
            for e in entities
        ]

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "MockDetector",
            "type": "OBJECT_DETECTION",
            "status": "MOCK",
            "backend": "synthetic_mock_generator",
            "device": "cpu",
            "details": {
                "visible_objects": self.visible_objects,
                "include_person": self.include_person,
                "confidence_overrides": self.confidence_overrides,
                "note": "Deterministic Mock Detector (Development & Testing Adapter)"
            }
        }


# Alias for backward compatibility
MockObjectDetector = MockDetector


class MockPoseEstimator(BasePoseEstimator):
    """Mock pose and hand tracking estimator."""

    def estimate_pose(self, frame: Optional[np.ndarray] = None) -> Optional[PoseResult]:
        h, w = (720, 1280)
        keypoints = [
            Keypoint(name="nose", x=0.5 * w, y=0.2 * h, visibility=0.98),
            Keypoint(name="left_shoulder", x=0.42 * w, y=0.3 * h, visibility=0.95),
            Keypoint(name="right_shoulder", x=0.58 * w, y=0.3 * h, visibility=0.95),
            Keypoint(name="left_elbow", x=0.38 * w, y=0.45 * h, visibility=0.92),
            Keypoint(name="right_elbow", x=0.62 * w, y=0.45 * h, visibility=0.92),
            Keypoint(name="left_wrist", x=0.35 * w, y=0.6 * h, visibility=0.90),
            Keypoint(name="right_wrist", x=0.65 * w, y=0.6 * h, visibility=0.90),
        ]
        return PoseResult(
            person_id=1,
            keypoints=keypoints,
            hands_detected=True,
            hand_positions={
                "left_hand": (0.35 * w, 0.6 * h),
                "right_hand": (0.65 * w, 0.6 * h)
            }
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "MockPoseEstimator",
            "type": "POSE_ESTIMATION",
            "status": "MOCK",
            "backend": "synthetic_mock_generator",
            "device": "cpu",
            "details": {
                "keypoint_count": 7,
                "hands_tracked": True,
                "note": "Deterministic Mock Pose Estimator"
            }
        }
