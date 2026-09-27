"""
Pydantic Schemas for Real-Time Processing Loop and Metrics Endpoints
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ProcessingStartRequest(BaseModel):
    """Optional configuration for starting real-time processor."""
    target_fps: Optional[int] = Field(default=None, ge=1, le=60, description="Processing loop target FPS")


class ProcessingStatusResponse(BaseModel):
    """Standardized response for processor status endpoint."""
    session_id: str
    state: str
    worker_active: bool
    camera_active: bool
    ai_ready: bool
    target_fps: int = 10
    frames_processed: int = 0
    last_frame_timestamp: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None


class ProcessingMetricsResponse(BaseModel):
    """Standardized response for processor runtime metrics endpoint."""
    session_id: str
    state: str
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    successful_inferences: int = 0
    failed_inferences: int = 0
    validation_results: Dict[str, int] = Field(default_factory=dict)
    average_inference_time_ms: float = 0.0
    average_processing_time_ms: float = 0.0
    processing_fps: float = 0.0
    uptime_seconds: float = 0.0
    last_frame_timestamp: Optional[str] = None
    last_successful_processing_timestamp: Optional[str] = None
