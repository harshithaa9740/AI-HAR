"""
Abstract Camera Source Interface for AURAVISION Offline System
Defines the standard contract for all physical, file, and simulated video sources.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.camera.frame_model import Frame


class CameraSource(ABC):
    """
    Abstract base class for all frame ingestion sources.
    Decouples source acquisition mechanisms from downstream frame processing.
    """

    @abstractmethod
    def open(self) -> bool:
        """
        Initialize and open the underlying video/camera capture device or resource.
        Returns True if successfully opened, False or raises an exception otherwise.
        """
        pass

    @abstractmethod
    def read_frame(self) -> Optional[Frame]:
        """
        Capture or generate the next frame in the sequence.
        Returns a Frame instance, or None if the stream has ended or no frame is available.
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """
        Release hardware handles, close open files, and deallocate resources.
        """
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """
        Check whether the source is currently open and ready to yield frames.
        """
        pass

    @abstractmethod
    def get_properties(self) -> Dict[str, Any]:
        """
        Return source metadata, such as width, height, FPS, backend type, and source ID.
        """
        pass
