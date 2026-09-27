"""
Processing State Definitions and Transition Rules for AURAVISION Real-Time Processor
"""
from typing import Dict, List
from app.core.constants import ProcessingState


class InvalidProcessingStateTransitionError(ValueError):
    """Raised when an illegal real-time processor state transition is attempted."""
    def __init__(self, current_state: str, target_state: str, message: str = None):
        msg = message or f"Invalid processor transition from '{current_state}' to '{target_state}'."
        super().__init__(msg)
        self.current_state = current_state
        self.target_state = target_state


class ProcessingStateManager:
    """
    Validates and manages state transitions for the RealTimeProcessor:
    - STOPPED
    - STARTING
    - RUNNING
    - PAUSED
    - STOPPING
    - ERROR
    """

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        ProcessingState.STOPPED.value: [
            ProcessingState.STARTING.value,
            ProcessingState.STOPPED.value
        ],
        ProcessingState.STARTING.value: [
            ProcessingState.RUNNING.value,
            ProcessingState.ERROR.value,
            ProcessingState.STOPPED.value,
            ProcessingState.STOPPING.value
        ],
        ProcessingState.RUNNING.value: [
            ProcessingState.PAUSED.value,
            ProcessingState.STOPPING.value,
            ProcessingState.STOPPED.value,
            ProcessingState.ERROR.value
        ],
        ProcessingState.PAUSED.value: [
            ProcessingState.RUNNING.value,
            ProcessingState.STOPPING.value,
            ProcessingState.STOPPED.value,
            ProcessingState.ERROR.value
        ],
        ProcessingState.STOPPING.value: [
            ProcessingState.STOPPED.value,
            ProcessingState.ERROR.value
        ],
        ProcessingState.ERROR.value: [
            ProcessingState.STOPPED.value,
            ProcessingState.STARTING.value
        ]
    }

    @classmethod
    def validate_transition(cls, current_state: ProcessingState, target_state: ProcessingState) -> None:
        """Ensure the target state is permissible from current state."""
        curr_val = current_state.value if hasattr(current_state, "value") else str(current_state)
        tgt_val = target_state.value if hasattr(target_state, "value") else str(target_state)

        allowed = cls.VALID_TRANSITIONS.get(curr_val, [])
        if tgt_val not in allowed:
            raise InvalidProcessingStateTransitionError(
                current_state=curr_val,
                target_state=tgt_val,
                message=f"Cannot transition RealTimeProcessor from '{curr_val}' to '{tgt_val}'. Allowed: {allowed}"
            )
