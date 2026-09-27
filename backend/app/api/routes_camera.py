"""
Camera Pipeline REST API Endpoints for AURAVISION Offline System
Provides global/standalone camera management, frame ingestion status, and frame metadata access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.schemas.camera import CameraStartRequest, CameraStatusResponse, FrameMetadataResponse
from app.services.camera_service import camera_service
from app.camera.exceptions import (
    CameraAlreadyRunningError,
    CameraStoppedError,
    CameraSourceError,
    InvalidVideoFileError,
)
from app.core.logging import logger

router = APIRouter(prefix="/camera", tags=["Camera Pipeline"])


@router.post("/start", response_model=CameraStatusResponse)
def start_camera(
    req: Optional[CameraStartRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Start the global/standalone camera pipeline.
    Supports 'mock', 'file', and 'webcam' sources.
    """
    try:
        source_type = req.source_type if req else None
        camera_index = req.camera_index if req else None
        file_path = req.file_path if req else None
        target_fps = req.target_fps if req else None
        frame_width = req.frame_width if req else None
        frame_height = req.frame_height if req else None
        buffer_size = req.buffer_size if req else None
        loop = req.loop if req else False

        status_dict = camera_service.start_global_camera(
            source_type=source_type,
            camera_index=camera_index,
            file_path=file_path,
            target_fps=target_fps,
            frame_width=frame_width,
            frame_height=frame_height,
            buffer_size=buffer_size,
            loop=loop,
            db=db
        )
        return status_dict
    except CameraAlreadyRunningError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Camera already running: {str(e)}"
        )
    except (CameraSourceError, InvalidVideoFileError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initialize camera source: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error starting camera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal camera error: {str(e)}"
        )


@router.post("/stop", response_model=CameraStatusResponse)
def stop_camera(db: Session = Depends(get_db)):
    """
    Stop the global camera pipeline and release hardware/file resources cleanly.
    """
    try:
        return camera_service.stop_global_camera(db=db)
    except Exception as e:
        logger.error(f"Error stopping camera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop camera: {str(e)}"
        )


@router.get("/status", response_model=CameraStatusResponse)
def get_camera_status():
    """
    Get current runtime status and metrics of the global camera pipeline.
    """
    return camera_service.get_global_status()


@router.post("/frame", response_model=FrameMetadataResponse)
@router.get("/frame", response_model=FrameMetadataResponse)
def get_camera_frame():
    """
    Fetch metadata for the latest preprocessed frame in the global buffer.
    Excludes raw binary payloads to prevent JSON bloat.
    """
    try:
        frame = camera_service.read_global_frame()
        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                detail="No frame available in buffer."
            )
        return frame.to_metadata_dict()
    except CameraStoppedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera is stopped: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading frame: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read frame: {str(e)}"
        )
