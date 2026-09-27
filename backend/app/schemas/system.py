"""
Pydantic Schemas for System Status, Video, Settings, and Models
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


def utc_now():
    return datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str
    app_version: str
    environment: str
    offline_mode: bool = True
    database_connected: bool = True
    database_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class SystemStatusResponse(BaseModel):
    app_name: str
    app_version: str
    offline_mode: bool = True
    ai_mode: str
    database_connected: bool = True
    database_path: Optional[str] = None
    active_sessions: int
    video_worker_running: bool
    video_source: str
    recording_active: bool
    ip_streaming_active: bool
    destination_ip: Optional[str] = None
    voice_engine_active: bool
    confidence_threshold: float
    timestamp: datetime = Field(default_factory=utc_now)


class VideoStartRequest(BaseModel):
    video_source: Optional[str] = Field(None, description="0, file path, or RTSP URL")
    record: Optional[bool] = Field(True, description="Enable local recording to MP4")
    session_id: Optional[str] = Field(None, description="Link video capture to session")


class VideoStatusResponse(BaseModel):
    is_running: bool
    source: str
    is_recording: bool
    current_recording_path: Optional[str] = None
    frames_processed: int
    fps: float
    resolution: str
    streaming_enabled: bool


class ModelStatusItem(BaseModel):
    name: str
    type: str  # OBJECT_DETECTION, POSE_ESTIMATION, ACTIVITY_RECOGNITION
    status: str  # LOADED, MOCK, UNAVAILABLE
    backend: str
    device: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ModelsStatusResponse(BaseModel):
    ai_mode: str
    models: List[ModelStatusItem]


class SettingsUpdateRequest(BaseModel):
    ai_mode: Optional[str] = None
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    object_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    video_source: Optional[str] = None
    video_recording_enabled: Optional[bool] = None
    stream_enabled: Optional[bool] = None
    stream_destination_ip: Optional[str] = None
    stream_port: Optional[int] = None
    voice_enabled: Optional[bool] = None
    voice_engine: Optional[str] = None
    log_level: Optional[str] = None


class DemoStartRequest(BaseModel):
    scenario: str = Field("NORMAL", description="NORMAL, SKIPPED_STEP, OUT_OF_SEQUENCE, LOW_CONFIDENCE, UNKNOWN_ACTION, MISSING_OBJECT")
    session_id: Optional[Any] = Field(None, description="Target session ID or auto-create one")
    speed_multiplier: float = Field(1.0, ge=0.1, le=5.0, description="Speed of demonstration steps")


class DemoStepRequest(BaseModel):
    session_id: Any = Field(..., description="Target session ID to advance by one mock observation")


class DemoStopRequest(BaseModel):
    session_id: Optional[Any] = Field(None, description="Target session ID to stop demo for")


class DemoStatusResponse(BaseModel):
    active: bool = False
    scenario: Optional[str] = None
    session_id: Optional[Any] = None
    observations_generated: int = 0
    last_observation: Optional[Dict[str, Any]] = None
    last_validation_result: Optional[str] = None
    current_step: Optional[int] = None
    completed: bool = False
