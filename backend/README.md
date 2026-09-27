# AURAVISION — Offline AI Human Activity Recognition & Experiment Validation System

AURAVISION is an **offline-first, edge-deployable AI system** designed to continuously monitor, recognize, and validate human/astronaut experimental procedures from fixed-payload cameras.

Built for the **Smart India Hackathon (SIH) 2026**.

---

## Key Features

1. **Deterministic Experiment Protocol State Machine**:
   - Validates live human actions against sequential protocol steps (1 → 2 → 3 → ...).
   - Detects skipped steps (`STEP_SKIPPED`) and out-of-sequence actions (`OUT_OF_SEQUENCE`).
   - Rejects unconfident detections (`confidence < threshold` → `VERIFY_REQUIRED`).
   - Flags unauthorized/unknown actions (`UNKNOWN_ACTION`).
2. **Modular Real-Time Camera & Ingestion Pipeline (Step 7)**:
   - Abstract `CameraSource` supporting synthetic mock frames, local video files, and physical webcams.
   - Paced frame acquisition with FPS rate limiting (`TARGET_FPS`).
   - Bounded in-memory frame ring buffer (`FRAME_BUFFER_SIZE`) prioritizing newest frames.
   - Zero raw frames persisted to SQLite; strict transient processing.
3. **AI Inference & Provider Integration Layer (Step 8)**:
   - Modular `AIProvider` abstraction and central `ModelRegistry`.
   - Dedicated `InferenceEngine` measuring execution timing (`inference_time_ms`) and preserving object evidence.
   - Session-scoped inference with optional validation flag (`validate=true|false`).
   - Strict separation of concerns: AI layer produces honest observations (`ObservedAction`); Sequence Validator determines protocol validity.
4. **Real-Time Processing Loop & Experiment Validation Pipeline (Step 9)**:
   - Continuous frame-by-frame orchestration: Camera -> Frame -> AI Inference -> Sequence Validator -> Session/Events -> ProcessingResult.
   - Paced background worker thread respecting `TARGET_FPS` rate limiting.
   - Frame dropping handling: skips backlog to prioritize newest frames during real-time load.
   - In-memory thread-safe runtime metrics (`frames_received`, `frames_processed`, `frames_dropped`, `processing_fps`, latency measurements).
   - Single-worker concurrency guarantee per session with thread-safe lifecycle control (`start`, `stop`, `pause`, `resume`).
   - Single-frame error isolation: worker loop survives temporary inference exceptions without crashing.
   - Automatic experiment completion handling: triggers session completion and releases hardware upon final step validation.
5. **Next Step Suggestion Engine**: Automatically yields next expected actions and descriptions.
6. **Local Offline Voice Alert Engine**: Generates audible spoken feedback without cloud APIs.
7. **Structured Audit Logs**: Writes timestamped `.log` (human-readable) and `.jsonl` audit trails.
8. **Local Video Capture & MP4 Recording**: Ingests webcam, MP4 files, RTSP streams, or synthetic frames.
9. **Real-Time WebSocket**: Broadcasts detections, pose metrics, validation results, and alerts to UI.
10. **Demonstration & Mock AI Scenarios**: Built-in SIH evaluation scenarios (`NORMAL`, `SKIPPED_STEP`, `OUT_OF_SEQUENCE`, `LOW_CONFIDENCE`, `UNKNOWN_OBJECT`).

---

## System Architecture Pipeline

```text
LOCAL CAMERA / VIDEO
        ↓
FRAME INGESTION (Mock / File / Webcam)
        ↓
FRAME PREPROCESSING (Normalization / Resize)
        ↓
AI INFERENCE ENGINE (AIProvider / InferenceEngine)
        ↓
STANDARDIZED OBSERVATION (ObservedAction)
        ↓
SEQUENCE VALIDATOR (Deterministic State Machine)
        ↓
SESSION & EVENT MANAGEMENT (DB Sync & Audit Events)
        ↓
REAL-TIME PROCESSOR RESULT & METRICS (In-Memory Runtime Results)
```

