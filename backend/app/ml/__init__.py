"""
AURAVISION ML Package
Provides modular perception, pose estimation, activity recognition interfaces, providers, and inference engines.
"""
from app.ml.base_detector import BaseObjectDetector, BasePoseEstimator, BaseActivityRecognizer
from app.ml.mock_detector import MockDetector, MockPoseEstimator, MockObjectDetector
from app.ml.mock_activity_model import MockActivityModel
from app.ml.model_provider import AIProvider
from app.ml.mock_provider import MockAIProvider
from app.ml.model_registry import ModelRegistry
from app.ml.inference_engine import InferenceEngine, inference_engine
from app.ml.frame_inference_interface import FrameInferenceEngine, MockFrameInferenceEngine
from app.ml.factory import get_activity_model, get_detector, get_pose_estimator, MLConfigurationError
from app.ml.exceptions import (
    AIInferenceError,
    ModelInitializationError,
    ProviderUnavailableError,
    InvalidFrameError,
)

__all__ = [
    "BaseObjectDetector",
    "BasePoseEstimator",
    "BaseActivityRecognizer",
    "MockDetector",
    "MockPoseEstimator",
    "MockObjectDetector",
    "MockActivityModel",
    "AIProvider",
    "MockAIProvider",
    "ModelRegistry",
    "InferenceEngine",
    "inference_engine",
    "FrameInferenceEngine",
    "MockFrameInferenceEngine",
    "get_activity_model",
    "get_detector",
    "get_pose_estimator",
    "MLConfigurationError",
    "AIInferenceError",
    "ModelInitializationError",
    "ProviderUnavailableError",
    "InvalidFrameError",
]
