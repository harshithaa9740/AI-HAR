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


from app.db import models


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
        target_session_id = session.id
    else:
        # Re-use current active running session or start a new persistent session
        exp = experiment_service.seed_default_experiment_if_empty(db)
        active_session = db.query(models.ExperimentSession).filter(
            models.ExperimentSession.experiment_id == exp.id,
            models.ExperimentSession.status == "RUNNING"
        ).order_by(models.ExperimentSession.id.desc()).first()

        if not active_session:
            active_session = experiment_service.start_session(db, exp.id)
        target_session_id = active_session.id

    resp = experiment_service.validate_session_action(
        db=db,
        session_id=target_session_id,
        action_code=payload.action_code,
        confidence=payload.confidence,
        observed_objects=payload.observed_objects,
        metadata=payload.metadata
    )
    resp.session_id = target_session_id
    resp.cloud_synced = True
    return resp
