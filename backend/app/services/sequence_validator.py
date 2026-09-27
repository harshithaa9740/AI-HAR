"""
Deterministic State Machine Sequence Validator for Experiment Protocol Validation
AURAVISION Core Business Logic Layer (Independent from AI frameworks, Web, Video, Audio)
"""
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from app.schemas.event import SequenceValidationResponse
from app.schemas.detection import ObservedAction
from app.core.constants import ValidationResult
from app.core.config import settings
from app.core.logging import logger


@dataclass
class StepDefinition:
    """Normalized experiment step definition."""
    step_number: int
    step_code: str
    name: str
    expected_action: str
    required_objects: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.70
    description: Optional[str] = None


@dataclass
class ExperimentValidatorState:
    """Session sequence progression state."""
    experiment_id: Union[int, str]
    session_id: Optional[Union[int, str]] = None
    steps: List[StepDefinition] = field(default_factory=list)
    current_step_number: int = 1
    current_step_code: Optional[str] = None
    expected_action: Optional[str] = None
    expected_next_step: Optional[str] = None
    completed: bool = False
    last_result: Optional[str] = None
    completed_steps: List[int] = field(default_factory=list)
    skipped_steps: List[int] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def current_step_index(self) -> int:
        return self.current_step_number

    @current_step_index.setter
    def current_step_index(self, val: int):
        self.current_step_number = val

    @property
    def is_completed(self) -> bool:
        return self.completed

    @is_completed.setter
    def is_completed(self, val: bool):
        self.completed = val


def _normalize_step(raw_step: Any, default_num: int = 1) -> StepDefinition:
    """Convert various step representations (dict, ORM, Pydantic) to StepDefinition."""
    if isinstance(raw_step, StepDefinition):
        return raw_step

    if isinstance(raw_step, dict):
        s_num = raw_step.get("step_number", default_num)
        s_code = raw_step.get("step_code") or f"STEP_{s_num:02d}"
        s_name = raw_step.get("name") or raw_step.get("display_name") or f"Step {s_num}"
        s_action = raw_step.get("expected_action") or raw_step.get("action_code") or "ACTION"
        s_desc = raw_step.get("description")
        s_conf = raw_step.get("confidence_threshold", 0.70)
        s_objs = raw_step.get("required_objects") if raw_step.get("required_objects") is not None else raw_step.get("expected_objects", [])
    else:
        s_num = getattr(raw_step, "step_number", default_num)
        s_code = getattr(raw_step, "step_code", None) or f"STEP_{s_num:02d}"
        s_name = getattr(raw_step, "name", None) or getattr(raw_step, "display_name", None) or f"Step {s_num}"
        s_action = getattr(raw_step, "expected_action", None) or getattr(raw_step, "action_code", None) or "ACTION"
        s_desc = getattr(raw_step, "description", None)
        s_conf = getattr(raw_step, "confidence_threshold", 0.70)
        s_objs = getattr(raw_step, "required_objects", None)
        if s_objs is None:
            s_objs = getattr(raw_step, "expected_objects", [])

    if isinstance(s_objs, str):
        try:
            parsed_objs = json.loads(s_objs)
            s_objs = parsed_objs if isinstance(parsed_objs, list) else []
        except Exception:
            s_objs = []
    elif not isinstance(s_objs, list):
        s_objs = []

    try:
        conf_val = float(s_conf) if s_conf is not None else 0.70
    except (ValueError, TypeError):
        conf_val = 0.70

    return StepDefinition(
        step_number=int(s_num),
        step_code=str(s_code),
        name=str(s_name),
        expected_action=str(s_action),
        required_objects=[str(o) for o in s_objs],
        confidence_threshold=conf_val,
        description=str(s_desc) if s_desc is not None else None
    )


