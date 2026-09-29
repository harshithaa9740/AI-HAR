"""
ML Model Factory & Provider for AURAVISION
Instantiates Activity Recognizer, Object Detector, and Pose Estimator based on system AI_MODE configuration.
"""
from typing import Optional, Any
from app.core.config import settings
from app.ml.base_detector import BaseObjectDetector, BasePoseEstimator, BaseActivityRecognizer
from app.ml.mock_detector import MockDetector, MockPoseEstimator
from app.ml.mock_activity_model import MockActivityModel
from app.core.logging import logger


class MLConfigurationError(ValueError):
    """Raised when an unconfigured or unsupported AI_MODE is selected."""
    pass


def get_activity_model(ai_mode: Optional[str] = None, scenario: Optional[Any] = None) -> BaseActivityRecognizer:
    """
    Factory function returning the configured Activity Recognition model.
    Currently supports AI_MODE="mock".
    Raises MLConfigurationError if an un-implemented mode is requested.
    """
    mode = (ai_mode or settings.AI_MODE).lower().strip()

    if mode in ("mock", "development"):
        return MockActivityModel(scenario=scenario) if scenario else MockActivityModel()
    elif mode == "real" or mode == "production":
        raise MLConfigurationError(
            f"AI_MODE '{mode}' requested, but real trained activity recognition model is not integrated in this phase. "
            "Please configure AI_MODE=mock."
        )
    else:
        raise MLConfigurationError(
            f"Unsupported AI_MODE '{mode}'. Valid configuration in this phase is 'mock'."
        )


def get_detector(
    ai_mode: Optional[str] = None,
    visible_objects: Optional[Any] = None,
    available_objects: Optional[Any] = None,
    include_person: bool = True
) -> BaseObjectDetector:
    """
    Factory function returning the configured Object Detector.
    Currently supports AI_MODE="mock".
    Raises MLConfigurationError if an un-implemented mode is requested.
    """
    mode = (ai_mode or settings.AI_MODE).lower().strip()

    if mode in ("mock", "development"):
        return MockDetector(
            visible_objects=visible_objects,
            available_objects=available_objects,
            include_person=include_person
        )
    elif mode in ("real", "yolo", "production"):
        raise MLConfigurationError(
            f"AI_MODE '{mode}' requested, but real YOLO detector weights are not integrated in this phase. "
            "Please configure AI_MODE=mock."
        )
    else:
        raise MLConfigurationError(
            f"Unsupported AI_MODE '{mode}'. Valid configuration in this phase is 'mock'."
        )



def get_pose_estimator(ai_mode: Optional[str] = None) -> BasePoseEstimator:
    """
    Factory function returning the configured Pose Estimator.
    Currently supports AI_MODE="mock".
    Raises MLConfigurationError if an un-implemented mode is requested.
    """
    mode = (ai_mode or settings.AI_MODE).lower().strip()

    if mode in ("mock", "development"):
        return MockPoseEstimator()
    elif mode in ("real", "mediapipe", "production"):
        raise MLConfigurationError(
            f"AI_MODE '{mode}' requested, but real MediaPipe pose estimator is not integrated in this phase. "
            "Please configure AI_MODE=mock."
        )
    else:
        raise MLConfigurationError(
            f"Unsupported AI_MODE '{mode}'. Valid configuration in this phase is 'mock'."
        )
