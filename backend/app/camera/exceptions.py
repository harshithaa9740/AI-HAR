"""
Camera Subsystem Exceptions for AURAVISION Offline System
"""

class CameraError(Exception):
    """Base exception for all camera and video ingestion errors."""
    pass


class CameraNotFoundError(CameraError):
    """Raised when a camera source, device index, or session camera is not found."""
    pass


class CameraSourceError(CameraError):
    """Raised when an underlying camera hardware or video stream cannot be opened or configured."""
    pass


class CameraAlreadyRunningError(CameraError):
    """Raised when attempting to start a camera manager that is already active/running."""
    pass


class CameraStoppedError(CameraError):
    """Raised when attempting to read or operate on a camera manager that is stopped."""
    pass


class InvalidVideoFileError(CameraError):
    """Raised when a specified local video file does not exist, is invalid, or cannot be decoded."""
    pass


class FrameReadError(CameraError):
    """Raised when a frame cannot be read from the source."""
    pass
