"""
Experiment Management, Protocol Validation, and Session Validation Orchestrator
"""
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db import models
from app.db.repository import (
    ExperimentRepository,
    SessionRepository,
    EventRepository,
    create_experiment as repo_create_experiment,
    get_experiment as repo_get_experiment,
    get_experiment_by_name,
    list_experiments as repo_list_experiments,
    update_experiment as repo_update_experiment,
    delete_experiment as repo_delete_experiment,
    create_step as repo_create_step,
    get_step as repo_get_step,
    get_steps_for_experiment as repo_get_steps,
    update_step as repo_update_step,
    delete_step as repo_delete_step,
    delete_steps_for_experiment
)
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentStepCreate,
    ExperimentStepUpdate,
    ProtocolResponse,
    ProtocolStepItem,
    ProtocolValidationResult
)
from app.schemas.event import SequenceValidationResponse
from app.core.constants import (
    SessionStatus,
    ValidationResult,
    AlertType,
    AlertSeverity,
    EventType
)
from app.services.sequence_validator import SequenceValidator
from app.services.alert_service import AlertService
from app.services.logging_service import SessionLoggingService
from app.services.websocket_service import ws_manager
from app.core.logging import logger


class ProtocolValidationError(ValueError):
    """Raised when an experiment protocol violates structural or validation rules."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class ExperimentService:
    def __init__(self):
        self.validator = SequenceValidator()

    # =====================================================================
    # PROTOCOL VALIDATION RULES (Deterministic, Rules 1-11)
    # =====================================================================

    @staticmethod
    def validate_protocol(
        steps: List[Union[dict, ExperimentStepCreate, models.ExperimentStep, Any]],
        name: Optional[str] = None
    ) -> ProtocolValidationResult:
        """
        Validate experiment protocol rules deterministically:
        RULE 1: Experiment name cannot be empty.
        RULE 2: Experiment must contain at least one step.
        RULE 3: step_number must be a positive integer (> 0).
        RULE 4: step_number values must be strictly sequential (1, 2, 3, ..., N).
        RULE 5: There must not be duplicate step numbers.
        RULE 6: step_code must be present and non-empty.
        RULE 7: step_code must be unique within an experiment.
        RULE 8: expected_action must be present and non-empty.
        RULE 9: confidence_threshold must be between 0.0 and 1.0.
        RULE 10: required_objects must be represented consistently.
        RULE 11: Protocol must be deterministic (no probabilistic validation).
        """
        errors: List[str] = []

        # RULE 1: Experiment name cannot be empty
        if name is not None and len(name.strip()) == 0:
            errors.append("Experiment name cannot be empty.")

        # RULE 2: Experiment must contain at least one step
        if not steps or len(steps) == 0:
            errors.append("Experiment protocol must contain at least one step.")
            return ProtocolValidationResult(valid=False, errors=errors)

        step_numbers: List[int] = []
        step_codes: List[str] = []

        for idx, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                s_num = step.get("step_number")
                s_code = step.get("step_code")
                s_action = step.get("expected_action") or step.get("action_code")
                s_conf = step.get("confidence_threshold", 0.70)
                s_objs = step.get("required_objects") if step.get("required_objects") is not None else step.get("expected_objects", [])
            elif hasattr(step, "step_number"):
                s_num = getattr(step, "step_number")
                s_code = getattr(step, "step_code", None)
                s_action = getattr(step, "expected_action", None) or getattr(step, "action_code", None)
                s_conf = getattr(step, "confidence_threshold", 0.70)
                s_objs = getattr(step, "required_objects", None)
                if s_objs is None:
                    s_objs = getattr(step, "expected_objects", [])
            else:
                errors.append(f"Step at index {idx} has unrecognized format.")
                continue

            # RULE 3: Positive integer step_number
            if s_num is None or not isinstance(s_num, int) or s_num <= 0:
                errors.append(f"Step at index {idx} has invalid step_number '{s_num}'; must be a positive integer.")
            else:
                step_numbers.append(s_num)

            # RULE 6: step_code must be present
            if not s_code or (isinstance(s_code, str) and len(s_code.strip()) == 0):
                errors.append(f"Step {s_num or idx} is missing required 'step_code'.")
            else:
                code_clean = str(s_code).strip()
                # RULE 7: Unique step_code within experiment
                if code_clean in step_codes:
                    errors.append(f"Duplicate step_code '{code_clean}' found at step {s_num or idx}.")
                else:
                    step_codes.append(code_clean)

            # RULE 8: expected_action must be present
            if not s_action or (isinstance(s_action, str) and len(s_action.strip()) == 0):
                errors.append(f"Step {s_num or idx} is missing required 'expected_action'.")

            # RULE 9: confidence_threshold between 0.0 and 1.0
            if s_conf is not None:
                try:
                    conf_val = float(s_conf)
                    if conf_val < 0.0 or conf_val > 1.0:
                        errors.append(f"Step {s_num or idx} has invalid confidence_threshold '{s_conf}'; must be between 0.0 and 1.0.")
                except (ValueError, TypeError):
                    errors.append(f"Step {s_num or idx} has invalid confidence_threshold format.")

            # RULE 10: required_objects consistency
            if isinstance(s_objs, str):
                try:
                    parsed = json.loads(s_objs)
                    if not isinstance(parsed, list):
                        errors.append(f"Step {s_num or idx} required_objects must be a list.")
                except Exception:
                    errors.append(f"Step {s_num or idx} required_objects string is not valid JSON.")
            elif not isinstance(s_objs, list):
                errors.append(f"Step {s_num or idx} required_objects must be a list of strings.")

        # RULE 5: No duplicate step numbers
        if len(step_numbers) != len(set(step_numbers)):
            errors.append("Duplicate step_number values found in protocol.")

        # RULE 4: Sequential step numbers starting from 1 to N
        expected_seq = list(range(1, len(steps) + 1))
        if sorted(step_numbers) != expected_seq:
            errors.append(f"Step numbers must be strictly sequential from 1 to {len(steps)}. Found: {sorted(step_numbers)}.")

        return ProtocolValidationResult(valid=len(errors) == 0, errors=errors)

    # =====================================================================
    # EXPERIMENT SERVICE CRUD OPERATIONS
    # =====================================================================

    def create_experiment(self, db: Session, payload: ExperimentCreate) -> models.Experiment:
        """
        Atomically create a new experiment protocol with its ordered steps.
        Enforces complete protocol validation before committing.
        """
        name = payload.name.strip()
        if not name:
            raise ProtocolValidationError(["Experiment name cannot be empty."])

        existing = get_experiment_by_name(db, name)
        if existing:
            raise ProtocolValidationError([f"Experiment with name '{name}' already exists."])

        # Validate steps protocol
        val_result = self.validate_protocol(payload.steps, name=name)
        if not val_result.valid:
            raise ProtocolValidationError(val_result.errors)

        try:
            exp = models.Experiment(
                name=name,
                description=payload.description,
                version=payload.version or "1.0",
                is_active=payload.is_active
            )
            db.add(exp)
            db.flush()  # Allocate exp.id

            sorted_steps = sorted(payload.steps, key=lambda s: s.step_number)
            for step_data in sorted_steps:
                objs_val = step_data.required_objects if step_data.required_objects is not None else step_data.expected_objects
                objs_str = json.dumps(objs_val) if isinstance(objs_val, list) else (objs_val or "[]")

                step = models.ExperimentStep(
                    experiment_id=exp.id,
                    step_number=step_data.step_number,
                    step_code=step_data.step_code or f"STEP_{step_data.step_number:02d}",
                    name=step_data.name or step_data.display_name or step_data.expected_action or f"Step {step_data.step_number}",
                    description=step_data.description,
                    expected_action=step_data.expected_action or step_data.action_code or "ACTION",
                    required_objects=objs_str,
                    confidence_threshold=step_data.confidence_threshold
                )
                db.add(step)

            db.commit()
            db.refresh(exp)
            return exp
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create experiment protocol: {e}")
            if isinstance(e, ProtocolValidationError):
                raise
            raise ProtocolValidationError([str(e)])

    def get_experiment(self, db: Session, experiment_id: Union[int, str]) -> Optional[models.Experiment]:
        """Retrieve an experiment by its primary key ID."""
        return repo_get_experiment(db, experiment_id)

    def list_experiments(self, db: Session, is_active_only: bool = False) -> List[models.Experiment]:
        """Retrieve all experiments, optionally filtering by active state."""
        return repo_list_experiments(db, is_active_only=is_active_only)

    def update_experiment(
        self,
        db: Session,
        experiment_id: Union[int, str],
        payload: ExperimentUpdate
    ) -> Optional[models.Experiment]:
        """
        Update experiment metadata and/or replace steps definition.
        Preserves existing steps when only updating metadata.
        """
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            return None

        # Check duplicate name if changing
        if payload.name is not None:
            name_clean = payload.name.strip()
            if not name_clean:
                raise ProtocolValidationError(["Experiment name cannot be empty."])
            if name_clean != exp.name:
                existing = get_experiment_by_name(db, name_clean)
                if existing:
                    raise ProtocolValidationError([f"Experiment with name '{name_clean}' already exists."])
            exp.name = name_clean

        if payload.description is not None:
            exp.description = payload.description
        if payload.version is not None:
            exp.version = payload.version
        if payload.is_active is not None:
            exp.is_active = payload.is_active
        elif payload.status is not None:
            exp.status = payload.status

        # If steps replacement requested, validate before applying
        if payload.steps is not None:
            val_result = self.validate_protocol(payload.steps, name=exp.name)
            if not val_result.valid:
                raise ProtocolValidationError(val_result.errors)

            try:
                # Delete existing steps and re-create
                db.query(models.ExperimentStep).filter(models.ExperimentStep.experiment_id == exp.id).delete()
                
                sorted_steps = sorted(payload.steps, key=lambda s: s.step_number)
                for step_data in sorted_steps:
                    objs_val = step_data.required_objects if step_data.required_objects is not None else step_data.expected_objects
                    objs_str = json.dumps(objs_val) if isinstance(objs_val, list) else (objs_val or "[]")

                    st = models.ExperimentStep(
                        experiment_id=exp.id,
                        step_number=step_data.step_number,
                        step_code=step_data.step_code or f"STEP_{step_data.step_number:02d}",
                        name=step_data.name or step_data.display_name or step_data.expected_action or f"Step {step_data.step_number}",
                        description=step_data.description,
                        expected_action=step_data.expected_action or step_data.action_code or "ACTION",
                        required_objects=objs_str,
                        confidence_threshold=step_data.confidence_threshold
                    )
                    db.add(st)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update experiment steps: {e}")
                raise ProtocolValidationError([str(e)])

        exp.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exp)
        return exp

    def delete_experiment(self, db: Session, experiment_id: Union[int, str]) -> bool:
        """Delete an experiment protocol and all its related steps/sessions."""
        return repo_delete_experiment(db, experiment_id)

    # =====================================================================
    # STEP CRUD OPERATIONS
    # =====================================================================

    def get_experiment_steps(self, db: Session, experiment_id: Union[int, str]) -> List[models.ExperimentStep]:
        """Retrieve ordered steps for an experiment, guaranteed sorted by step_number ascending."""
        return repo_get_steps(db, experiment_id)

    def get_step(self, db: Session, step_id: Union[int, str]) -> Optional[models.ExperimentStep]:
        """Retrieve an individual step by its primary key ID."""
        return repo_get_step(db, step_id)

    def add_step(
        self,
        db: Session,
        experiment_id: Union[int, str],
        step_payload: ExperimentStepCreate
    ) -> models.ExperimentStep:
        """Add a step to an experiment and validate that the resulting protocol remains valid."""
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        existing_steps = repo_get_steps(db, exp.id)
        simulated = list(existing_steps) + [step_payload]
        val_result = self.validate_protocol(simulated)
        if not val_result.valid:
            raise ProtocolValidationError(val_result.errors)

        return repo_create_step(
            db=db,
            experiment_id=exp.id,
            step_number=step_payload.step_number,
            step_code=step_payload.step_code or f"STEP_{step_payload.step_number:02d}",
            name=step_payload.name or step_payload.display_name or step_payload.expected_action or f"Step {step_payload.step_number}",
            expected_action=step_payload.expected_action or step_payload.action_code or "ACTION",
            description=step_payload.description,
            required_objects=step_payload.required_objects or step_payload.expected_objects,
            confidence_threshold=step_payload.confidence_threshold
        )

    def update_step(
        self,
        db: Session,
        experiment_id: Union[int, str],
        step_id: Union[int, str],
        step_payload: ExperimentStepUpdate
    ) -> Optional[models.ExperimentStep]:
        """Update an individual step and validate resulting protocol integrity."""
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        target_step = repo_get_step(db, step_id)
        if not target_step or target_step.experiment_id != exp.id:
            return None

        existing_steps = repo_get_steps(db, exp.id)
        simulated = []
        for s in existing_steps:
            if s.id == target_step.id:
                simulated_step = {
                    "step_number": step_payload.step_number if step_payload.step_number is not None else s.step_number,
                    "step_code": step_payload.step_code if step_payload.step_code is not None else s.step_code,
                    "name": step_payload.name if step_payload.name is not None else s.name,
                    "expected_action": (step_payload.expected_action or step_payload.action_code) if (step_payload.expected_action or step_payload.action_code) is not None else s.expected_action,
                    "description": step_payload.description if step_payload.description is not None else s.description,
                    "required_objects": (step_payload.required_objects if step_payload.required_objects is not None else (step_payload.expected_objects if step_payload.expected_objects is not None else json.loads(s.required_objects or "[]"))),
                    "confidence_threshold": step_payload.confidence_threshold if step_payload.confidence_threshold is not None else s.confidence_threshold
                }
                simulated.append(simulated_step)
            else:
                simulated.append(s)

        val_result = self.validate_protocol(simulated)
        if not val_result.valid:
            raise ProtocolValidationError(val_result.errors)

        update_kwargs: Dict[str, Any] = {}
        if step_payload.step_number is not None:
            update_kwargs["step_number"] = step_payload.step_number
        if step_payload.step_code is not None:
            update_kwargs["step_code"] = step_payload.step_code
        if step_payload.name is not None:
            update_kwargs["name"] = step_payload.name
        elif step_payload.display_name is not None:
            update_kwargs["name"] = step_payload.display_name
        if step_payload.expected_action is not None:
            update_kwargs["expected_action"] = step_payload.expected_action
        elif step_payload.action_code is not None:
            update_kwargs["expected_action"] = step_payload.action_code
        if step_payload.description is not None:
            update_kwargs["description"] = step_payload.description
        if step_payload.required_objects is not None:
            update_kwargs["required_objects"] = step_payload.required_objects
        elif step_payload.expected_objects is not None:
            update_kwargs["required_objects"] = step_payload.expected_objects
        if step_payload.confidence_threshold is not None:
            update_kwargs["confidence_threshold"] = step_payload.confidence_threshold

        return repo_update_step(db, target_step.id, **update_kwargs)

    def remove_step(self, db: Session, experiment_id: Union[int, str], step_id: Union[int, str]) -> bool:
        """Delete an individual step. Validates that remaining steps form a valid protocol."""
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        target_step = repo_get_step(db, step_id)
        if not target_step or target_step.experiment_id != exp.id:
            return False

        existing_steps = repo_get_steps(db, exp.id)
        remaining = [s for s in existing_steps if s.id != target_step.id]

        val_result = self.validate_protocol(remaining)
        if not val_result.valid:
            raise ProtocolValidationError(val_result.errors)

        return repo_delete_step(db, target_step.id)

    def reorder_steps(self, db: Session, experiment_id: Union[int, str], step_order: List[int]) -> List[models.ExperimentStep]:
        """Reorder steps according to a list of step IDs and re-index them sequentially 1..N."""
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        existing_steps = {s.id: s for s in repo_get_steps(db, exp.id)}
        if set(step_order) != set(existing_steps.keys()):
            raise ProtocolValidationError(["Step order list must include all existing step IDs exactly once."])

        for new_seq, s_id in enumerate(step_order, start=1):
            repo_update_step(db, s_id, step_number=new_seq)

        return repo_get_steps(db, exp.id)

    def get_protocol(self, db: Session, experiment_id: Union[int, str]) -> Optional[ProtocolResponse]:
        """Retrieve clean structured experiment protocol specification."""
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            return None

        steps = repo_get_steps(db, exp.id)
        protocol_steps = [
            ProtocolStepItem(
                step_number=s.step_number,
                step_code=s.step_code,
                name=s.name,
                expected_action=s.expected_action,
                required_objects=json.loads(s.required_objects or "[]") if isinstance(s.required_objects, str) else (s.required_objects or []),
                confidence_threshold=s.confidence_threshold
            )
            for s in steps
        ]

        return ProtocolResponse(
            experiment_id=exp.id,
            name=exp.name,
            version=exp.version,
            is_active=exp.is_active,
            step_count=len(protocol_steps),
            steps=protocol_steps
        )

    # =====================================================================
    # SEED DEFAULT PROTOCOL DATA
    # =====================================================================

    def seed_default_experiment_if_empty(self, db: Session) -> models.Experiment:
        """
        Seed default demonstration experiment if no experiments exist.
        NOTE: These are placeholder demonstration experiment steps for testing
        activity recognition and are NOT an actual spaceflight procedure.
        Does not automatically overwrite existing experiments.
        """
        existing = repo_list_experiments(db)
        if existing:
            return existing[0]

        logger.info("Seeding default Sample Astronaut Experiment (Placeholder Demo Data)...")
        exp = repo_create_experiment(
            db=db,
            name="Sample Astronaut Experiment",
            description="Placeholder demonstration protocol for astronaut sample handling testing. Not an actual spaceflight procedure.",
            version="1.0"
        )

        steps_data = [
            {
                "step_number": 1,
                "step_code": "STEP_01",
                "name": "Pick Tool",
                "expected_action": "PICK_TOOL",
                "description": "Retrieve sterilized extraction tool from rack.",
                "required_objects": ["tool"],
                "confidence_threshold": 0.70
            },
            {
                "step_number": 2,
                "step_code": "STEP_02",
                "name": "Open Container",
                "expected_action": "OPEN_CONTAINER",
                "description": "Unseal specimen containment vessel.",
                "required_objects": ["container"],
                "confidence_threshold": 0.70
            },
            {
                "step_number": 3,
                "step_code": "STEP_03",
                "name": "Take Sample",
                "expected_action": "TAKE_SAMPLE",
                "description": "Carefully extract sample core.",
                "required_objects": ["sample"],
                "confidence_threshold": 0.70
            },
            {
                "step_number": 4,
                "step_code": "STEP_04",
                "name": "Place Sample",
                "expected_action": "PLACE_SAMPLE",
                "description": "Transfer sample into analysis chamber.",
                "required_objects": ["sample", "container"],
                "confidence_threshold": 0.70
            },
            {
                "step_number": 5,
                "step_code": "STEP_05",
                "name": "Close Container",
                "expected_action": "CLOSE_CONTAINER",
                "description": "Reseal specimen containment vessel securely.",
                "required_objects": ["container"],
                "confidence_threshold": 0.70
            },
        ]

        for s in steps_data:
            repo_create_step(
                db=db,
                experiment_id=exp.id,
                step_number=s["step_number"],
                step_code=s["step_code"],
                name=s["name"],
                expected_action=s["expected_action"],
                description=s["description"],
                required_objects=s["required_objects"],
                confidence_threshold=s["confidence_threshold"]
            )

        logger.info(f"Default experiment created with ID: {exp.id}")
        return exp

    # =====================================================================
    # SESSION & VALIDATION RUNTIME ORCHESTRATION
    # =====================================================================

    def start_session(self, db: Session, experiment_id: Union[int, str], session_code: Optional[str] = None) -> models.ExperimentSession:
        exp = repo_get_experiment(db, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        code = session_code or f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        db_steps = repo_get_steps(db, exp.id)
        first_step = db_steps[0] if db_steps else None
        first_step_code = first_step.step_code if first_step else "STEP_01"
        expected_next = f"{first_step.step_code} / {first_step.expected_action}" if first_step else None

        session = SessionRepository.create_session(
            db,
            experiment_id=exp.id,
            session_code=code,
            status=SessionStatus.ACTIVE.value
        )
        session.current_step_number = 1
        session.current_step_code = first_step_code
        session.expected_next_step = expected_next
        db.commit()
        db.refresh(session)

        # Initialize validator state in memory
        self.validator.init_session_state(
            session_id=session.id,
            experiment_id=exp.id,
            steps=db_steps,
            current_step_number=1,
            completed=False
        )

        # Broadcast session start
        ws_manager.broadcast_sync(
            event_type=EventType.SYSTEM_STATUS.value,
            data={"session_id": session.id, "status": "STARTED", "session_code": code},
            session_id=session.id
        )

        return session

    def reset_session_sequence_state(self, db: Session, session_id: Union[int, str]) -> models.ExperimentSession:
        """Reset a session's sequence progression state to step 1 without deleting data."""
        session = SessionRepository.get_by_id(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        db_steps = repo_get_steps(db, session.experiment_id)
        first_step = db_steps[0] if db_steps else None
        first_code = first_step.step_code if first_step else "STEP_01"
        expected_next = f"{first_step.step_code} / {first_step.expected_action}" if first_step else None

        session.current_step_number = 1
        session.current_step_code = first_code
        session.expected_next_step = expected_next
        session.status = SessionStatus.ACTIVE.value
        session.ended_at = None
        db.commit()
        db.refresh(session)

        # Reset validator in-memory state
        self.validator.reset_session(session.id)
        self.validator.init_session_state(
            session_id=session.id,
            experiment_id=session.experiment_id,
            steps=db_steps,
            current_step_number=1,
            completed=False
        )

        # Record SystemEvent
        EventRepository.record_system_event(
            db=db,
            event_type="SESSION_RESET",
            message=f"Session {session.id} ({session.session_uuid}) sequence state reset to Step 1.",
            component="sequence_validator",
            metadata_json={"session_id": session.id, "experiment_id": session.experiment_id}
        )

        logger.info(f"Session {session.id} sequence state successfully reset to Step 1.")
        return session

    def validate_session_action(
        self,
        db: Session,
        session_id: Union[int, str],
        action_code: str,
        confidence: Optional[float] = None,
        observed_objects: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SequenceValidationResponse:
        """
        Validate an action against an experiment session with full persistence:
        1. Reads session state from database
        2. Evaluates deterministic sequence logic
        3. Updates session step in database (only when VALID / EXPERIMENT_COMPLETE)
        4. Records SequenceEvent in database
        5. Dispatches AlertEvent for deviations & completion
        """
        observed_objects = observed_objects or []
        metadata = metadata or {}

        session = SessionRepository.get_by_id(db, session_id)
        if not session:
            # Ephemeral fallback
            exp = self.seed_default_experiment_if_empty(db)
            db_steps = repo_get_steps(db, exp.id)
            return self.validator.validate_action(
                action_code=action_code,
                confidence=confidence,
                observed_objects=observed_objects,
                steps=db_steps
            )

        db_steps = repo_get_steps(db, session.experiment_id)
        is_completed = (session.status == SessionStatus.COMPLETED.value)
        curr_step_num = session.current_step_number or 1

        # Rehydrate validator memory state from DB
        val_state = self.validator.get_state(session.id)
        if not val_state or val_state.current_step_number != curr_step_num or val_state.completed != is_completed:
            val_state = self.validator.init_session_state(
                session_id=session.id,
                experiment_id=session.experiment_id,
                steps=db_steps,
                current_step_number=curr_step_num,
                completed=is_completed
            )

        # Run deterministic validation
        val_res = self.validator.validate_action(
            action_code=action_code,
            confidence=confidence,
            observed_objects=observed_objects,
            session_id=session.id
        )

        # Determine observed step number & code from protocol
        step_by_action = {s.expected_action: s for s in db_steps}
        obs_step_def = step_by_action.get(action_code)
        observed_step_num = obs_step_def.step_number if obs_step_def else None
        observed_step_code = obs_step_def.step_code if obs_step_def else None

        # 1. Record SequenceEvent in database
        EventRepository.record_sequence(
            db=db,
            session_id=session.id,
            expected_step=val_res.expected_step_number,
            expected_step_code=val_res.expected_step_code,
            observed_step=observed_step_num,
            observed_step_code=observed_step_code,
            result=val_res.result,
            reason=val_res.message,
            confidence=confidence,
            metadata=metadata
        )

        # 2. Audit Log Entry
        SessionLoggingService.log_step_event(
            session_id=session.id,
            session_code=session.session_uuid,
            step_number=observed_step_num or val_res.expected_step_number,
            action_code=action_code,
            result=val_res.result,
            confidence=confidence or 0.0,
            metadata={"objects": observed_objects, "message": val_res.message, **metadata}
        )

        # 3. Handle Database State Updates & Alerts
        if val_res.result == ValidationResult.VALID.value:
            # Advance DB session to next step
            session.current_step_number = val_res.next_step_number
            session.current_step_code = val_res.next_step_code
            if val_res.next_step_name:
                session.expected_next_step = f"{val_res.next_step_code} / {val_res.next_step_name}"
            if session.status not in (SessionStatus.STOPPED.value, SessionStatus.COMPLETED.value, SessionStatus.PAUSED.value):
                session.status = SessionStatus.RUNNING.value
            db.commit()
            db.refresh(session)

            # Broadcast step validated event
            ws_manager.broadcast_sync(
                event_type=EventType.STEP_VALIDATED.value,
                data={
                    "session_id": session.id,
                    "step_number": val_res.completed_step,
                    "action": action_code,
                    "confidence": confidence,
                    "next_step": val_res.next_step,
                    "next_step_name": val_res.next_step_name,
                    "message": val_res.message
                },
                session_id=session.id
            )

            # Step completed notification alert
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=AlertType.STEP_COMPLETED,
                severity=AlertSeverity.INFO,
                message=val_res.message,
                voice_prompt=f"Step {val_res.completed_step} completed. Proceed to step {val_res.next_step}."
            )

        elif val_res.result == ValidationResult.EXPERIMENT_COMPLETE.value:
            # Finalize session in DB
            session.status = SessionStatus.COMPLETED.value
            session.ended_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)

            # Create Alert for experiment completion
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=AlertType.EXPERIMENT_COMPLETE,
                severity=AlertSeverity.INFO,
                message="Experiment completed successfully.",
                voice_prompt="Experiment completed successfully."
            )

            ws_manager.broadcast_sync(
                event_type=EventType.EXPERIMENT_COMPLETE.value,
                data={"session_id": session.id, "message": "Experiment completed successfully."},
                session_id=session.id
            )

        elif val_res.result == ValidationResult.STEP_SKIPPED.value:
            # Create AlertEvent for skipped step (state remains unchanged)
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=AlertType.STEP_SKIPPED,
                severity=AlertSeverity.WARNING,
                message=val_res.message,
                voice_prompt=f"Warning. Step {val_res.expected_step_code} has not been completed."
            )
            ws_manager.broadcast_sync(
                event_type=EventType.STEP_SKIPPED.value,
                data={
                    "expected_step": val_res.expected_step_number,
                    "observed_step": observed_step_num,
                    "message": val_res.message
                },
                session_id=session.id
            )

        elif val_res.result == ValidationResult.OUT_OF_SEQUENCE.value:
            # Create AlertEvent for out of sequence (state remains unchanged)
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=AlertType.OUT_OF_SEQUENCE,
                severity=AlertSeverity.WARNING,
                message=val_res.message,
                voice_prompt="Warning. Unexpected action out of sequence."
            )
            ws_manager.broadcast_sync(
                event_type=EventType.OUT_OF_SEQUENCE.value,
                data={
                    "expected_step": val_res.expected_step_number,
                    "observed_step": observed_step_num,
                    "message": val_res.message
                },
                session_id=session.id
            )

        elif val_res.result == ValidationResult.UNKNOWN_ACTION.value:
            # Create AlertEvent for unknown action (state remains unchanged)
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=AlertType.UNKNOWN_ACTION,
                severity=AlertSeverity.WARNING,
                message=val_res.message,
                voice_prompt="Warning. Unknown action detected."
            )

        elif val_res.result == ValidationResult.VERIFY_REQUIRED.value:
            # Create AlertEvent for low confidence / missing object (state remains unchanged)
            alert_type = AlertType.OBJECT_NOT_DETECTED if ("object" in val_res.message.lower() or val_res.reason == "OBJECT_NOT_DETECTED") else AlertType.LOW_CONFIDENCE
            AlertService.create_and_dispatch_alert(
                db=db,
                session_id=session.id,
                alert_type=alert_type,
                severity=AlertSeverity.WARNING,
                message=val_res.message,
                voice_prompt="Verification required."
            )

        return val_res


experiment_service = ExperimentService()
