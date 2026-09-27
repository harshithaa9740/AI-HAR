"""
AI Inference REST API Endpoints for AURAVISION Offline System
Provides standalone frame inference, model metadata discovery, and provider inspection.
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional, List, Dict, Any

from app.schemas.detection import InferenceFrameRequest, InferenceFrameResponse
from app.ml.inference_engine import inference_engine
from app.ml.model_registry import ModelRegistry
from app.camera.frame_model import Frame
from app.camera.camera_manager import CameraManagerRegistry
from app.camera.mock_camera import MockCameraSource
from app.ml.exceptions import AIInferenceError, InvalidFrameError
from app.core.logging import logger

router = APIRouter(prefix="/inference", tags=["AI Inference"])


@router.post("/frame", response_model=InferenceFrameResponse)
def infer_frame(req: Optional[InferenceFrameRequest] = None):
    """
    Run AI perception and activity inference on a frame.
    Pulls the latest frame from the global camera buffer, or generates a deterministic development frame.
    """
    scenario_override = req.scenario if req else None
    step_idx = req.step_index if (req and req.step_index is not None) else 1

    # Attempt to retrieve latest frame from global camera buffer
    global_mgr = CameraManagerRegistry.get_global_manager()
    frame: Optional[Frame] = None
    if global_mgr.is_running():
        frame = global_mgr.read()

    # Fallback to deterministic test frame if global camera is stopped
    if frame is None:
        mock_source = MockCameraSource(source_id="inference-dev-frame")
        mock_source.open()
        # Advance mock source to step_idx
        for _ in range(step_idx):
            frame = mock_source.read_frame()
        mock_source.release()

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to obtain or generate frame for inference."
        )

    try:
        obs, detections = inference_engine.infer(frame, scenario_override=scenario_override)
        return InferenceFrameResponse(
            frame_id=frame.frame_id,
            action_code=obs.action_code,
            confidence=obs.confidence or 0.0,
            observed_objects=obs.observed_objects,
            detections=detections,
            timestamp=obs.timestamp.isoformat() if obs.timestamp else "",
            metadata=obs.metadata
        )
    except (AIInferenceError, InvalidFrameError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected inference failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference processing error: {str(e)}"
        )
