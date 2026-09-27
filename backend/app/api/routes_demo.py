"""
SIH Demonstration Scenarios Control Endpoints (Step 5)
Provides manual step execution, scenario initialization, status tracking, and scenario listing.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.schemas.system import (
    DemoStartRequest,
    DemoStepRequest,
    DemoStopRequest,
    DemoStatusResponse
)
from app.core.constants import DemoScenario
from app.services.demo_service import demo_service
from app.services.experiment_service import experiment_service
from app.core.logging import logger

router = APIRouter(prefix="/demo", tags=["Demonstration Mode"])


@router.get("/scenarios")
def list_demo_scenarios():
    """List available offline demonstration scenarios."""
    return {
        "mode": "DEMONSTRATION MODE",
        "description": "Deterministic mock scenarios for offline experiment sequence evaluation.",
        "scenarios": demo_service.list_scenarios()
    }


@router.post("/start")
def start_demo(payload: DemoStartRequest, db: Session = Depends(get_db)):
    """
    Initialize a deterministic mock demonstration scenario for a session.
    """
    scen_str = MockActivityModel_normalize(payload.scenario)
    if not scen_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scenario '{payload.scenario}'."
        )

    # Ensure experiment exists
    exp = experiment_service.seed_default_experiment_if_empty(db)
    session_id = payload.session_id
    if not session_id:
        session = experiment_service.start_session(db, exp.id, session_code=f"DEMO-{scen_str}")
        session_id = session.id
    else:
        # Validate session exists
        session = experiment_service.get_experiment(db, session_id)  # or check session
        from app.db.repository import SessionRepository
        sess_obj = SessionRepository.get_by_id(db, session_id)
        if not sess_obj:
            session = experiment_service.start_session(db, exp.id, session_code=f"DEMO-{scen_str}")
            session_id = session.id

    res = demo_service.start_demo(session_id=session_id, scenario=scen_str)
    return res


@router.post("/step")
def execute_demo_step(payload: DemoStepRequest, db: Session = Depends(get_db)):
    """
    Execute exactly one mock observation from the active scenario,
    pass it through the Sequence Validator, and return the observation and validation result.
    """
    session_id = payload.session_id
    from app.db.repository import SessionRepository
    session = SessionRepository.get_by_id(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found."
        )

    res = demo_service.execute_demo_step(db=db, session_id=session.id)
    return res


@router.get("/status/{session_id}", response_model=DemoStatusResponse)
def get_demo_status(session_id: str):
    """Retrieve the current state of mock demo execution for a session."""
    return demo_service.get_demo_status(session_id)


@router.post("/stop")
def stop_demo(payload: Optional[DemoStopRequest] = None):
    """Stop active demo simulation for session without deleting historical data."""
    session_id = payload.session_id if payload else None
    return demo_service.stop_demo(session_id=session_id)


def MockActivityModel_normalize(scenario: str) -> Optional[str]:
    from app.ml.mock_activity_model import MockActivityModel
    return MockActivityModel._normalize_scenario(scenario)
