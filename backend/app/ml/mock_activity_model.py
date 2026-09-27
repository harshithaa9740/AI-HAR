"""
Deterministic Mock Activity Recognition Model for Demonstration & Testing (Step 5)
Produces structured, deterministic ObservedAction observations without real AI models.
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import numpy as np
from app.ml.base_detector import BaseActivityRecognizer
from app.schemas.detection import BoundingBox, PoseResult, ActivityDetection, ObservedAction
from app.core.constants import DemoScenario


class MockActivityModel(BaseActivityRecognizer):
    """
    Deterministic Mock Activity Recognition Model.
    Provides predictable sequence of actions for testing and demonstration.
    """

    SCENARIO_SEQUENCES: Dict[str, List[Dict[str, Any]]] = {
        DemoScenario.NORMAL.value: [
            {"action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]},
            {"action_code": "OPEN_CONTAINER", "confidence": 0.93, "observed_objects": ["container"]},
            {"action_code": "TAKE_SAMPLE", "confidence": 0.94, "observed_objects": ["sample"]},
            {"action_code": "PLACE_SAMPLE", "confidence": 0.92, "observed_objects": ["sample", "container"]},
            {"action_code": "CLOSE_CONTAINER", "confidence": 0.96, "observed_objects": ["container"]},
        ],
        DemoScenario.SKIPPED_STEP.value: [
            {"action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]},
            {"action_code": "TAKE_SAMPLE", "confidence": 0.94, "observed_objects": ["sample"]},  # Skips step 2
        ],
        DemoScenario.OUT_OF_SEQUENCE.value: [
            {"action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]},
            {"action_code": "OPEN_CONTAINER", "confidence": 0.93, "observed_objects": ["container"]},
            {"action_code": "PICK_TOOL", "confidence": 0.95, "observed_objects": ["tool"]},  # Out of sequence when step 3 is expected
        ],
        DemoScenario.LOW_CONFIDENCE.value: [
            {"action_code": "PICK_TOOL", "confidence": 0.40, "observed_objects": ["tool"]},  # Low confidence < 0.70
        ],
        DemoScenario.UNKNOWN_ACTION.value: [
            {"action_code": "UNKNOWN_ACTION_TEST", "confidence": 0.90, "observed_objects": []},
        ],
        DemoScenario.MISSING_OBJECT.value: [
            {"action_code": "TAKE_SAMPLE", "confidence": 0.95, "observed_objects": []},  # Missing required "sample"
        ],
    }

    # Add legacy alias
    SCENARIO_SEQUENCES[DemoScenario.UNKNOWN_OBJECT.value] = SCENARIO_SEQUENCES[DemoScenario.UNKNOWN_ACTION.value]

    def __init__(self, scenario: Union[str, DemoScenario] = DemoScenario.NORMAL):
        self.scenario = self._normalize_scenario(scenario)
        self.current_step_index = 0

    @staticmethod
    def _normalize_scenario(scenario: Union[str, DemoScenario]) -> str:
        if isinstance(scenario, DemoScenario):
            return scenario.value
        if isinstance(scenario, str):
            val = scenario.upper().strip()
            if val in DemoScenario._value2member_map_:
                return val
            if val == "UNKNOWN_OBJECT":
                return DemoScenario.UNKNOWN_ACTION.value
        return DemoScenario.NORMAL.value

    def set_scenario(self, scenario: Union[str, DemoScenario]) -> None:
        """Set active scenario and reset step index to 0."""
        self.scenario = self._normalize_scenario(scenario)
        self.current_step_index = 0

    def reset(self) -> None:
        """Reset sequence index to beginning."""
        self.current_step_index = 0

    @property
    def total_observations(self) -> int:
        return len(self.SCENARIO_SEQUENCES.get(self.scenario, []))

    def get_all_observations(self) -> List[ObservedAction]:
        """Return all observations for current active scenario."""
        return self.get_scenario_observations(self.scenario)

    def get_observation(self, index: int) -> Optional[ObservedAction]:
        """Return observation at 0-based index."""
        sequence = self.SCENARIO_SEQUENCES.get(self.scenario, [])
        if 0 <= index < len(sequence):
            item = sequence[index]
            return ObservedAction(
                action_code=item["action_code"],
                confidence=item["confidence"],
                observed_objects=list(item.get("observed_objects", [])),
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "source": "mock",
                    "scenario": self.scenario,
                    "step_index": index + 1,
                    "total_steps": len(sequence)
                }
            )
        return None

    @classmethod
    def get_scenario_observations(cls, scenario: Union[str, DemoScenario]) -> List[ObservedAction]:
        """Return full list of deterministic observations for a scenario."""
        scen_name = cls._normalize_scenario(scenario)
        raw_items = cls.SCENARIO_SEQUENCES.get(scen_name, [])
        return [
            ObservedAction(
                action_code=item["action_code"],
                confidence=item["confidence"],
                observed_objects=list(item.get("observed_objects", [])),
                timestamp=datetime.now(timezone.utc),
                metadata={"source": "mock", "scenario": scen_name, "step_index": idx + 1}
            )
            for idx, item in enumerate(raw_items)
        ]


    def next_observation(self) -> Optional[ObservedAction]:
        """Obtain the next deterministic observation in the active scenario."""
        sequence = self.SCENARIO_SEQUENCES.get(self.scenario, [])
        if self.current_step_index >= len(sequence):
            return None

        item = sequence[self.current_step_index]
        self.current_step_index += 1

        return ObservedAction(
            action_code=item["action_code"],
            confidence=item["confidence"],
            observed_objects=list(item.get("observed_objects", [])),
            timestamp=datetime.now(timezone.utc),
            metadata={
                "source": "mock",
                "scenario": self.scenario,
                "step_index": self.current_step_index,
                "total_steps": len(sequence)
            }
        )

    def observe(self, scenario: Optional[str] = None, step_index: Optional[int] = None) -> Optional[ObservedAction]:
        """Deterministic observation lookup for given scenario and step index (1-based)."""
        scen_name = self._normalize_scenario(scenario) if scenario else self.scenario
        sequence = self.SCENARIO_SEQUENCES.get(scen_name, [])
        if not sequence:
            return None

        if step_index is not None:
            idx = (step_index - 1) % len(sequence)
        else:
            idx = self.current_step_index % len(sequence)

        item = sequence[idx]
        return ObservedAction(
            action_code=item["action_code"],
            confidence=item["confidence"],
            observed_objects=list(item.get("observed_objects", [])),
            timestamp=datetime.now(timezone.utc),
            metadata={"source": "mock", "scenario": scen_name, "step_index": idx + 1}
        )


    def predict(
        self,
        frames: Optional[List[np.ndarray]] = None,
        detections: Optional[List[BoundingBox]] = None,
        pose: Optional[PoseResult] = None
    ) -> ObservedAction:
        """Produce the next observation or default to next in scenario."""
        obs = self.next_observation()
        if obs:
            return obs
        # Fallback if sequence exhausted
        return ObservedAction(
            action_code="IDLE",
            confidence=0.99,
            observed_objects=[],
            timestamp=datetime.now(timezone.utc),
            metadata={"source": "mock", "scenario": self.scenario}
        )

    # Legacy compatibility methods
    def next_action(self) -> Optional[ActivityDetection]:
        obs = self.next_observation()
        if not obs:
            return None
        return ActivityDetection(
            action=obs.action_code,
            confidence=obs.confidence or 0.90,
            objects=obs.observed_objects,
            timestamp=obs.timestamp or datetime.now(timezone.utc),
            person_id=1,
            metadata=obs.metadata
        )

    def recognize_activity(
        self,
        frames: Optional[List[np.ndarray]] = None,
        detections: Optional[List[BoundingBox]] = None,
        pose: Optional[PoseResult] = None
    ) -> ActivityDetection:
        act = self.next_action()
        if act:
            return act
        return ActivityDetection(
            action="IDLE",
            confidence=0.99,
            objects=[],
            timestamp=datetime.now(timezone.utc)
        )

    def get_status(self) -> Dict[str, Any]:
        seq_len = len(self.SCENARIO_SEQUENCES.get(self.scenario, []))
        return {
            "name": "MockActivityModel",
            "type": "ACTIVITY_RECOGNITION",
            "status": "MOCK",
            "backend": "scenario_engine",
            "device": "cpu",
            "details": {
                "scenario": self.scenario,
                "current_index": self.current_step_index,
                "total_steps": seq_len,
                "note": "Deterministic Mock Activity Model (Development & Testing Adapter)"
            }
        }
