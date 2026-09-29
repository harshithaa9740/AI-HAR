"""
Pydantic Schemas for Experiments, Steps, and Protocol Definitions
"""
import json
from typing import List, Optional, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ExperimentStepBase(BaseModel):
    step_number: int = Field(..., ge=1, description="Sequential index of the experiment step (1-based)")
    step_code: Optional[str] = Field(None, description="Step identifier code e.g. STEP_01")
    name: Optional[str] = Field(None, description="Human-readable name of the step")
    description: Optional[str] = Field(None, description="Detailed instructions for the astronaut")
    expected_action: Optional[str] = Field(None, description="Unique action identifier e.g. PICK_TOOL")
    required_objects: Optional[Union[List[str], str]] = Field(default_factory=list, description="List of expected object labels")
    confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0, description="Minimum detection confidence threshold (0.0 to 1.0)")
    validation_rules: Optional[Union[dict, str]] = Field(None, description="Optional custom validation constraints")
    expected_duration_seconds: Optional[int] = Field(None, ge=1, description="Nominal step duration in seconds")

    # Backwards compatibility input aliases
    action_code: Optional[str] = Field(None, description="Legacy alias for expected_action")
    display_name: Optional[str] = Field(None, description="Legacy alias for name")
    expected_objects: Optional[Union[List[str], str]] = Field(None, description="Legacy alias for required_objects")

    def model_post_init(self, __context: Any) -> None:
        if not self.expected_action and self.action_code:
            self.expected_action = self.action_code
        if not self.name and self.display_name:
            self.name = self.display_name
        if not self.name and self.expected_action:
            self.name = self.expected_action.replace("_", " ").title()
        if not self.step_code:
            self.step_code = f"STEP_{self.step_number:02d}"
        if not self.required_objects and self.expected_objects:
            self.required_objects = self.expected_objects


class ExperimentStepCreate(ExperimentStepBase):
    pass


class ExperimentStepUpdate(BaseModel):
    step_number: Optional[int] = Field(None, ge=1)
    step_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    expected_action: Optional[str] = None
    required_objects: Optional[Union[List[str], str]] = None
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    validation_rules: Optional[Union[dict, str]] = None
    expected_duration_seconds: Optional[int] = None

    # Legacy aliases
    action_code: Optional[str] = None
    display_name: Optional[str] = None
    expected_objects: Optional[Union[List[str], str]] = None


class ExperimentStepResponse(ExperimentStepBase):
    id: int
    experiment_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("required_objects", "expected_objects", mode="before")
    @classmethod
    def parse_required_objects(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [v] if v else []
        return v or []


class ExperimentBase(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Protocol name")
    title: Optional[str] = Field(None, description="Legacy alias for name")
    description: Optional[str] = Field(None, description="Protocol description")
    version: Optional[Union[str, int, float]] = Field(default="1.0", description="Protocol version string")
    is_active: bool = Field(default=True, description="Whether this protocol is active")

    def model_post_init(self, __context: Any) -> None:
        if not self.name and self.title:
            self.name = self.title
        if not self.name:
            self.name = "Untitled Experiment"
        if isinstance(self.version, (int, float)):
            self.version = str(self.version)


class ExperimentCreate(ExperimentBase):
    steps: List[ExperimentStepCreate] = Field(default_factory=list, description="Ordered sequential steps")


class ExperimentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None
    steps: Optional[List[ExperimentStepCreate]] = None


class ExperimentResponse(ExperimentBase):
    id: int
    status: str = "ACTIVE"
    created_at: datetime
    updated_at: datetime
    steps: List[ExperimentStepResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProtocolStepItem(BaseModel):
    step_number: int
    step_code: str
    name: str
    expected_action: str
    required_objects: List[str] = Field(default_factory=list)
    confidence_threshold: float = 0.70
    validation_rules: Optional[Union[dict, str]] = None
    expected_duration_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("required_objects", mode="before")
    @classmethod
    def parse_objects(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [v] if v else []
        return v or []


class ProtocolResponse(BaseModel):
    experiment_id: int
    name: str
    version: str
    is_active: bool
    step_count: int
    steps: List[ProtocolStepItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProtocolValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
