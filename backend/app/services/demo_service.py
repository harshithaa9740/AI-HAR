"""
Demonstration Service for Scenario Simulation & Controlled Mock AI Execution (Step 5)
Manages demo session state, steps through mock observations, and passes them to the Sequence Validator.
"""
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.constants import DemoScenario, ValidationResult
from app.ml.mock_activity_model import MockActivityModel
from app.ml.mock_detector import MockDetector
from app.schemas.detection import ObservedAction
from app.schemas.system import DemoStatusResponse
from app.services.experiment_service import experiment_service
from app.db.repository import EventRepository, SessionRepository
from app.core.logging import logger


class DemoService:
    """
    Service coordinating Mock AI scenario execution, perception recording,
    and deterministic sequence validation.
    """

    def __init__(self):
        self._models: Dict[str, MockActivityModel] = {}
        self._detectors: Dict[str, MockDetector] = {}
        self._states: Dict[str, Dict[str, Any]] = {}

    def get_or_create_model(self, session_id: Union[int, str], scenario: str = DemoScenario.NORMAL.value) -> MockActivityModel:
        sess_key = str(session_id)
        if sess_key not in self._models:
            self._models[sess_key] = MockActivityModel(scenario=scenario)
        return self._models[sess_key]

    def get_or_create_detector(self, session_id: Union[int, str]) -> MockDetector:
        sess_key = str(session_id)
        if sess_key not in self._detectors:
            self._detectors[sess_key] = MockDetector()
        return self._detectors[sess_key]

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """Return all 6 supported demonstration scenarios with descriptions."""
        return [
            {
                "name": DemoScenario.NORMAL.value,
                "description": "Step 1 to Step 5 executed in normal sequence with development confidence (0.92 - 0.96).",
                "expected_result": "VALID for steps 1-4, culminating in EXPERIMENT_COMPLETE on Step 5."
            },
            {
                "name": DemoScenario.SKIPPED_STEP.value,
                "description": "Astronaut performs Step 1 (PICK_TOOL), then prematurely executes Step 3 (TAKE_SAMPLE).",
                "expected_result": "STEP_SKIPPED warning alert, expected step remains OPEN_CONTAINER (Step 2)."
            },
            {
                "name": DemoScenario.OUT_OF_SEQUENCE.value,
                "description": "Astronaut performs Step 1, Step 2, then executes Step 1 again while expecting Step 3.",
                "expected_result": "OUT_OF_SEQUENCE warning alert, expected step remains TAKE_SAMPLE (Step 3)."
            },
            {
                "name": DemoScenario.LOW_CONFIDENCE.value,
                "description": "Step 1 (PICK_TOOL) executed with confidence 0.40 (< 0.70 threshold).",
                "expected_result": "VERIFY_REQUIRED alert, state does not advance."
            },
            {
                "name": DemoScenario.UNKNOWN_ACTION.value,
                "description": "Action UNKNOWN_ACTION_TEST observed which is not contained in protocol.",
                "expected_result": "UNKNOWN_ACTION warning alert, state does not advance."
            },
            {
                "name": DemoScenario.MISSING_OBJECT.value,
                "description": "Step 3 (TAKE_SAMPLE) observed with confidence 0.95 but observed_objects is empty.",
                "expected_result": "VERIFY_REQUIRED alert indicating required object 'sample' was not verified."
            }
        ]

    def start_demo(
        self,
        session_id: Union[int, str],
        scenario: Union[str, DemoScenario] = DemoScenario.NORMAL
    ) -> Dict[str, Any]:
        """Initialize mock demo scenario sequence for a session."""
        sess_key = str(session_id)
        scen_str = MockActivityModel._normalize_scenario(scenario)

        model = self.get_or_create_model(session_id, scenario=scen_str)
        model.set_scenario(scen_str)

        detector = self.get_or_create_detector(session_id)
        detector.clear_overrides()

        self._states[sess_key] = {
            "active": True,
            "scenario": scen_str,
            "session_id": session_id,
            "observations_generated": 0,
            "last_observation": None,
            "last_validation_result": None,
            "current_step": 1,
            "completed": False
        }

        logger.info(f"Demo Service: Started scenario '{scen_str}' for session {session_id}.")
        return {
            "status": "STARTED",
            "active": True,
            "scenario": scen_str,
            "session_id": session_id,
            "observations_total": len(MockActivityModel.SCENARIO_SEQUENCES.get(scen_str, [])),
            "observations_generated": 0,
            "mode": "DEMONSTRATION MODE",
            "message": f"Demonstration scenario '{scen_str}' initialized."
        }

    def execute_demo_step(
        self,
        db: Session,
        session_id: Union[int, str]
    ) -> Dict[str, Any]:
        """
        Execute exactly one mock observation step:
        1. Obtain next observation from MockActivityModel
        2. Record DetectionEvents in DB
        3. Pass observation to Sequence Validator through ExperimentService
        4. Return structured observation & validation result
        """
        sess_key = str(session_id)
        if sess_key not in self._states or not self._states[sess_key]["active"]:
            # Auto-start with NORMAL scenario
            self.start_demo(session_id, scenario=DemoScenario.NORMAL.value)

        demo_state = self._states[sess_key]
        model = self.get_or_create_model(session_id, scenario=demo_state["scenario"])
        detector = self.get_or_create_detector(session_id)

        # 1. Obtain next mock observation
        obs: Optional[ObservedAction] = model.next_observation()
        if not obs:
            logger.info(f"Demo Service: All observations exhausted for session {session_id}.")
            return {
                "session_id": session_id,
                "observation": None,
                "validation": None,
                "message": f"Scenario '{demo_state['scenario']}' has no further observations.",
                "completed": demo_state["completed"]
            }

        # 2. Record mock perception DetectionEvents in DB
        try:
            # Person detection
            EventRepository.record_detection(
                db=db,
                session_id=session_id,
                event_type="PERSON",
                object_name="astronaut",
                confidence=0.98,
                source="mock",
                metadata_json={"source": "mock", "scenario": demo_state["scenario"]}
            )

            # Object detections
            for obj_name in obs.observed_objects:
                EventRepository.record_detection(
                    db=db,
                    session_id=session_id,
                    event_type="OBJECT",
                    object_name=obj_name,
                    confidence=obs.confidence or 0.90,
                    source="mock",
                    metadata_json={"source": "mock", "action": obs.action_code}
                )
        except Exception as e:
            logger.warning(f"Failed to record mock detection event: {e}")

        # 3. Pass observation to Sequence Validator (SOLE state transition authority)
        val_res = experiment_service.validate_session_action(
            db=db,
            session_id=session_id,
            action_code=obs.action_code,
            confidence=obs.confidence,
            observed_objects=obs.observed_objects,
            metadata=obs.metadata
        )

        # 4. Update demo session state
        demo_state["observations_generated"] += 1
        demo_state["last_observation"] = obs.model_dump()
        demo_state["last_validation_result"] = val_res.result
        demo_state["current_step"] = val_res.next_step_number or val_res.expected_step_number
        demo_state["completed"] = val_res.completed

        return {
            "session_id": session_id,
            "current_observation_index": demo_state["observations_generated"],
            "observation": {
                "action_code": obs.action_code,
                "confidence": obs.confidence,
                "observed_objects": obs.observed_objects,
                "metadata": obs.metadata
            },
            "validation": {
                "result": val_res.result,
                "current_step_number": val_res.next_step_number or val_res.expected_step_number,
                "expected_step_number": val_res.expected_step_number,
                "expected_step_code": val_res.expected_step_code,
                "expected_action": val_res.expected_action,
                "observed_action": val_res.observed_action,
                "confidence": val_res.confidence,
                "message": val_res.message,
                "next_step_number": val_res.next_step_number,
                "next_step_code": val_res.next_step_code,
                "completed": val_res.completed
            }
        }

    def get_demo_status(self, session_id: Union[int, str]) -> DemoStatusResponse:
        """Return current status of mock demo execution for session."""
        sess_key = str(session_id)
        state = self._states.get(sess_key, {
            "active": False,
            "scenario": None,
            "session_id": session_id,
            "observations_generated": 0,
            "last_observation": None,
            "last_validation_result": None,
            "current_step": 1,
            "completed": False
        })
        return DemoStatusResponse(
            active=state["active"],
            scenario=state.get("scenario"),
            session_id=session_id,
            observations_generated=state.get("observations_generated", 0),
            last_observation=state.get("last_observation"),
            last_validation_result=state.get("last_validation_result"),
            current_step=state.get("current_step", 1),
            completed=state.get("completed", False)
        )

    def stop_demo(self, session_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """Stop active demo simulation for session without deleting historical data."""
        if session_id is not None:
            sess_key = str(session_id)
            if sess_key in self._states:
                self._states[sess_key]["active"] = False
        else:
            for s in self._states.values():
                s["active"] = False

        logger.info(f"Demo Service: Stopped demo for session {session_id}.")
        return {
            "status": "STOPPED",
            "active": False,
            "session_id": session_id,
            "message": "Demonstration mode stopped."
        }



demo_service = DemoService()
