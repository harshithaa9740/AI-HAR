"""
Direct Action Validation API Endpoint
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.detection import ValidateActionRequest
from app.schemas.event import SequenceValidationResponse
from app.services.experiment_service import experiment_service
from app.db.repository import SessionRepository

router = APIRouter(tags=["Validation"])


@router.post("/validate", response_model=SequenceValidationResponse)
def validate_action(payload: ValidateActionRequest, db: Session = Depends(get_db)):
    """
    Validate an action code against the experiment state machine.
    If session_id is supplied, state is persisted; otherwise evaluated against active or default experiment.
    """
    session_id = payload.session_id

    if session_id:
        session = SessionRepository.get_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return experiment_service.validate_session_action(
            db=db,
            session_id=session.id,
            action_code=payload.action_code,
            confidence=payload.confidence,
            observed_objects=payload.observed_objects,
            metadata=payload.metadata
        )

    # Ephemeral or default experiment validation
    exp = experiment_service.seed_default_experiment_if_empty(db)
    temp_session = experiment_service.start_session(db, exp.id)
    return experiment_service.validate_session_action(
        db=db,
        session_id=temp_session.id,
        action_code=payload.action_code,
        confidence=payload.confidence,
        observed_objects=payload.observed_objects,
        metadata=payload.metadata
    )
