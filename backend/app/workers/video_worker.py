"""
Background Video Processing and AI Inference Worker
"""
import time
import threading
import asyncio
from typing import Optional
from app.services.video_service import video_service
from app.services.detection_service import detection_service
from app.services.experiment_service import experiment_service
from app.services.websocket_service import ws_manager
from app.db.database import SessionLocal
from app.db.repository import EventRepository
from app.core.constants import EventType
from app.core.logging import logger


class VideoWorker:
    def __init__(self):
        self.is_running = False
        self.active_session_id: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.fps = 10  # Inference loop rate (10 fps)

    def start(self, session_id: Optional[str] = None):
        if self.is_running:
            self.active_session_id = session_id
            return

        self.active_session_id = session_id
        self.is_running = True
        self._stop_event.clear()
        
        # Ensure video capture is active
        if not video_service.is_running:
            video_service.start_capture(session_id=session_id)

        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info(f"Video AI Worker started for session {session_id}")

    def stop(self):
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Video AI Worker stopped.")

    def _worker_loop(self):
        while not self._stop_event.is_set() and self.is_running:
            try:
                frame = video_service.get_latest_frame()
                if frame is not None:
                    # Run AI Pipeline
                    ai_results = detection_service.process_frame(frame)
                    
                    # Broadcast real-time detections over WebSocket
                    ws_manager.broadcast_sync(
                        event_type=EventType.DETECTION.value,
                        data={
                            "boxes": ai_results["boxes"],
                            "pose_available": ai_results["pose"] is not None
                        },
                        session_id=self.active_session_id
                    )

                    # Check Activity
                    activity = ai_results.get("activity")
                    if activity and activity.get("action") not in (None, "IDLE"):
                        ws_manager.broadcast_sync(
                            event_type=EventType.ACTIVITY.value,
                            data=activity,
                            session_id=self.active_session_id
                        )

                        # If an active session is running, validate against experiment sequence
                        if self.active_session_id:
                            with SessionLocal() as db:
                                sess = SessionRepository.get_by_id(db, self.active_session_id)
                                if sess and sess.status == "RUNNING":
                                    experiment_service.validate_session_action(
                                        db=db,
                                        session_id=self.active_session_id,
                                        action_code=activity["action"],
                                        confidence=activity["confidence"],
                                        observed_objects=activity.get("objects", [])
                                    )
                                    # Also record detection event
                                    EventRepository.record_detection(
                                        db=db,
                                        session_id=self.active_session_id,
                                        event_type="ACTIVITY_RECOGNITION",
                                        action_code=activity["action"],
                                        confidence=activity["confidence"],
                                        metadata_json=activity
                                    )

                time.sleep(1.0 / self.fps)
            except Exception as e:
                logger.error(f"Error in VideoWorker loop: {e}")
                time.sleep(0.5)


video_worker = VideoWorker()
