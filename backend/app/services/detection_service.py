"""
AI Detection and Processing Orchestrator
"""
from typing import List, Dict, Any, Optional
import numpy as np
from app.ml.yolo_detector import YOLOObjectDetector
from app.ml.pose_estimator import MediaPipePoseEstimator
from app.ml.activity_model import ActivityRecognitionModel
from app.schemas.detection import BoundingBox, PoseResult, ActivityDetection
from app.core.config import settings
from app.core.constants import DemoScenario


class DetectionService:
    """Orchestrates modular detectors and processors."""

    def __init__(self):
        self.object_detector = YOLOObjectDetector()
        self.pose_estimator = MediaPipePoseEstimator()
        self.activity_recognizer = ActivityRecognitionModel()

    def set_demo_scenario(self, scenario: DemoScenario):
        self.activity_recognizer.set_scenario(scenario)

    def reset_demo(self):
        self.activity_recognizer.reset()

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Run object detection, pose estimation, and temporal activity recognition."""
        boxes: List[BoundingBox] = self.object_detector.detect(frame)
        pose: Optional[PoseResult] = self.pose_estimator.estimate_pose(frame)
        activity: ActivityDetection = self.activity_recognizer.recognize_activity([frame], boxes, pose)

        return {
            "boxes": [b.model_dump() for b in boxes],
            "pose": pose.model_dump() if pose else None,
            "activity": activity.model_dump()
        }

    def get_models_status(self) -> List[Dict[str, Any]]:
        return [
            self.object_detector.get_status(),
            self.pose_estimator.get_status(),
            self.activity_recognizer.get_status()
        ]


detection_service = DetectionService()
