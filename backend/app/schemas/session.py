"""
Pydantic Schemas for Experiment Sessions
"""
from typing import Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SessionCreate(BaseModel):
    experiment_id: Union[int, str] = Field(..., description="ID of the experiment to run")
    session_uuid: Optional[str] = Field(None, description="Optional custom session UUID or code")
    session_code: Optional[str] = Field(None, description="Legacy alias for session_uuid")
    session_name: Optional[str] = Field(None, description="Optional human-readable session name")
    operator_label: Optional[str] = Field("Astronaut Specialist", description="Operator / astronaut identifier")
    notes: Optional[str] = Field(None, description="Optional session notes")
    stream_enabled: bool = False


class SessionStartRequest(BaseModel):
    experiment_id: Union[int, str] = Field(..., description="ID of the experiment to run")
    session_code: Optional[str] = Field(None, description="Optional custom session identifier")
    session_uuid: Optional[str] = Field(None, description="Optional custom session UUID")


class SessionStopRequest(BaseModel):
    reason: Optional[str] = Field("User requested stop", description="Reason for stopping session")


class SessionResponse(BaseModel):
    id: int
    experiment_id: int
    session_uuid: str
    session_name: Optional[str] = None
    status: str = "CREATED"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    current_step_number: Optional[int] = 1
    current_step_code: Optional[str] = None
    expected_next_step: Optional[str] = None
    operator_label: Optional[str] = "Astronaut Specialist"
    notes: Optional[str] = None
    recording_path: Optional[str] = None
    stream_enabled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Sequence state & completion
    completed: bool = False
    is_completed: bool = False

    # Legacy compatibility fields
    session_code: Optional[str] = None
    current_step: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)

    def model_post_init(self, __context) -> None:
        if not self.session_code and self.session_uuid:
            self.session_code = self.session_uuid
        if not self.current_step and self.current_step_number:
            self.current_step = self.current_step_number
        if self.status == "COMPLETED":
            self.completed = True
            self.is_completed = True


class SessionLogResponse(BaseModel):
    session_id: Union[int, str]
    session_code: str
    log_format: str  # text or jsonl
    content: str
    download_url: Optional[str] = None
