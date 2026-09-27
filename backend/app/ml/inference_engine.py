"""
Inference Engine for AURAVISION Offline System
Coordinates frame execution through configured AI providers, measures inference timing,
normalizes detections, and generates standardized ObservedAction instances.
"""
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from app.camera.frame_model import Frame
from app.schemas.detection import ObservedAction, DetectionResult
from app.ml.model_registry import ModelRegistry
from app.ml.exceptions import AIInferenceError, InvalidFrameError
from app.core.logging import logger


class InferenceEngine:
    """
    Central AI Inference Engine.
    
    Responsibilities:
    1. Receive a preprocessed Frame
    2. Route to the active AIProvider (Mock, YOLO, ONNX, etc.)
    3. Measure inference execution latency (inference_time_ms)
    4. Normalize detections and preserve object evidence
    5. Package and emit standardized ObservedAction for the Sequence Validator
    
    IMPORTANT:
    Does NOT validate experiment protocols, advance session steps, or emit validation alerts.
    """

    def __init__(self, provider_name: Optional[str] = None):
        self.provider_name = provider_name

    def get_provider(self):
        """Resolve the active AI provider from the registry."""
        return ModelRegistry.get_provider(self.provider_name)

    def infer(
        self,
        frame: Frame,
        scenario_override: Optional[str] = None
    ) -> Tuple[ObservedAction, List[DetectionResult]]:
        """
        Run inference on a Frame and return (ObservedAction, List[DetectionResult]).
        """
        if frame is None:
            raise InvalidFrameError("Frame cannot be None for inference.")

        provider = self.get_provider()

        # Handle mock scenario override if supported by provider
        if scenario_override and hasattr(provider, "set_scenario"):
            provider.set_scenario(scenario_override)

        start_time = time.perf_counter()

        try:
            raw_res = provider.infer(frame)
        except Exception as e:
            logger.error(f"Inference execution failed on provider '{self.provider_name or 'active'}': {e}")
            raise AIInferenceError(f"AI inference error: {str(e)}")

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        model_info = provider.get_model_info()

        action_code = raw_res.get("action_code", "UNKNOWN_ACTION")
        confidence = float(raw_res.get("confidence", 0.0))
        observed_objects = list(raw_res.get("observed_objects", []))
        detections: List[DetectionResult] = raw_res.get("detections", [])

        # Build comprehensive metadata package
        metadata = {
            "source_frame_id": frame.frame_id,
            "source_frame_index": frame.frame_index,
            "source_id": frame.source_id,
            "inference_time_ms": elapsed_ms,
            "model_name": model_info.get("model_name"),
            "model_version": model_info.get("model_version"),
            "provider": model_info.get("provider"),
            "model_status": model_info.get("status"),
            "detections_count": len(detections),
            "detections": [d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in detections]
        }

        observed_action = ObservedAction(
            action_code=action_code,
            confidence=confidence,
            observed_objects=observed_objects,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata
        )

        return observed_action, detections

    def infer_action(self, frame: Frame) -> ObservedAction:
        """
        Convenience method producing only ObservedAction (for direct validator feed).
        """
        action, _ = self.infer(frame)
        return action


# Global singleton instance
inference_engine = InferenceEngine()
