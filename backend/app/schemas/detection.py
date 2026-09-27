"""
Pydantic Schemas for AI Detections, Pose, Activities, and Inference Endpoints
"""
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


def utc_now():
    return datetime.now(timezone.utc)


class BoundingBox(BaseModel):
    label: str = Field(..., description="Detected object label e.g. container, tool")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Tuple[int, int, int, int] = Field(..., description="[x1, y1, x2, y2] bounding coordinates")


class DetectionResult(BaseModel):
    """Standardized object detection entity item."""
    class_name: str = Field(..., description="Object class name e.g. tool, container, sample")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bounding_box: Optional[Dict[str, int]] = Field(default=None, description="Bounding box e.g. {x1, y1, x2, y2}")
    tracking_id: Optional[int] = Field(default=None, description="Optional tracker ID")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Keypoint(BaseModel):
    name: str
    x: float
    y: float
    z: Optional[float] = 0.0
    visibility: float = Field(default=1.0, ge=0.0, le=1.0)


class PoseResult(BaseModel):
    person_id: int = 0
    keypoints: List[Keypoint] = Field(default_factory=list)
    hands_detected: bool = False
    hand_positions: Dict[str, Tuple[float, float]] = Field(default_factory=dict)


class ActivityDetection(BaseModel):
    action: str = Field(..., description="Detected action code e.g. TAKE_SAMPLE")
    confidence: float = Field(..., ge=0.0, le=1.0)
    objects: List[str] = Field(default_factory=list, description="Observed interacting objects")
    timestamp: datetime = Field(default_factory=utc_now)
    person_id: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObservedAction(BaseModel):
    """
    Standardized observation emitted by the AI layer and passed into the Sequence Validator.
    Never decides protocol progression on its own.
    """
    action_code: str = Field(..., description="Observed action code to validate")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detection confidence score")
    observed_objects: List[str] = Field(default_factory=list, description="Observed/interacting objects")
    timestamp: Optional[datetime] = Field(default_factory=utc_now, description="Detection timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class ValidateActionRequest(BaseModel):
    session_id: Optional[Union[int, str]] = None
    experiment_id: Optional[Union[int, str]] = None
    action_code: str = Field(..., description="Observed action code to validate")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detection confidence score")
    observed_objects: List[str] = Field(default_factory=list, description="List of detected objects")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class InferenceFrameRequest(BaseModel):
    """Request payload for standalone or manual frame inference."""
    frame_id: Optional[str] = Field(default=None, description="Optional frame identifier")
    scenario: Optional[str] = Field(default=None, description="Optional mock scenario override (e.g. NORMAL, SKIPPED_STEP)")
    step_index: Optional[int] = Field(default=None, description="Optional protocol step index for deterministic mock inference")


class InferenceFrameResponse(BaseModel):
    """Standardized response from AI inference on a frame."""
    frame_id: str
    action_code: str
    confidence: float
    observed_objects: List[str] = Field(default_factory=list)
    detections: List[DetectionResult] = Field(default_factory=list)
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionInferenceResponse(BaseModel):
    """Response from session-scoped inference with optional sequence validation outcome."""
    session_id: str
    frame_id: Optional[str] = None
    observation: ObservedAction
    validation: Optional[Dict[str, Any]] = None
