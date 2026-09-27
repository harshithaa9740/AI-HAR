"""
Model Registry for AURAVISION Offline System
Provides centralized registration, metadata discovery, and provider selection for AI inference backends.
"""
import threading
from typing import Dict, Any, Optional, List

from app.ml.model_provider import AIProvider
from app.ml.mock_provider import MockAIProvider
from app.ml.exceptions import ProviderUnavailableError
from app.core.config import settings
from app.core.logging import logger


class ModelRegistry:
    """
    Registry for managing AI perception providers and discovering model metadata.
    Ensures safe switching between mock/development and future local production models.
    """
    _providers: Dict[str, AIProvider] = {}
    _active_provider_name: str = "mock"
    _lock = threading.Lock()

    @classmethod
    def register_provider(cls, name: str, provider: AIProvider) -> None:
        """Register a new AI provider instance."""
        with cls._lock:
            key = name.lower().strip()
            cls._providers[key] = provider
            logger.info(f"Registered AI Provider '{key}'.")

    @classmethod
    def get_provider(cls, name: Optional[str] = None) -> AIProvider:
        """Retrieve registered provider by name or active default."""
        with cls._lock:
            key = (name or cls._active_provider_name).lower().strip()
            if key not in cls._providers:
                if key == "mock":
                    # Lazy initialize default mock provider
                    mock = MockAIProvider()
                    mock.initialize()
                    cls._providers["mock"] = mock
                else:
                    raise ProviderUnavailableError(f"AI Provider '{key}' is not registered.")
            return cls._providers[key]

    @classmethod
    def set_active_provider(cls, name: str) -> None:
        """Set the system-wide active AI provider."""
        with cls._lock:
            key = name.lower().strip()
            if key not in cls._providers and key != "mock":
                raise ProviderUnavailableError(f"Cannot set active provider: '{key}' not found.")
            cls._active_provider_name = key
            logger.info(f"Active AI Provider switched to '{key}'.")

    @classmethod
    def get_active_model_info(cls) -> Dict[str, Any]:
        """Return metadata for the currently active AI provider."""
        provider = cls.get_provider()
        return provider.get_model_info()

    @classmethod
    def list_models(cls) -> List[Dict[str, Any]]:
        """List metadata for all registered AI providers."""
        with cls._lock:
            # Ensure mock is registered
            if "mock" not in cls._providers:
                cls._providers["mock"] = MockAIProvider()
            
            result = []
            for name, prov in cls._providers.items():
                info = prov.get_model_info()
                info["is_active"] = (name == cls._active_provider_name)
                result.append(info)
            return result

    @classmethod
    def reset(cls) -> None:
        """Reset registry to default state."""
        with cls._lock:
            for prov in cls._providers.values():
                if prov.is_ready():
                    prov.shutdown()
            cls._providers.clear()
            cls._active_provider_name = "mock"


# Initialize default mock provider upon module load
ModelRegistry.register_provider("mock", MockAIProvider())
