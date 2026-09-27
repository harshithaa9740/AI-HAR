"""
AI Model Status, Registry, and Diagnostic Endpoints
"""
from fastapi import APIRouter
from typing import List, Dict, Any
from app.schemas.system import ModelsStatusResponse, ModelStatusItem
from app.services.detection_service import detection_service
from app.ml.model_registry import ModelRegistry
from app.core.config import settings

router = APIRouter(prefix="/models", tags=["AI Models"])


@router.get("/status", response_model=ModelsStatusResponse)
def get_models_status():
    """Returns the initialization, load status, and device info of all AI pipeline modules."""
    statuses = detection_service.get_models_status()
    items = [
        ModelStatusItem(
            name=s.get("name", "Unknown"),
            type=s.get("type", "UNKNOWN"),
            status=s.get("status", "MOCK"),
            backend=s.get("backend", "generic"),
            device=s.get("device", "cpu"),
            details=s.get("details", {})
        )
        for s in statuses
    ]
    return ModelsStatusResponse(
        ai_mode=settings.AI_MODE,
        models=items
    )


@router.get("/active")
def get_active_model():
    """Return metadata and capability info for the active AI Provider."""
    return ModelRegistry.get_active_model_info()


@router.get("")
@router.get("/")
def list_registered_models() -> List[Dict[str, Any]]:
    """List all registered AI providers in the ModelRegistry."""
    return ModelRegistry.list_models()
