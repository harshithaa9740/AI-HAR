"""
AI Model Provider Interface for AURAVISION Offline System
Defines the standard contract for all machine learning and mock perception backends.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.camera.frame_model import Frame


class AIProvider(ABC):
    """
    Abstract base class for all AI perception providers.
    Decouples underlying model execution (Mock, YOLO, ONNX, PyTorch) from downstream pipelines.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize provider, load offline model weights, and prepare execution contexts.
        Returns True if successfully initialized, or raises ModelInitializationError.
        """
        pass

    @abstractmethod
    def infer(self, frame: Frame) -> Dict[str, Any]:
        """
        Run inference on an ingested preprocessed Frame.
        Returns dictionary containing:
        - action_code: str
        - confidence: float
        - observed_objects: List[str]
        - detections: List[DetectionResult]
        - raw_output: Dict[str, Any]
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Return provider and model metadata:
        - model_name: str
        - model_version: str
        - provider: str
        - task: str
        - local_path: Optional[str]
        - status: str ("development/mock", "trained/production", etc.)
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Cleanly release model handles, memory buffers, and device contexts.
        """
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if provider is initialized and ready to receive frames.
        """
        pass