> [!NOTE]
> "This camera pipeline is an offline local frame-ingestion layer. It does not perform AI inference by itself."

> [!IMPORTANT]
> "The current AI provider is a deterministic development/mock implementation. It is not a trained astronaut activity-recognition model."

---

## Directory Structure

```text
backend/
├── app/
│   ├── main.py                     # FastAPI application & lifespan entrypoint
│   ├── api/                        # Modular REST endpoints
│   │   ├── routes_health.py        # Health & system diagnostics
│   │   ├── routes_experiments.py   # Protocol & step configuration
│   │   ├── routes_sessions.py      # Session lifecycle, logs, & alerts
│   │   ├── routes_processing.py    # Real-time processing loop endpoints (Step 9)
│   │   ├── routes_camera.py        # Standalone & global camera control
│   │   ├── routes_inference.py     # Standalone AI inference endpoints
│   │   ├── routes_models.py        # AI model registry & diagnostics
│   │   ├── routes_video.py         # Video capture & MJPEG live feed
│   │   ├── routes_validate.py      # Action validation API
│   │   ├── routes_demo.py          # SIH demonstration scenario runner
│   │   └── routes_settings.py      # Dynamic runtime settings
│   ├── camera/                     # Real-time frame ingestion subsystem (Step 7)
│   │   ├── camera_source.py        # Abstract camera source interface
│   │   ├── mock_camera.py          # Deterministic synthetic test camera
│   │   ├── video_file_source.py    # Local offline video file source (OpenCV)
│   │   ├── real_camera.py          # Local webcam hardware source with fallback
│   │   ├── frame_model.py          # Transient Frame model
│   │   ├── frame_processor.py      # Resizing, normalization, indexing
│   │   ├── camera_manager.py       # Thread lifecycle, FPS pacing, ring buffer
│   │   └── exceptions.py           # Camera error types
│   ├── ml/                         # AI Perception & Inference subsystem (Step 8)
│   │   ├── model_provider.py       # Abstract AIProvider interface
│   │   ├── mock_provider.py        # Deterministic MockAIProvider
│   │   ├── model_registry.py       # Provider registry & model discovery
│   │   ├── inference_engine.py     # Frame -> AI -> ObservedAction orchestrator
│   │   ├── mock_activity_model.py  # Scenario-based activity model
│   │   ├── mock_detector.py        # Object & pose detector
│   │   └── exceptions.py           # AI inference custom exceptions
│   ├── core/
│   │   ├── config.py               # Pydantic settings & environment variables
│   │   ├── constants.py            # Enums for states, alerts, and scenarios
│   │   └── logging.py              # Structured logging
│   ├── db/
│   │   ├── database.py             # SQLite engine & session
│   │   ├── models.py               # SQLAlchemy ORM schemas
│   │   └── repository.py           # CRUD data access layer
│   ├── schemas/                    # Pydantic request/response models
│   │   └── processing.py           # Processing status & metrics schemas
│   ├── services/                   # Core business logic & services
│   │   ├── realtime_processor.py   # Continuous processing loop service (Step 9)
│   │   ├── processing_state.py     # Processing state transition manager
│   │   ├── processing_metrics.py   # In-memory metrics & result tracker
│   │   ├── sequence_validator.py   # State machine sequence validator
│   │   ├── camera_service.py       # Camera orchestration service
│   │   ├── session_service.py      # Session lifecycle service
│   │   ├── event_service.py        # Central event recording & timeline
│   │   ├── alert_service.py        # Alert persistence & dispatch
│   │   └── websocket_service.py    # Real-time WebSocket connection manager
│   └── workers/
│       └── video_worker.py         # Background video inference loop
├── data/                           # Local storage (SQLite DB, logs, recordings)
├── docs/                           # Architecture, API, ML & Offline Docs
├── tests/                          # Automated Pytest test suites (151+ tests)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Configuration Variables (.env)

```ini
# App
APP_ENV=development
PORT=8000
OFFLINE_ONLY=true

