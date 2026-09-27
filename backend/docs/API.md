# AURAVISION REST & WebSocket API Specification

AURAVISION exposes a complete set of local-first REST endpoints and real-time WebSocket event streams.

Base URL: `http://localhost:8000`
Interactive Swagger Documentation: `http://localhost:8000/docs`

---

## 1. System & Health

### `GET /api/health`
Returns system health check and offline status guarantee.

**Response (200 OK):**
```json
{
  "status": "ok",
  "app_name": "AURAVISION-Backend",
  "app_version": "1.0.0",
  "environment": "development",
  "offline_mode": true,
  "timestamp": "2026-09-19T23:30:00Z"
}
```

### `GET /api/system/status`
Returns complete diagnostic telemetry including AI pipeline status, SQLite connection, video capture/recording state, and IP streaming status.

---

## 2. Experiments & Protocols

### `GET /api/experiments`
List all configured experiment protocols.

### `POST /api/experiments`
Create a new experiment with sequential steps.

**Request Body:**
```json
{
  "name": "Sample Handling Experiment",
  "description": "Astronaut mineral specimen containment protocol",
  "version": "1.0.0",
  "steps": [
    {
      "step_number": 1,
      "action_code": "PICK_TOOL",
      "display_name": "Pick tool",
      "description": "Retrieve sterilized tool from rack",
      "expected_objects": ["tool"],
      "required": true
    },
    {
      "step_number": 2,
      "action_code": "OPEN_CONTAINER",
      "display_name": "Open container",
      "expected_objects": ["container"],
      "required": true
    }
  ]
}
```

### `GET /api/experiments/{id}`
Get experiment protocol and steps by ID.

### `PUT /api/experiments/{id}`
Update experiment metadata or replace step definitions.

### `GET /api/experiments/{id}/steps`
Retrieve ordered steps for a specific experiment.

---

## 3. Sessions & Execution

### `POST /api/sessions/start`
Start a live experiment validation session.

**Request Body:**
```json
{
  "experiment_id": "82665394-345e-45ed-9729-f27ded735b90",
  "session_code": "EXP-20260919-01"
}
```

### `POST /api/sessions/{id}/stop`
Stops session, finalizes local MP4 recording, and flushes audit logs.

### `GET /api/sessions/{id}`
Get session status and current step index.

### `GET /api/sessions/{id}/events`
Retrieve chronological sequence validation events.

### `GET /api/sessions/{id}/alerts`
Retrieve all voice/visual alerts generated during session.

### `GET /api/sessions/{id}/log?format=txt|jsonl&download=false`
Retrieve or download the session audit log.

---

## 4. Sequence Validation

### `POST /api/validate`
Validates an observed human action against the deterministic state machine.

**Request Body:**
```json
{
  "session_id": "session-uuid-optional",
  "action_code": "PICK_TOOL",
  "confidence": 0.95,
  "observed_objects": ["tool"]
}
```

**Response (200 OK):**
```json
{
  "result": "VALID",
  "current_step": 2,
  "completed_step": 1,
  "expected_step": 1,
  "observed_step": 1,
  "next_step": 2,
  "next_step_name": "Open container",
  "next_step_description": "Unseal specimen containment vessel.",
  "message": "Step 1 (Pick tool) completed. Proceed to Step 2: Open container.",
  "confidence": 0.95,
  "experiment_complete": false
}
```

---

## 5. Demonstration Scenarios (SIH Simulation Mode)

### `GET /api/demo/scenarios`
Lists available demonstration scenarios:
- `NORMAL`
- `SKIPPED_STEP`
- `OUT_OF_SEQUENCE`
- `LOW_CONFIDENCE`
- `UNKNOWN_OBJECT`

### `POST /api/demo/start`
**Request Body:**
```json
{
  "scenario": "SKIPPED_STEP",
  "speed_multiplier": 1.0
}
```

### `POST /api/demo/stop`
Stops active demo simulation.

---

## 6. Video Pipeline & Live Preview

### `POST /api/video/start`
Start video ingestion (Webcam, file, RTSP, or mock synthetic generator) and local MP4 recording.

### `POST /api/video/stop`
Stop video capture and close active recording.

### `GET /api/video/status`
Get current camera frame count, FPS, recording path, and streaming state.

### `GET /api/video/feed`
Live multipart MJPEG stream for direct display in browser/GUI `<img src="/api/video/feed" />`.

---

## 7. AI Models & Settings

### `GET /api/models/status`
Diagnostic report of all loaded detection, pose, and activity models.

### `GET /api/settings`
Get runtime system settings.

### `POST /api/settings`
Update confidence thresholds, video source, voice settings, and IP stream parameters dynamically.

---

## 8. Real-Time WebSocket

### `WS /ws/events`
Connects via WebSocket to receive real-time JSON events:
- `SYSTEM_STATUS`
- `DETECTION`
- `ACTIVITY`
- `STEP_VALIDATED`
- `STEP_SKIPPED`
- `OUT_OF_SEQUENCE`
- `ALERT`
- `NEXT_STEP`
- `EXPERIMENT_COMPLETE`

**Sample WebSocket Event:**
```json
{
  "type": "STEP_VALIDATED",
  "session_id": "317e937d-165d-4b42-91f8-cdfd8cf29978",
  "data": {
    "step_number": 3,
    "action": "TAKE_SAMPLE",
    "confidence": 0.92,
    "next_step": 4,
    "next_step_name": "Place sample",
    "message": "Step 3 (Take sample) completed. Proceed to Step 4: Place sample."
  },
  "timestamp": "2026-09-19T23:30:15Z"
}
```
