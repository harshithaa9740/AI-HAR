"""
Processing Metrics and Result Models for AURAVISION Real-Time Processor
Provides thread-safe in-memory metrics tracking for continuous frame processing.
"""
import time
import threading
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ProcessingResult:
    """Standardized runtime result emitted on each processed frame cycle."""
    session_id: str
    action_code: str
    confidence: float
    validation_status: str
    frame_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    observed_objects: List[str] = field(default_factory=list)
    expected_step: Optional[int] = None
    current_step: Optional[int] = None
    inference_time_ms: float = 0.0
    processing_time_ms: float = 0.0
    model_name: Optional[str] = None
    model_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp.isoformat(),
            "action_code": self.action_code,
            "confidence": round(self.confidence, 4),
            "observed_objects": self.observed_objects,
            "validation_status": self.validation_status,
            "expected_step": self.expected_step,
            "current_step": self.current_step,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "model_name": self.model_name,
            "model_version": self.model_version,
        }


class ProcessingMetrics:
    """
    Thread-safe, in-memory metrics collector for real-time video inference loop.
    Does NOT write every frame to SQLite to guarantee minimal latency.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._frames_received: int = 0
        self._frames_processed: int = 0
        self._frames_dropped: int = 0
        self._successful_inferences: int = 0
        self._failed_inferences: int = 0
        self._validation_results: Dict[str, int] = {
            "VALID": 0,
            "STEP_SKIPPED": 0,
            "OUT_OF_SEQUENCE": 0,
            "UNKNOWN_ACTION": 0,
            "VERIFY_REQUIRED": 0,
            "EXPERIMENT_COMPLETE": 0,
        }
        self._total_inference_time_ms: float = 0.0
        self._total_processing_time_ms: float = 0.0
        self._last_frame_timestamp: Optional[str] = None
        self._last_successful_processing_timestamp: Optional[str] = None

    def start(self) -> None:
        """Mark start time of processing loop."""
        with self._lock:
            if self._start_time is None:
                self._start_time = time.time()

    def record_frame_received(self, timestamp: Optional[str] = None) -> None:
        """Record receipt of a new frame from camera manager."""
        with self._lock:
            self._frames_received += 1
            if timestamp:
                self._last_frame_timestamp = timestamp
            else:
                self._last_frame_timestamp = datetime.now(timezone.utc).isoformat()

    def record_frame_dropped(self, count: int = 1) -> None:
        """Record dropped stale frame(s) when processor skips backlog."""
        with self._lock:
            self._frames_dropped += max(0, count)

    def record_success(self, result: ProcessingResult) -> None:
        """Record successful inference and sequence validation cycle."""
        with self._lock:
            self._frames_processed += 1
            self._successful_inferences += 1
            self._total_inference_time_ms += result.inference_time_ms
            self._total_processing_time_ms += result.processing_time_ms
            self._last_successful_processing_timestamp = datetime.now(timezone.utc).isoformat()

            val_status = (result.validation_status or "UNKNOWN").upper()
            self._validation_results[val_status] = self._validation_results.get(val_status, 0) + 1

    def record_failure(self, inference_time_ms: float = 0.0, processing_time_ms: float = 0.0) -> None:
        """Record an inference or validation failure on a frame cycle."""
        with self._lock:
            self._frames_processed += 1
            self._failed_inferences += 1
            self._total_inference_time_ms += max(0.0, inference_time_ms)
            self._total_processing_time_ms += max(0.0, processing_time_ms)

    def reset(self) -> None:
        """Reset all metrics counters."""
        with self._lock:
            self._start_time = None
            self._frames_received = 0
            self._frames_processed = 0
            self._frames_dropped = 0
            self._successful_inferences = 0
            self._failed_inferences = 0
            self._validation_results = {
                "VALID": 0,
                "STEP_SKIPPED": 0,
                "OUT_OF_SEQUENCE": 0,
                "UNKNOWN_ACTION": 0,
                "VERIFY_REQUIRED": 0,
                "EXPERIMENT_COMPLETE": 0,
            }
            self._total_inference_time_ms = 0.0
            self._total_processing_time_ms = 0.0
            self._last_frame_timestamp = None
            self._last_successful_processing_timestamp = None

    def get_summary(self) -> Dict[str, Any]:
        """Return computed runtime metrics summary dictionary."""
        with self._lock:
            now = time.time()
            uptime = (now - self._start_time) if self._start_time else 0.0

            avg_inf = (
                round(self._total_inference_time_ms / self._frames_processed, 2)
                if self._frames_processed > 0
                else 0.0
            )
            avg_proc = (
                round(self._total_processing_time_ms / self._frames_processed, 2)
                if self._frames_processed > 0
                else 0.0
            )
            processing_fps = (
                round(self._frames_processed / uptime, 2)
                if uptime > 0 and self._frames_processed > 0
                else 0.0
            )

            return {
                "frames_received": self._frames_received,
                "frames_processed": self._frames_processed,
                "frames_dropped": self._frames_dropped,
                "successful_inferences": self._successful_inferences,
                "failed_inferences": self._failed_inferences,
                "validation_results": dict(self._validation_results),
                "average_inference_time_ms": avg_inf,
                "average_processing_time_ms": avg_proc,
                "processing_fps": processing_fps,
                "uptime_seconds": round(uptime, 2),
                "last_frame_timestamp": self._last_frame_timestamp,
                "last_successful_processing_timestamp": self._last_successful_processing_timestamp,
            }
