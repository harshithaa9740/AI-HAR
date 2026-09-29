"""
Real-Time AI Processing Loop and Experiment Validation Orchestration Service for AURAVISION
Coordinates Frame Ingestion, AI Inference Engine, Deterministic Sequence Validator,
and Session/Event Management in a continuous, offline-first execution loop.
"""
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ProcessingState,
    SessionStatus,
    EventType,
    AlertSeverity,
    ValidationResult,
)
from app.core.logging import logger
from app.db.database import SessionLocal
from app.db.repository import get_session, get_steps_for_experiment
from app.camera.frame_model import Frame
from app.camera.exceptions import CameraStoppedError, CameraError, CameraSourceError
from app.camera.camera_manager import CameraManagerRegistry
from app.services.camera_service import camera_service
from app.ml.inference_engine import inference_engine, InferenceEngine
from app.ml.exceptions import AIInferenceError, ProviderUnavailableError
from app.services.sequence_validator import sequence_validator, SequenceValidator
from app.services.event_service import event_service
from app.services.processing_state import (
    ProcessingStateManager,
    InvalidProcessingStateTransitionError,
)
from app.services.processing_metrics import ProcessingMetrics, ProcessingResult


class RealTimeProcessorError(Exception):
    """Base exception for RealTimeProcessor operations."""
    pass