class SequenceValidator:
    """
    Deterministic State Machine for Experiment Protocol Validation.
    Pure business-logic component: independent from ML, UI, audio, and hardware.
    """

    def __init__(self, confidence_threshold: Optional[float] = None):
        self.confidence_threshold = confidence_threshold or settings.CONFIDENCE_THRESHOLD
        self._states: Dict[str, ExperimentValidatorState] = {}

    def init_session_state(
        self,
        session_id: Union[int, str],
        experiment_id: Union[int, str],
        steps: List[Any],
        current_step_number: int = 1,
        completed: bool = False
    ) -> ExperimentValidatorState:
        """Initialize or reload the state machine for an experiment session."""
        normalized_steps = sorted(
            [_normalize_step(s, idx) for idx, s in enumerate(steps, start=1)],
            key=lambda s: s.step_number
        )

        step_map = {s.step_number: s for s in normalized_steps}
        curr_step = step_map.get(current_step_number)

        curr_code = curr_step.step_code if curr_step else (normalized_steps[0].step_code if normalized_steps else "STEP_01")
        curr_action = curr_step.expected_action if curr_step else (normalized_steps[0].expected_action if normalized_steps else None)

        next_step_def = step_map.get(current_step_number + 1)
        expected_next = f"{next_step_def.step_code} / {next_step_def.expected_action}" if next_step_def else None

        state = ExperimentValidatorState(
            experiment_id=experiment_id,
            session_id=session_id,
            steps=normalized_steps,
            current_step_number=current_step_number,
            current_step_code=curr_code,
            expected_action=curr_action,
            expected_next_step=expected_next,
            completed=completed,
            last_result=None,
            completed_steps=list(range(1, current_step_number)) if not completed else [s.step_number for s in normalized_steps],
            skipped_steps=[],
            history=[]
        )
        self._states[str(session_id)] = state
        return state

    def get_state(self, session_id: Union[int, str]) -> Optional[ExperimentValidatorState]:
        """Retrieve stored in-memory state for session."""
        return self._states.get(str(session_id))

    def reset_session(self, session_id: Union[int, str]) -> None:
        """Reset and remove session state from validator cache."""
        sess_key = str(session_id)
        if sess_key in self._states:
            del self._states[sess_key]

    def validate_action(
        self,
        action_code: str,
        confidence: Optional[float] = None,
        observed_objects: Optional[List[str]] = None,
        steps: Optional[List[Any]] = None,
        session_id: Optional[Union[int, str]] = None
    ) -> SequenceValidationResponse:
        """
        Validate an observed action against active experiment protocol state.
        Deterministic, offline, and safe.
        """
        observed_objects = observed_objects or []
        obs = ObservedAction(
            action_code=action_code,
            confidence=confidence,
            observed_objects=observed_objects
        )
        return self.validate_observation(obs, session_id=session_id, steps=steps)

    def validate_observation(
        self,
        observation: ObservedAction,
        session_id: Optional[Union[int, str]] = None,
        steps: Optional[List[Any]] = None
    ) -> SequenceValidationResponse:
        """
        Core Deterministic Validation State Machine.
        Evaluates already-determined observation against protocol sequence.
        """
        sess_key = str(session_id) if session_id is not None else None
        state = self._states.get(sess_key) if sess_key else None

        # If no active session state, initialize ephemeral state from steps
        if not state:
            if not steps:
                return SequenceValidationResponse(
                    result=ValidationResult.UNKNOWN_ACTION.value,
                    confidence=observation.confidence,
                    message="No experiment steps configured for validation.",
                    reason="Experiment definition missing."
                )
            state = self.init_session_state(
                session_id=sess_key or "ephemeral",
                experiment_id="ephemeral",
                steps=steps
            )

        protocol_steps = state.steps
        if not protocol_steps:
            return SequenceValidationResponse(
                result=ValidationResult.UNKNOWN_ACTION.value,
                confidence=observation.confidence,
                message="No steps in experiment protocol.",
                reason="Empty protocol."
            )

        step_map = {s.step_number: s for s in protocol_steps}
        action_to_step = {s.expected_action: s for s in protocol_steps}

        action_code = observation.action_code
        confidence = observation.confidence
        observed_objects = observation.observed_objects or []

        # -------------------------------------------------------------
        # 1. Check if experiment already complete (TEST 9 / CASE H)
        # -------------------------------------------------------------
        if state.completed:
            final_step = protocol_steps[-1]
            logger.info(f"Validation: Session {state.session_id} is already completed. Action '{action_code}' ignored.")
            return SequenceValidationResponse(
                result=ValidationResult.EXPERIMENT_COMPLETE.value,
                expected_step_number=final_step.step_number,
                expected_step_code=final_step.step_code,
                expected_action=final_step.expected_action,
                observed_action=action_code,
                confidence=confidence,
                message="Experiment protocol is already completed.",
                next_step_number=None,
                next_step_code=None,
                completed=True
            )

        # Get current expected step definition
        curr_step = step_map.get(state.current_step_number)
        if not curr_step:
            curr_step = protocol_steps[0]
            state.current_step_number = curr_step.step_number

        expected_step_num = curr_step.step_number
        expected_step_code = curr_step.step_code
        expected_action = curr_step.expected_action
        threshold = curr_step.confidence_threshold if curr_step.confidence_threshold is not None else self.confidence_threshold

        # -------------------------------------------------------------
        # 2. Check for Unknown Action (TEST 4 / CASE D)
        # -------------------------------------------------------------
        if action_code not in action_to_step:
            logger.warning(f"Validation: UNKNOWN_ACTION '{action_code}' observed. Expected: {expected_action} (Step {expected_step_num}).")
            state.last_result = ValidationResult.UNKNOWN_ACTION.value
            return SequenceValidationResponse(
                result=ValidationResult.UNKNOWN_ACTION.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Action '{action_code}' is not recognized in this experiment protocol.",
                next_step_number=expected_step_num,
                next_step_code=expected_step_code,
                next_step_name=curr_step.name,
                next_step_description=curr_step.description,
                reason=f"Action '{action_code}' does not match any protocol steps.",
                completed=False
            )

        target_step = action_to_step[action_code]
        observed_step_num = target_step.step_number
        observed_step_code = target_step.step_code

        # -------------------------------------------------------------
        # 3. Check Sequence Order
        # -------------------------------------------------------------

        # CASE B: SKIPPED STEP (observed_step > expected_step)
        if observed_step_num > expected_step_num:
            logger.warning(f"Validation: STEP_SKIPPED. Observed Step {observed_step_num} ({action_code}) while expecting Step {expected_step_num} ({expected_action}).")
            state.last_result = ValidationResult.STEP_SKIPPED.value
            # State remains unchanged!
            return SequenceValidationResponse(
                result=ValidationResult.STEP_SKIPPED.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Expected step {expected_action} was skipped.",
                next_step_number=expected_step_num,
                next_step_code=expected_step_code,
                next_step_name=curr_step.name,
                next_step_description=curr_step.description,
                observed_step=observed_step_num,
                reason=f"Step {expected_step_num} ({expected_action}) was skipped.",
                completed=False
            )

        # CASE C: OUT OF SEQUENCE (observed_step < expected_step)
        elif observed_step_num < expected_step_num:
            logger.warning(f"Validation: OUT_OF_SEQUENCE. Observed Step {observed_step_num} ({action_code}) after Step {expected_step_num} ({expected_action}) is expected.")
            state.last_result = ValidationResult.OUT_OF_SEQUENCE.value
            # State remains unchanged!
            return SequenceValidationResponse(
                result=ValidationResult.OUT_OF_SEQUENCE.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Out of sequence: Action '{action_code}' (Step {observed_step_num}) was observed, but expected Step {expected_step_num} ({expected_action}).",
                next_step_number=expected_step_num,
                next_step_code=expected_step_code,
                next_step_name=curr_step.name,
                next_step_description=curr_step.description,
                observed_step=observed_step_num,
                reason=f"Observed Step {observed_step_num} after it was already completed or out of order.",
                completed=False
            )

        # -------------------------------------------------------------
        # 4. Matching Step: Check Confidence Threshold (TEST 5 / CASE E)
        # -------------------------------------------------------------
        if confidence is None or confidence < threshold:
            conf_display = f"{confidence:.2f}" if confidence is not None else "None"
            logger.warning(f"Validation: VERIFY_REQUIRED for '{action_code}'. Low confidence ({conf_display} < {threshold:.2f}).")
            state.last_result = ValidationResult.VERIFY_REQUIRED.value
            return SequenceValidationResponse(
                result=ValidationResult.VERIFY_REQUIRED.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Confidence ({conf_display}) below required threshold ({threshold:.2f}). Human verification required.",
                next_step_number=expected_step_num,
                next_step_code=expected_step_code,
                next_step_name=curr_step.name,
                next_step_description=curr_step.description,
                observed_step=observed_step_num,
                reason="LOW_CONFIDENCE",
                completed=False
            )

        # -------------------------------------------------------------
        # 5. Matching Step: Check Required Objects (TEST 6, 7 / CASE G)
        # -------------------------------------------------------------
        if curr_step.required_objects:
            obs_normalized = {str(o).strip().lower() for o in observed_objects}
            for req_obj in curr_step.required_objects:
                req_norm = str(req_obj).strip().lower()
                if req_norm not in obs_normalized:
                    logger.warning(f"Validation: VERIFY_REQUIRED for '{action_code}'. Missing required object '{req_obj}'.")
                    state.last_result = ValidationResult.VERIFY_REQUIRED.value
                    return SequenceValidationResponse(
                        result=ValidationResult.VERIFY_REQUIRED.value,
                        expected_step_number=expected_step_num,
                        expected_step_code=expected_step_code,
                        expected_action=expected_action,
                        observed_action=action_code,
                        confidence=confidence,
                        message=f"Required object '{req_obj}' was not verified.",
                        next_step_number=expected_step_num,
                        next_step_code=expected_step_code,
                        next_step_name=curr_step.name,
                        next_step_description=curr_step.description,
                        observed_step=observed_step_num,
                        reason="OBJECT_NOT_DETECTED",
                        completed=False
                    )

        # -------------------------------------------------------------
        # 6. Exact Step Valid Match (CASE A & F: VALID / EXPERIMENT_COMPLETE)
        # -------------------------------------------------------------
        is_final_step = (expected_step_num == len(protocol_steps))
        state.completed_steps.append(observed_step_num)

        if is_final_step:
            state.completed = True
            state.last_result = ValidationResult.EXPERIMENT_COMPLETE.value
            state.expected_next_step = None
            logger.info(f"Validation: EXPERIMENT_COMPLETE! Final step {expected_step_num} ({action_code}) completed.")
            return SequenceValidationResponse(
                result=ValidationResult.EXPERIMENT_COMPLETE.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Step {expected_step_num} ({curr_step.name}) completed. Experiment protocol completed successfully!",
                next_step_number=None,
                next_step_code=None,
                completed=True,
                observed_step=observed_step_num,
                completed_step=expected_step_num
            )
        else:
            next_step_num = expected_step_num + 1
            next_step_def = step_map[next_step_num]
            state.current_step_number = next_step_num
            state.current_step_code = next_step_def.step_code
            state.expected_action = next_step_def.expected_action
            state.expected_next_step = f"{next_step_def.step_code} / {next_step_def.expected_action}"
            state.last_result = ValidationResult.VALID.value

            logger.info(f"Validation: VALID. Step {expected_step_num} completed. Advancing to Step {next_step_num} ({next_step_def.step_code}).")
            return SequenceValidationResponse(
                result=ValidationResult.VALID.value,
                expected_step_number=expected_step_num,
                expected_step_code=expected_step_code,
                expected_action=expected_action,
                observed_action=action_code,
                confidence=confidence,
                message=f"Expected step completed. Proceed to Step {next_step_num}: {next_step_def.name}.",
                next_step_number=next_step_num,
                next_step_code=next_step_def.step_code,
                next_step_name=next_step_def.name,
                next_step_description=next_step_def.description,
                observed_step=observed_step_num,
                completed_step=expected_step_num,
                completed=False
            )


sequence_validator = SequenceValidator()

