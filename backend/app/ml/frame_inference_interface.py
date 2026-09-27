"""
Frame Inference Interface for AURAVISION Offline System
Defines the clean contract where future AI inference engines consume transient Frames
and output standardized ObservedAction objects for the Sequence Validator.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from app.camera.frame_model import Frame
from app.schemas.detection import ObservedAction
from app.ml.mock_activity_model import MockActivityModel


class FrameInferenceEngine(ABC):
    """
    Abstract interface for AI perception engines that consume ingested video frames
    and generate standardized ObservedAction objects.
    """

    @abstractmethod
    def infer_action(self, frame: Frame) -> ObservedAction:
        """
        Consume a transient preprocessed Frame and produce an ObservedAction.
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return engine metadata and status."""
        pass


class MockFrameInferenceEngine(FrameInferenceEngine):
    """
    Mock inference engine demonstrating the Frame -> ObservedAction bridge
    without requiring real deep learning weights.
    """

    def __init__(self, activity_model: Optional[MockActivityModel] = None):
        self.activity_model = activity_model or MockActivityModel()

    def set_scenario(self, scenario: str) -> None:
        self.activity_model.set_scenario(scenario)

    def reset(self) -> None:
        self.activity_model.reset()

    def infer_action(self, frame: Frame) -> ObservedAction:
        """
        Produces deterministic action corresponding to the current step/frame.
        """
        # Uses frame properties / frame_index to guide mock observation
        step_idx = frame.frame_index if frame.frame_index > 0 else 1
        obs = self.activity_model.observe(step_index=step_idx)
        if obs is None:
            # Default action if step exceeds scenario length
            return ObservedAction(
                action_code="NOOP",
                confidence=0.99,
                observed_objects=[],
                metadata={"frame_id": frame.frame_id, "frame_index": frame.frame_index}
            )
        
        # Enrich metadata with frame tracking
        enriched_meta = dict(obs.metadata)
        enriched_meta.update({
            "source_frame_id": frame.frame_id,
            "source_frame_index": frame.frame_index,
            "source_id": frame.source_id
        })
        obs.metadata = enriched_meta
        return obs

    def get_status(self) -> Dict[str, Any]:
        return {
            "engine": "MockFrameInferenceEngine",
            "type": "FRAME_TO_ACTION_ADAPTER",
            "status": "READY",
            "model_status": self.activity_model.get_status()
        }
