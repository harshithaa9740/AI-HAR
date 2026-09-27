"""
AI Inference Subsystem Exceptions for AURAVISION Offline System
"""

class AIInferenceError(Exception):
    """Base exception for all AI perception and inference failures."""
    pass


class ModelInitializationError(AIInferenceError):
    """Raised when an AI model or provider fails to initialize or load weights."""
    pass


class ProviderUnavailableError(AIInferenceError):
    """Raised when a requested AI provider is not registered or unavailable."""
    pass


class InvalidFrameError(AIInferenceError):
    """Raised when an invalid or corrupt frame is passed to the inference pipeline."""
    pass
