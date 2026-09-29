"""
Video Ingestion, Recording, and MJPEG Live Preview Endpoints
"""
import time
from typing import Optional
import os
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import cv2
from app.db.database import get_db
from app.schemas.system import VideoStartRequest, VideoStatusResponse
from app.services.video_service import video_service
from app.workers.video_worker import video_worker
from app.core.logging import logger

router = APIRouter(prefix="/video", tags=["Video Pipeline"])


@router.post("/start", response_model=VideoStatusResponse)
def start_video(payload: Optional[VideoStartRequest] = None):
    """Start local video capture and optional local MP4 recording."""
    source = payload.video_source if payload else None
    record = payload.record if payload else True
    session_id = payload.session_id if payload else None

    video_service.start_capture(source=source, record=record, session_id=session_id)
    video_worker.start(session_id=session_id)

    return video_service.get_status()


@router.post("/stop", response_model=VideoStatusResponse)
def stop_video(db: Session = Depends(get_db)):
    """Stop video capture and close active recording file."""
    sess_id = video_service.current_session_id
    video_summary = video_service.stop_capture()
    video_worker.stop()

    rec_path = video_summary.get("recording_path")
    if sess_id and rec_path and os.path.exists(rec_path):
        try:
            from app.db.repository import ArtifactRepository, SessionRepository
            sess = SessionRepository.get_by_id(db, sess_id)
            if sess:
                ArtifactRepository.create(
                    db=db,
                    session_id=sess.id,
                    artifact_type="recording",
                    file_path=str(rec_path),
                    file_name=os.path.basename(rec_path),
                    mime_type="video/mp4",
                    file_size_bytes=os.path.getsize(rec_path),
                    metadata={
                        "duration": video_summary.get("duration_seconds", 0),
                        "fps": video_summary.get("fps", 30)
                    }
                )
        except Exception as e:
            logger.error(f"Failed to record session artifact: {e}")

    return video_service.get_status()


@router.get("/status", response_model=VideoStatusResponse)
def get_video_status():
    """Get current video stream, recording path, FPS, and resolution."""
    return video_service.get_status()


def generate_mjpeg_stream():
    """Generator function yielding multipart MJPEG frames for offline browser video player."""
    while True:
        frame = video_service.get_latest_frame()
        if frame is not None:
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.04)  # ~25 fps


@router.get("/feed")
def get_video_feed():
    """Live MJPEG video preview endpoint for frontend UI."""
    if not video_service.is_running:
        video_service.start_capture()
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
