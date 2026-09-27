"""
AURAVISION — Offline AI Human Activity Recognition & Experiment Validation System
FastAPI Backend Application Entry Point
"""
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db, SessionLocal
from app.services.experiment_service import experiment_service
from app.services.websocket_service import ws_manager
from app.services.video_service import video_service
from app.workers.video_worker import video_worker
from app.camera.camera_manager import CameraManagerRegistry
from app.services.realtime_processor import RealTimeProcessorRegistry

# Import API routers
from app.api.routes_health import router as health_router
from app.api.routes_experiments import router as experiments_router
from app.api.routes_sessions import router as sessions_router
from app.api.routes_processing import router as processing_router
from app.api.routes_camera import router as camera_router
from app.api.routes_inference import router as inference_router
from app.api.routes_video import router as video_router
from app.api.routes_validate import router as validate_router
from app.api.routes_demo import router as demo_router
from app.api.routes_models import router as models_router
from app.api.routes_settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan handler."""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV} | AI Mode: {settings.AI_MODE}")
    logger.info("Local-First & Offline Architecture Guarantee: ACTIVE")
    logger.info("=" * 60)

    # 1. Initialize SQLite Database Tables
    init_db()
    logger.info("SQLite database initialized.")

    # 2. Seed default Sample Handling Experiment
    with SessionLocal() as db:
        experiment_service.seed_default_experiment_if_empty(db)

    # 3. Ensure Local Directories
    settings.ensure_directories()

    yield

    # Shutdown logic
    logger.info("Shutting down AURAVISION Backend...")
    RealTimeProcessorRegistry.stop_all()
    CameraManagerRegistry.stop_all()
    video_worker.stop()
    video_service.stop_capture()
    logger.info("Shutdown complete.")



app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Offline AI Human Activity Recognition & Experiment Protocol Validation Engine for Fixed-Payload Cameras.",
    lifespan=lifespan
)

# Configure CORS (Allows local frontend GUI connections)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST API Routers
app.include_router(health_router, prefix="/api")
app.include_router(experiments_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(processing_router, prefix="/api")
app.include_router(camera_router, prefix="/api")
app.include_router(inference_router, prefix="/api")
app.include_router(video_router, prefix="/api")
app.include_router(validate_router, prefix="/api")
app.include_router(demo_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(settings_router, prefix="/api")





# Real-time WebSocket endpoint
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """Real-time event streaming for UI clients."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep socket alive and receive any client ping/heartbeats
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        await ws_manager.disconnect(websocket)


@app.get("/")
def root_info():
    """Root metadata endpoint."""
    return {
        "project": "AURAVISION",
        "description": "Offline AI Human Activity Recognition & Experiment Validation System",
        "version": settings.APP_VERSION,
        "offline": True,
        "docs_url": "/docs",
        "api_prefix": "/api",
        "websocket_url": "/ws/events"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