class RealTimeProcessor:
    """
    Continuous frame-by-frame AI inference and deterministic protocol validation loop
    for an active Experiment Session.
    
    Architecture:
    Camera Manager (Frame)
            ↓
    AI Inference Engine (ObservedAction + Detections)
            ↓
    Sequence Validator (Deterministic Protocol Evaluation)
            ↓
    Session / Event Management (DB updates, Events, Metrics)
            ↓
    ProcessingResult (In-memory runtime result & metrics)
    """

    def __init__(
        self,
        session_id: str,
        target_fps: Optional[int] = None,
        engine: Optional[InferenceEngine] = None,
        validator: Optional[SequenceValidator] = None
    ):
        self.session_id = str(session_id)
        self.target_fps = max(1, target_fps or settings.TARGET_FPS)
        self.inference_engine = engine or inference_engine
        self.sequence_validator = validator or sequence_validator

        self.metrics = ProcessingMetrics()
        self._state: ProcessingState = ProcessingState.STOPPED
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        self._last_result: Optional[ProcessingResult] = None
        self._last_error: Optional[str] = None
        self._last_processed_frame_id: Optional[str] = None
        self._last_processed_frame_index: Optional[int] = None
        self._last_recorded_action: Optional[str] = None
        self._last_recorded_action_time: float = 0.0

    @property
    def state(self) -> ProcessingState:
        with self._lock:
            return self._state

    def is_running(self) -> bool:
        with self._lock:
            return self._state == ProcessingState.RUNNING

    def is_paused(self) -> bool:
        with self._lock:
            return self._state == ProcessingState.PAUSED

    def is_active(self) -> bool:
        with self._lock:
            return self._state in (ProcessingState.RUNNING, ProcessingState.PAUSED, ProcessingState.STARTING)

    def start(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Start the continuous processing worker for this session.
        Validates session status, camera availability, and AI provider readiness.
        """
        with self._lock:
            if self._state in (ProcessingState.RUNNING, ProcessingState.STARTING):
                raise RealTimeProcessorError(f"RealTimeProcessor for session '{self.session_id}' is already running.")
            ProcessingStateManager.validate_transition(self._state, ProcessingState.STARTING)
            self._state = ProcessingState.STARTING
            self._last_error = None

        # 1. Validate Session in DB
        own_db = False
        if db is None:
            db = SessionLocal()
            own_db = True

        try:
            sess = get_session(db, self.session_id)
            if not sess:
                with self._lock:
                    self._state = ProcessingState.STOPPED
                raise ValueError(f"Session '{self.session_id}' not found.")

            if sess.status != SessionStatus.RUNNING.value:
                with self._lock:
                    self._state = ProcessingState.STOPPED
                raise ValueError(
                    f"Cannot start processing on session in '{sess.status}' status. Session must be in RUNNING status."
                )

            # 2. Verify AI Provider is initialized and ready
            provider = self.inference_engine.get_provider()
            if provider is None or not provider.is_ready():
                with self._lock:
                    self._state = ProcessingState.STOPPED
                raise ProviderUnavailableError("AI Provider is not initialized or ready.")

            # 3. Verify camera is available
            cam_mgr = CameraManagerRegistry.get_for_session(self.session_id)
            if cam_mgr is None or not cam_mgr.is_running():
                # Check global camera fallback
                global_cam = CameraManagerRegistry.get_global_manager()
                if not global_cam.is_running():
                    with self._lock:
                        self._state = ProcessingState.STOPPED
                    raise CameraStoppedError(
                        f"No active camera running for session '{self.session_id}'. Start camera first."
                    )

            # 4. Initialize Sequence Validator state for session
            steps = get_steps_for_experiment(db, sess.experiment_id)
            self.sequence_validator.init_session_state(
                session_id=sess.id,
                experiment_id=sess.experiment_id,
                steps=steps,
                current_step_number=sess.current_step_number or 1,
                completed=(sess.status == SessionStatus.COMPLETED.value)
            )

            # 5. Launch worker thread
            with self._lock:
                self._stop_event.clear()
                self._pause_event.clear()
                self.metrics.start()
                self._state = ProcessingState.RUNNING

                self._thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"RealTimeProcessorWorker-{self.session_id}",
                    daemon=True
                )
                self._thread.start()

            # Record system event
            self._log_event(
                event_type=EventType.PROCESSING_STARTED.value,
                message=f"Real-time processing worker started for session '{self.session_id}' at {self.target_fps} FPS.",
                db=db
            )
            logger.info(f"RealTimeProcessor started for session {self.session_id} at {self.target_fps} FPS.")
            return self.status()

        finally:
            if own_db:
                db.close()

    def pause(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """Pause real-time frame processing while preserving session and validator state."""
        with self._lock:
            if self._state != ProcessingState.RUNNING:
                if self._state == ProcessingState.PAUSED:
                    return self.status()
                raise RealTimeProcessorError(f"Cannot pause processor in '{self._state.value}' state.")

            ProcessingStateManager.validate_transition(self._state, ProcessingState.PAUSED)
            self._pause_event.set()
            self._state = ProcessingState.PAUSED

        self._log_event(
            event_type=EventType.SYSTEM_STATUS.value,
            message=f"Real-time processing paused for session '{self.session_id}'.",
            db=db
        )
        logger.info(f"RealTimeProcessor paused for session {self.session_id}.")
        return self.status()

    def resume(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """Resume real-time frame processing from PAUSED state."""
        with self._lock:
            if self._state != ProcessingState.PAUSED:
                if self._state == ProcessingState.RUNNING:
                    return self.status()
                raise RealTimeProcessorError(f"Cannot resume processor in '{self._state.value}' state.")

            ProcessingStateManager.validate_transition(self._state, ProcessingState.RUNNING)
            self._pause_event.clear()
            self._state = ProcessingState.RUNNING

        self._log_event(
            event_type=EventType.SYSTEM_STATUS.value,
            message=f"Real-time processing resumed for session '{self.session_id}'.",
            db=db
        )
        logger.info(f"RealTimeProcessor resumed for session {self.session_id}.")
        return self.status()

    def stop(self, db: Optional[Session] = None, reason: str = "Processing stopped by user") -> Dict[str, Any]:
        """Stop frame processing and wait for worker thread shutdown."""
        with self._lock:
            if self._state in (ProcessingState.STOPPED, ProcessingState.ERROR):
                return self.status()
            self._state = ProcessingState.STOPPING

        self._stop_event.set()
        self._pause_event.clear()

        if self._thread is not None and self._thread.is_alive():
            if threading.current_thread() != self._thread:
                self._thread.join(timeout=2.0)
            self._thread = None

        with self._lock:
            self._state = ProcessingState.STOPPED

        self._log_event(
            event_type=EventType.PROCESSING_STOPPED.value,
            message=f"Real-time processing stopped for session '{self.session_id}': {reason}",
            db=db
        )
        logger.info(f"RealTimeProcessor stopped for session {self.session_id}.")
        return self.status()

    def _worker_loop(self) -> None:
        """Background worker thread continuously executing Frame -> AI -> Validator -> Events."""
        interval = 1.0 / self.target_fps

        while not self._stop_event.is_set():
            cycle_start = time.perf_counter()

            # Handle pause state
            if self._pause_event.is_set():
                time.sleep(0.05)
                continue

            # 1. Acquire latest Frame from session or global camera
            frame: Optional[Frame] = None
            try:
                frame = camera_service.read_session_frame(self.session_id)
            except CameraStoppedError:
                # Try fallback to global camera
                try:
                    frame = camera_service.read_global_frame()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Fatal camera error in processing worker for session {self.session_id}: {e}")
                with self._lock:
                    self._state = ProcessingState.ERROR
                    self._last_error = str(e)
                self._log_event(
                    event_type=EventType.PROCESSING_ERROR.value,
                    message=f"Camera failure in processing worker: {str(e)}",
                    severity=AlertSeverity.CRITICAL.value
                )
                break

            if frame is None:
                # No frame available yet
                time.sleep(0.01)
                continue

            # Avoid re-processing identical unchanged frame instance
            if self._last_processed_frame_id == frame.frame_id:
                time.sleep(0.01)
                continue

            # Check for frame dropping / skipped indices
            if self._last_processed_frame_index is not None and frame.frame_index > (self._last_processed_frame_index + 1):
                dropped = frame.frame_index - self._last_processed_frame_index - 1
                self.metrics.record_frame_dropped(dropped)

            self._last_processed_frame_id = frame.frame_id
            self._last_processed_frame_index = frame.frame_index
            self.metrics.record_frame_received(frame.timestamp)

            # 2. Run AI Inference on Frame (Isolated from crashing loop on single frame failure)
            inf_start = time.perf_counter()
            try:
                obs, detections = self.inference_engine.infer(frame)
                inf_elapsed = (time.perf_counter() - inf_start) * 1000.0
            except Exception as e:
                inf_elapsed = (time.perf_counter() - inf_start) * 1000.0
                proc_elapsed = (time.perf_counter() - cycle_start) * 1000.0
                self.metrics.record_failure(inference_time_ms=inf_elapsed, processing_time_ms=proc_elapsed)
                logger.warning(f"Inference error on frame {frame.frame_id}: {e}")
                self._log_event(
                    event_type=EventType.INFERENCE_ERROR.value,
                    message=f"Inference failed on frame {frame.frame_id}: {str(e)}",
                    severity=AlertSeverity.WARNING.value
                )
                time.sleep(0.02)
                continue

            # 3. Deterministic Protocol Validation & Database Event Recording
            try:
                with SessionLocal() as db:
                    sess = get_session(db, self.session_id)
                    if not sess:
                        logger.error(f"Session {self.session_id} not found during processing loop.")
                        break

                    # Check if session was stopped or completed externally
                    if sess.status != SessionStatus.RUNNING.value:
                        if sess.status == SessionStatus.PAUSED.value:
                            self._pause_event.set()
                            with self._lock:
                                self._state = ProcessingState.PAUSED
                            continue
                        else:
                            # STOPPED, COMPLETED, or ERROR
                            logger.info(f"Session {self.session_id} transitioned to '{sess.status}'. Stopping worker.")
                            with self._lock:
                                self._state = ProcessingState.STOPPED
                            break

                    steps = get_steps_for_experiment(db, sess.experiment_id)

                    action_code = obs.action_code
                    confidence = obs.confidence or 0.0
                    is_active_action = action_code not in (None, "IDLE")

                    # Avoid spamming database on every frame:
                    # Persist detection & sequence event only for active non-idle actions
                    # when the action changes or after 1.0 second has elapsed.
                    now_ts = time.perf_counter()
                    should_persist_event = is_active_action and (
                        action_code != self._last_recorded_action
                        or (now_ts - self._last_recorded_action_time) >= 1.0
                    )

                    if should_persist_event:
                        self._last_recorded_action = action_code
                        self._last_recorded_action_time = now_ts

                        # Record Detection Event in DB
                        event_service.record_detection_event(
                            db=db,
                            session_id=sess.id,
                            entity_type="action",
                            action_code=action_code,
                            confidence=confidence,
                            metadata=obs.metadata
                        )

                        # Use experiment_service for deterministic sequence validation,
                        # sequence event persistence, and deduplicated alerts linked by validation_event_id
                        from app.services.experiment_service import experiment_service
                        val_res = experiment_service.validate_session_action(
                            db=db,
                            session_id=sess.id,
                            action_code=action_code,
                            confidence=confidence,
                            observed_objects=obs.observed_objects
                        )
                    else:
                        # Ephemeral validation without DB persistence when action is IDLE or unchanged
                        val_res = self.sequence_validator.validate_observation(
                            observation=obs,
                            session_id=sess.id,
                            steps=steps
                        )

                    # Handle EXPERIMENT_COMPLETE
                    is_complete = (
                        val_res.result == ValidationResult.EXPERIMENT_COMPLETE.value
                        or getattr(val_res, "completed", False)
                        or getattr(val_res, "experiment_complete", False)
                        or sess.status == SessionStatus.COMPLETED.value
                    )

                    proc_elapsed = (time.perf_counter() - cycle_start) * 1000.0

                    model_info = self.inference_engine.get_provider().get_model_info() if self.inference_engine.get_provider() else {}

                    result = ProcessingResult(
                        session_id=str(sess.id),
                        frame_id=frame.frame_id,
                        timestamp=datetime.now(timezone.utc),
                        action_code=obs.action_code,
                        confidence=obs.confidence or 0.0,
                        observed_objects=obs.observed_objects or [],
                        validation_status=val_res.result,
                        expected_step=val_res.expected_step_number,
                        current_step=sess.current_step_number,
                        inference_time_ms=inf_elapsed,
                        processing_time_ms=proc_elapsed,
                        model_name=model_info.get("model_name"),
                        model_version=model_info.get("model_version"),
                    )

                    self.metrics.record_success(result)
                    with self._lock:
                        self._last_result = result

                    if is_complete:
                        logger.info(f"Experiment completed for session {self.session_id} via sequence validator.")
                        with self._lock:
                            self._state = ProcessingState.STOPPED

                        if sess.status != SessionStatus.COMPLETED.value:
                            sess.status = SessionStatus.COMPLETED.value
                            sess.ended_at = datetime.now(timezone.utc)
                            db.commit()

                            event_service.record_system_event(
                                db=db,
                                event_type=EventType.SESSION_COMPLETED.value,
                                message=f"Experiment session '{sess.id}' marked COMPLETED after final step.",
                                session_id=sess.id
                            )
                            event_service.record_system_event(
                                db=db,
                                event_type=EventType.EXPERIMENT_COMPLETE.value,
                                message="Experiment protocol completed successfully.",
                                session_id=sess.id
                            )

                        # Cleanly release session camera
                        try:
                            camera_service.stop_session_camera(self.session_id, db=db)
                        except Exception as ce:
                            logger.warning(f"Camera release after experiment completion: {ce}")

                        break


            except Exception as e:
                logger.error(f"Error during validation/event recording on session {self.session_id}: {e}")
                proc_elapsed = (time.perf_counter() - cycle_start) * 1000.0
                self.metrics.record_failure(inference_time_ms=inf_elapsed, processing_time_ms=proc_elapsed)

            # Cycle interval pacing
            cycle_elapsed = time.perf_counter() - cycle_start
            sleep_needed = max(0.0, interval - cycle_elapsed)
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    def status(self) -> Dict[str, Any]:
        """Return standardized processing status response dictionary."""
        with self._lock:
            curr_state = self._state.value
            last_res = self._last_result.to_dict() if self._last_result else None
            last_err = self._last_error

        cam_mgr = CameraManagerRegistry.get_for_session(self.session_id)
        if cam_mgr is None:
            cam_mgr = CameraManagerRegistry.get_global_manager()
        cam_active = cam_mgr.is_running() if cam_mgr else False

        provider = self.inference_engine.get_provider()
        ai_ready = provider.is_ready() if provider else False

        metrics_summary = self.metrics.get_summary()

        return {
            "session_id": self.session_id,
            "state": curr_state,
            "worker_active": (curr_state == ProcessingState.RUNNING.value),
            "camera_active": cam_active,
            "ai_ready": ai_ready,
            "target_fps": self.target_fps,
            "frames_processed": metrics_summary.get("frames_processed", 0),
            "last_frame_timestamp": metrics_summary.get("last_frame_timestamp"),
            "last_result": last_res,
            "last_error": last_err,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Return runtime in-memory metrics for the session."""
        summary = self.metrics.get_summary()
        summary["session_id"] = self.session_id
        summary["state"] = self.state.value
        return summary

    def _log_event(
        self,
        event_type: str,
        message: str,
        severity: str = AlertSeverity.INFO.value,
        db: Optional[Session] = None
    ) -> None:
        """Helper to safely record system events in SQLite."""
        try:
            if db is not None:
                event_service.record_system_event(
                    db=db,
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    component="realtime_processor",
                    session_id=self.session_id
                )
            else:
                with SessionLocal() as local_db:
                    event_service.record_system_event(
                        db=local_db,
                        event_type=event_type,
                        message=message,
                        severity=severity,
                        component="realtime_processor",
                        session_id=self.session_id
                    )
        except Exception as e:
            logger.warning(f"Failed to record processor system event: {e}")


class RealTimeProcessorRegistry:
    """
    Registry for managing at most one active RealTimeProcessor per session.
    """
    _processors: Dict[str, RealTimeProcessor] = {}
    _lock = threading.Lock()

    @classmethod
    def get_for_session(cls, session_id: str) -> Optional[RealTimeProcessor]:
        with cls._lock:
            return cls._processors.get(str(session_id))

    @classmethod
    def get_or_create(
        cls,
        session_id: str,
        target_fps: Optional[int] = None
    ) -> RealTimeProcessor:
        with cls._lock:
            key = str(session_id)
            if key not in cls._processors:
                cls._processors[key] = RealTimeProcessor(
                    session_id=key,
                    target_fps=target_fps
                )
            return cls._processors[key]

    @classmethod
    def remove_for_session(cls, session_id: str) -> None:
        with cls._lock:
            key = str(session_id)
            if key in cls._processors:
                proc = cls._processors[key]
                if proc.is_active():
                    proc.stop()
                del cls._processors[key]

    @classmethod
    def stop_all(cls) -> None:
        with cls._lock:
            for proc in cls._processors.values():
                try:
                    if proc.is_active():
                        proc.stop()
                except Exception as e:
                    logger.warning(f"Error stopping processor in registry: {e}")
            cls._processors.clear()