# Camera Ingestion Pipeline (Step 7)
CAMERA_SOURCE=mock          # Options: 'mock', 'file', 'webcam'
CAMERA_INDEX=0              # Hardware device index
VIDEO_FILE_PATH=            # Absolute or local path to video file
TARGET_FPS=10               # Ingestion frame rate limit
FRAME_WIDTH=640             # Canonical frame width
FRAME_HEIGHT=480            # Canonical frame height
FRAME_BUFFER_SIZE=5         # Bounded in-memory ring buffer size

# AI Inference Pipeline (Step 8)
AI_MODE=mock                # Active AI mode: 'mock' (reserved: 'local')
AI_MODEL_PATH=              # Optional path to local model weights
AI_CONFIDENCE_THRESHOLD=0.50# Base confidence threshold
AI_DEVICE=cpu               # Target execution device: 'cpu'
```

---

## Key API Endpoints

### 1. Real-Time Processing Loop Endpoints (Step 9)
- `POST /api/sessions/{id}/processing/start`: Start continuous AI inference and validation loop for active session.
- `POST /api/sessions/{id}/processing/stop`: Stop continuous processing loop cleanly.
- `POST /api/sessions/{id}/processing/pause`: Pause frame processing while preserving session and validator state.
- `POST /api/sessions/{id}/processing/resume`: Resume frame processing from paused state.
- `GET /api/sessions/{id}/processing/status`: Retrieve worker state (`STOPPED`, `STARTING`, `RUNNING`, `PAUSED`, `STOPPING`, `ERROR`), camera/AI health, frames processed, and latest result.
- `GET /api/sessions/{id}/processing/metrics`: Retrieve in-memory runtime processing metrics (latency, FPS, dropped frames, outcome counts).

### 2. Camera Pipeline Endpoints
- `POST /api/camera/start`: Start global camera manager with configured source.
- `POST /api/camera/stop`: Stop global camera pipeline and release resources.
- `GET /api/camera/status`: Inspect camera state, FPS, buffered frames, uptime.
- `GET /api/camera/frame` or `POST /api/camera/frame`: Retrieve latest frame metadata (no raw binary).
- `POST /api/sessions/{id}/camera/start`: Start session-scoped camera pipeline.
- `POST /api/sessions/{id}/camera/stop`: Stop session-scoped camera pipeline.
- `GET /api/sessions/{id}/camera/status`: Session-scoped camera status.
- `GET /api/sessions/{id}/camera/frame`: Session-scoped latest frame metadata.

### 3. AI Inference Endpoints
- `POST /api/inference/frame`: Run AI perception on latest frame or simulated step frame.
- `GET /api/models`: List all registered AI providers in `ModelRegistry`.
- `GET /api/models/active`: Retrieve active AI model metadata and capabilities.
- `POST /api/sessions/{id}/inference/frame?validate=true|false`:
  - `validate=false`: Returns pure AI observation (`ObservedAction`) with detection evidence and execution time (`inference_time_ms`).
  - `validate=true`: Feeds `ObservedAction` into `SequenceValidator`, updates session progress, records events, and returns both observation and validation outcomes.

### 4. Session & Event Management Endpoints
- `POST /api/sessions`: Create session in `CREATED` state.
- `POST /api/sessions/{id}/start`: Start session (`CREATED -> RUNNING`).
- `POST /api/sessions/{id}/pause`: Pause session (`RUNNING -> PAUSED`).
- `POST /api/sessions/{id}/resume`: Resume session (`PAUSED -> RUNNING`).
- `POST /api/sessions/{id}/stop`: Stop session (`RUNNING/PAUSED -> STOPPED`).
- `GET /api/sessions/{id}/events`: Unified chronological timeline (`SYSTEM`, `SEQUENCE`, `ALERT`, `DETECTION`).

---

## Running Automated Tests

```bash
cd backend
python -m pytest -v
```

All **151 tests pass** covering Database, Protocol Rules, Deterministic State Machine Validation, Mock AI Pipeline, Session Lifecycles & Timelines, Real-Time Camera Pipeline, AI Inference Engine, and Real-Time Processing Loop.

