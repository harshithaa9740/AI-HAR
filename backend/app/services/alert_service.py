"""
Alert Management and Dispatch Engine
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.repository import EventRepository
from app.schemas.event import AlertResponse
from app.core.constants import AlertType, AlertSeverity, EventType
from app.services.voice_service import voice_engine
from app.services.websocket_service import ws_manager
from app.core.logging import logger


class AlertService:
    @staticmethod
    def create_and_dispatch_alert(
        db: Optional[Session],
        session_id: Optional[str],
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        voice_prompt: Optional[str] = None
    ) -> AlertResponse:
        """
        Record alert in SQLite, trigger offline local voice TTS, and broadcast via WebSocket.
        """
        spoken = False
        if voice_prompt or message:
            speech_text = voice_prompt or message
            voice_engine.speak(speech_text)
            spoken = True

        alert_id = None
        if db:
            try:
                db_alert = EventRepository.record_alert(
                    db=db,
                    session_id=session_id,
                    alert_type=alert_type.value,
                    severity=severity.value,
                    message=message,
                    spoken=spoken
                )
                alert_id = db_alert.id
            except Exception as e:
                logger.error(f"Failed to record alert in DB: {e}")

        # WebSocket real-time event
        ws_manager.broadcast_sync(
            event_type=EventType.ALERT.value,
            data={
                "alert_id": alert_id,
                "alert_type": alert_type.value,
                "severity": severity.value,
                "message": message,
                "spoken": spoken
            },
            session_id=session_id
        )

        return AlertResponse(
            id=alert_id,
            session_id=session_id,
            alert_type=alert_type.value,
            severity=severity.value,
            message=message,
            spoken=spoken
        )
