"""
Pydantic Schemas for Real-Time and Persisted Events
"""
import json
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DetectionEventResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    protocol_step_id: Optional[int] = None
    timestamp: datetime
    frame_number: Optional[int] = None
    start_time_ms: Optional[float] = None
    end_time_ms: Optional[float] = None
    entity_type: str
    entity_name: str
    confidence: Optional[float] = None
    bbox: Optional[str] = None
    source: Optional[str] = None
    metadata_json: Optional[Union[Dict[str, Any], str]] = "{}"

    model_config = ConfigDict(from_attributes=True)


class SequenceEventResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    protocol_step_id: Optional[int] = None
    event_type: Optional[str] = None
    timestamp: datetime
    expected_step_number: Optional[int] = None
    expected_step_code: Optional[str] = None
    observed_step_number: Optional[int] = None
    observed_step_code: Optional[str] = None
    result: str
    confidence: Optional[float] = None
    message: Optional[str] = None
    metadata_json: Optional[Union[Dict[str, Any], str]] = "{}"

    model_config = ConfigDict(from_attributes=True)


class AlertEventResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    validation_event_id: Optional[int] = None
    timestamp: datetime
    alert_type: str
    severity: str = "INFO"
    category: str = "protocol"
    message: str
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    spoken: bool = False
    metadata_json: Optional[Union[Dict[str, Any], str]] = "{}"

    model_config = ConfigDict(from_attributes=True)


class SystemEventResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    timestamp: datetime
    event_type: str
    severity: str = "INFO"
    message: str
    component: Optional[str] = None
    metadata_json: Optional[Union[Dict[str, Any], str]] = "{}"

    model_config = ConfigDict(from_attributes=True)


class SequenceValidationResponse(BaseModel):
    result: str = Field(..., description="VALID, STEP_SKIPPED, OUT_OF_SEQUENCE, UNKNOWN_ACTION, VERIFY_REQUIRED, EXPERIMENT_COMPLETE")
    expected_step_number: Optional[int] = None
    expected_step_code: Optional[str] = None
    expected_action: Optional[str] = None
    observed_action: Optional[str] = None
    confidence: Optional[float] = None
    message: str = ""
    next_step_number: Optional[int] = None
    next_step_code: Optional[str] = None
    completed: bool = False

    # Legacy/compatibility fields
    session_id: Optional[int] = None
    cloud_synced: Optional[bool] = True
    current_step: Optional[int] = None
    completed_step: Optional[int] = None
    expected_step: Optional[int] = None
    observed_step: Optional[int] = None
    next_step: Optional[int] = None
    next_step_name: Optional[str] = None
    next_step_description: Optional[str] = None
    reason: Optional[str] = None
    experiment_complete: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context) -> None:
        if self.expected_step is None and self.expected_step_number is not None:
            self.expected_step = self.expected_step_number
        if self.expected_step_number is None and self.expected_step is not None:
            self.expected_step_number = self.expected_step

        if self.next_step is None and self.next_step_number is not None:
            self.next_step = self.next_step_number
        if self.next_step_number is None and self.next_step is not None:
            self.next_step_number = self.next_step

        if self.experiment_complete is None:
            self.experiment_complete = self.completed
        if self.completed is False and self.experiment_complete is True:
            self.completed = True

        if self.current_step is None and self.expected_step_number is not None:
            self.current_step = self.expected_step_number

        if self.reason is None and self.message:
            self.reason = self.message


class AlertResponse(BaseModel):
    id: Optional[Union[int, str]] = None
    session_id: Optional[Union[int, str]] = None
    validation_event_id: Optional[int] = None
    alert_type: str
    severity: str
    category: str = "protocol"
    message: str
    spoken: bool = False
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=utc_now)


class TimelineEvent(BaseModel):
    timestamp: datetime
    type: str = Field(..., description="SYSTEM, SEQUENCE, ALERT, or DETECTION")
    event_type: str
    severity: str = "INFO"
    message: str = ""
    component: Optional[str] = None
    category: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context) -> None:
        if not self.category:
            self.category = self.type.lower()
        if not self.details and self.data:
            self.details = self.data
        elif not self.data and self.details:
            self.data = self.details


class SessionTimelineResponse(BaseModel):
    session_id: int
    session_uuid: Optional[str] = None
    total_events: int = 0
    events: List[TimelineEvent] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context) -> None:
        if self.total_events == 0 and self.events:
            self.total_events = len(self.events)



class WebSocketEvent(BaseModel):
    type: str = Field(..., description="Type of event e.g. STEP_VALIDATED, ALERT, etc.")
    session_id: Optional[Union[int, str]] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)

