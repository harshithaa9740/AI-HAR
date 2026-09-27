"""
Experiment Protocol and Step Configuration API Endpoints
All business rules and validation logic are encapsulated within ExperimentService.
"""
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    ExperimentStepCreate,
    ExperimentStepUpdate,
    ExperimentStepResponse,
    ProtocolResponse,
    ProtocolValidationResult
)
from app.services.experiment_service import (
    experiment_service,
    ProtocolValidationError
)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


@router.get("", response_model=List[ExperimentResponse])
def list_experiments(is_active_only: bool = False, db: Session = Depends(get_db)):
    """Retrieve all available experiment protocols."""
    return experiment_service.list_experiments(db, is_active_only=is_active_only)


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    """
    Create a new experiment protocol with its ordered steps.
    Validates complete protocol deterministically before persisting.
    """
    try:
        return experiment_service.create_experiment(db, payload)
    except ProtocolValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": e.errors, "message": str(e)}
        )


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: Union[int, str], db: Session = Depends(get_db)):
    """Get experiment details and ordered step sequence by ID."""
    exp = experiment_service.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found."
        )
    return exp


@router.put("/{experiment_id}", response_model=ExperimentResponse)
def update_experiment(
    experiment_id: Union[int, str],
    payload: ExperimentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update experiment metadata or replace step definitions.
    Preserves existing steps when only updating metadata.
    """
    try:
        exp = experiment_service.update_experiment(db, experiment_id, payload)
        if not exp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found."
            )
        return exp
    except ProtocolValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": e.errors, "message": str(e)}
        )


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: Union[int, str], db: Session = Depends(get_db)):
    """Delete an experiment protocol and all associated cascade records."""
    success = experiment_service.delete_experiment(db, experiment_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found."
        )
    return None


@router.get("/{experiment_id}/steps", response_model=List[ExperimentStepResponse])
def get_experiment_steps(experiment_id: Union[int, str], db: Session = Depends(get_db)):
    """Retrieve ordered steps for a specific experiment (sorted step_number ASC)."""
    exp = experiment_service.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found."
        )
    return experiment_service.get_experiment_steps(db, experiment_id)


@router.post("/{experiment_id}/steps", response_model=ExperimentStepResponse, status_code=status.HTTP_201_CREATED)
def add_experiment_step(
    experiment_id: Union[int, str],
    step: ExperimentStepCreate,
    db: Session = Depends(get_db)
):
    """Append or insert a new step into an experiment protocol with protocol validation."""
    try:
        return experiment_service.add_step(db, experiment_id, step)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": getattr(e, "errors", [str(e)]), "message": str(e)}
        )


@router.put("/{experiment_id}/steps/{step_id}", response_model=ExperimentStepResponse)
def update_experiment_step(
    experiment_id: Union[int, str],
    step_id: Union[int, str],
    step: ExperimentStepUpdate,
    db: Session = Depends(get_db)
):
    """Update an individual experiment step and validate resulting protocol integrity."""
    try:
        updated = experiment_service.update_step(db, experiment_id, step_id, step)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found in experiment {experiment_id}."
            )
        return updated
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": getattr(e, "errors", [str(e)]), "message": str(e)}
        )


@router.delete("/{experiment_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment_step(
    experiment_id: Union[int, str],
    step_id: Union[int, str],
    db: Session = Depends(get_db)
):
    """Delete an experiment step and verify remaining protocol validity."""
    try:
        success = experiment_service.remove_step(db, experiment_id, step_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Step {step_id} not found in experiment {experiment_id}."
            )
        return None
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": getattr(e, "errors", [str(e)]), "message": str(e)}
        )


@router.get("/{experiment_id}/protocol", response_model=ProtocolResponse)
def get_experiment_protocol(experiment_id: Union[int, str], db: Session = Depends(get_db)):
    """Retrieve structured protocol specification for UI and sequence validation."""
    proto = experiment_service.get_protocol(db, experiment_id)
    if not proto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found."
        )
    return proto


@router.post("/validate-protocol", response_model=ProtocolValidationResult)
def validate_protocol_definition(payload: ExperimentCreate):
    """Lightweight deterministic validation endpoint for draft protocols without saving."""
    return experiment_service.validate_protocol(payload.steps, name=payload.name)
