"""
Pydantic Schemas for Camera Ingestion Subsystem
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CameraStartRequest(BaseModel):
    """Configuration payload to start or initialize camera capture."""
    source_type: Optional[str] = Field(default="mock", description="Source type: 'mock', 'file', or 'webcam'")
    camera_index: Optional[int] = Field(default=0, description="Webcam hardware index (0, 1, ...)")
    file_path: Optional[str] = Field(default=None, description="Local filesystem path for video file source")
    target_fps: Optional[int] = Field(default=10, ge=1, le=60, description="Target ingestion FPS")
    frame_width: Optional[int] = Field(default=640, ge=64, le=3840, description="Target frame width")
    frame_height: Optional[int] = Field(default=480, ge=64, le=2160, description="Target frame height")
    buffer_size: Optional[int] = Field(default=5, ge=1, le=100, description="In-memory ring buffer capacity")
    loop: Optional[bool] = Field(default=False, description="Whether video file playback should loop upon EOF")


class CameraStatusResponse(BaseModel):
    """Status metadata for the active or stopped camera pipeline."""
    state: str = Field(description="Camera lifecycle state: STOPPED, STARTING, RUNNING, PAUSED, ERROR")
    session_id: Optional[str] = Field(default=None, description="Session ID if camera is session-scoped")
    target_fps: int
    buffer_size: int
    buffered_frames: int
    total_frames_ingested: int
    uptime_seconds: float
    last_error: Optional[str] = None
    source: Optional[Dict[str, Any]] = None


class FrameMetadataResponse(BaseModel):
    """Metadata of a captured and preprocessed transient frame (excludes binary payload)."""
    frame_id: str
    timestamp: str
    frame_index: int
    width: int
    height: int
    source_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
