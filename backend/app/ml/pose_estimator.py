"""
Modular Pose and Hand Estimator Adapter with Graceful Fallback
"""
from typing import Dict, Any, Optional
import numpy as np
from app.ml.base_detector import BasePoseEstimator
from app.ml.mock_detector import MockPoseEstimator
from app.schemas.detection import PoseResult, Keypoint
from app.core.logging import logger


class MediaPipePoseEstimator(BasePoseEstimator):
    """
    Adapter for MediaPipe Pose / Hands.
    Falls back gracefully to MockPoseEstimator if mediapipe is not installed.
    """

    def __init__(self):
        self.fallback = MockPoseEstimator()
        self.mp_pose = None
        self.pose_processor = None
        self.is_loaded = False
        self._initialize()

    def _initialize(self):
        try:
            import mediapipe as mp
            self.mp_pose = mp.solutions.pose
            self.pose_processor = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.is_loaded = True
            logger.info("MediaPipe Pose initialized successfully.")
        except ImportError:
            logger.info("MediaPipe not installed; using MockPoseEstimator.")
        except Exception as e:
            logger.warning(f"Failed to initialize MediaPipe Pose: {e}; using MockPoseEstimator.")

    def estimate_pose(self, frame: np.ndarray) -> Optional[PoseResult]:
        if not self.is_loaded or self.pose_processor is None:
            return self.fallback.estimate_pose(frame)

        try:
            import cv2
            h, w = frame.shape[:2]
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose_processor.process(image_rgb)
            
            if not results.pose_landmarks:
                return None

            keypoints = []
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                keypoints.append(Keypoint(
                    name=str(idx),
                    x=lm.x * w,
                    y=lm.y * h,
                    z=lm.z,
                    visibility=lm.visibility
                ))

            # Extract wrists as hand positions
            hand_positions = {}
            if len(keypoints) > 16:
                hand_positions["left_wrist"] = (keypoints[15].x, keypoints[15].y)
                hand_positions["right_wrist"] = (keypoints[16].x, keypoints[16].y)

            return PoseResult(
                person_id=1,
                keypoints=keypoints,
                hands_detected=bool(hand_positions),
                hand_positions=hand_positions
            )
        except Exception as e:
            logger.error(f"Error during pose estimation: {e}")
            return self.fallback.estimate_pose(frame)

    def get_status(self) -> Dict[str, Any]:
        if self.is_loaded:
            return {
                "name": "MediaPipePoseEstimator",
                "type": "POSE_ESTIMATION",
                "status": "LOADED",
                "backend": "mediapipe",
                "device": "cpu",
                "details": {"solution": "mediapipe.solutions.pose"}
            }
        return self.fallback.get_status()
