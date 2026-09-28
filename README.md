# AURAVISION — Offline AI Human Activity Recognition & BAS Experiment Validation
### Designed for ISRO / Smart India Hackathon (SIH)

AURAVISION is an **offline, edge-native AI Human Activity Recognition (HAR) and Bio-Astronautics (BAS) Experiment Protocol Verification System**. It operates strictly over local Wi-Fi or air-gapped Local Area Networks (LAN) with **zero internet dependencies** (no Firebase, Supabase, Google Maps, or hosted authentication).

---

## 🛰️ Architecture & Offline LAN Connectivity

```
  +-------------------------------------+             +-----------------------------------------+
  |    OPERATOR / JUDGES CLIENT LAPTOP  |             |      FASTAPI AI EDGE SERVER LAPTOP      |
  |                                     |   Local     |                                         |
  |  AURAVISION React + TS Frontend     |   Wi-Fi     |  FastAPI (Uvicorn) :8000                |
  |  http://<CLIENT_IP>:3000            | ----------> |  - REST API (/api/health, /sessions...) |
  |  - Central Config (localStorage)    |    LAN      |  - WebSocket Bus (/ws/events)           |
  |  - Dynamic IP Connection Modal      |             |  - MJPEG Camera Stream (/api/video/feed)|
  |  - Offline Preview Mode (Mock Data) |             |  - SQLite Audit Store (auravision.db)   |
  +-------------------------------------+             +-----------------------------------------+
```

### Dynamic Backend Server IP Configuration
- On first launch, AURAVISION displays the **Connect to AURAVISION Backend** dialog.
- Enter the IPv4 address of the backend machine (e.g. `192.168.1.25`) and port `8000`.
- Click **Test Connection (GET /api/health)** to verify LAN ping and health.
- URLs are computed dynamically:
  - **REST Base URL:** `http://<BACKEND_IP>:8000`
  - **WebSocket URL:** `ws://<BACKEND_IP>:8000/ws/events`
  - **Live Camera MJPEG:** `http://<BACKEND_IP>:8000/api/video/feed`
- If the backend is off or unreachable, click **Offline Preview Mode** to test the entire interface with high-fidelity realistic data.

---

## 🚀 How to Run

### 1. One-Click Full-Stack Launch (Backend + Frontend)
Double-click:
```bat
start-auravision.bat
```
This automatically starts:
1. The **FastAPI backend** on `0.0.0.0:8000`
2. The **AURAVISION React frontend** on `0.0.0.0:3000`
3. Opens `http://localhost:3000` in your default browser.

### 2. Launching Services Individually
- **React Frontend:** Double-click `start-frontend.bat` (serves at `http://localhost:3000` and `http://<YOUR_IP>:3000`)
- **FastAPI Backend:** Run in PowerShell or Command Prompt:
  ```powershell
  cd backend
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

---

## 🖥️ Screen & Page Overview

AURAVISION includes a collapsible sidebar navigation with **7 responsive pages**:

### 1. Live Mission (Primary Page)
- **Top Mission Header:** Experiment name (`BAS-CHEM-802`), session code, status pill (`RUNNING`, `PAUSED`, `STOPPED`), elapsed timer, and controls (**Start / Pause / Resume / Stop / Reset**).
- **Live Optical Stream:** MJPEG camera feed (`/api/video/feed`) with synthetic fallback canvas visualizer.
- **HUD Overlays:** `LIVE` badge, bounding boxes for tools and containers, action label, confidence indicator, 33-point pose skeleton toggle, and recording timer.
- **Procedure Validation Stepper (6 Checkpoints):**
  1. *Pick tool (Pipette)*
  2. *Open container (Specimen vessel)*
  3. *Take sample (2.5 ml aspiration)*
  4. *Place sample (Reaction well A1)*
  5. *Seal container (Hermetic lock)*
  6. *Return tool (Sanitized rack)*
  - Completed steps in **Green**, Current expected step in **Cyan**, Upcoming in **Muted Gray**, Violations in **Red / Amber**.
- **Next-Step Guidance Box:** Prominently highlights upcoming required actions and expected objects.
- **Real-Time Telemetry Grid:** Processing FPS, frame count, dropped frames, average latency, camera health, and AI status.
- **Live Alert Feed:** `STEP_VALIDATED`, `STEP_SKIPPED`, `OUT_OF_SEQUENCE`, `VERIFY_REQUIRED`, `UNKNOWN_ACTION`, `EXPERIMENT_COMPLETE`.

### 2. Overview
- Operational KPI summary: Compliance rate (%), active session code, optical sensor health, AI engine status.
- SVG real-time telemetry line chart (FPS & latency consistency).
- Recent session histories and quick-jump action buttons.

### 3. Experiments
- Sequential protocol editor and sequence builder.
- Add, edit, reorder, or delete protocol steps with step number, action code, display name, description, and expected object tags.
- Protocol validation with integrity checks.

### 4. Sessions & Audit
- Historical mission runs with status badges and compliance scores.
- Filter tabs: **All Events**, **Sequence Events**, **Detections**, **Alerts**, **System Events**.
- **Downloadable Local Logs:** One-click **Export TXT** and **Export JSONL** (zero cloud reliance; generated client-side).

### 5. AI Models
- Active model architecture (YOLOv8 + MediaPipe Pose).
- Hardware execution target (`Local Intel Edge CPU / Integrated GPU` or `CUDA / TensorRT`).
- Sensitivity sliders for action recognition threshold and object detector threshold.
- Pipeline benchmark diagnostic test button.

### 6. Demo Mode (Judges Evaluation Mode)
- 5 Preconfigured Fault Injection Scenarios:
  - `NORMAL`: Standard nominal sequential progression (Steps 1 → 6 validated).
  - `SKIPPED_STEP`: Jumps step, immediately raising `STEP_SKIPPED` alert.
  - `OUT_OF_SEQUENCE`: Premature action attempt triggering `OUT_OF_SEQUENCE` alert.
  - `LOW_CONFIDENCE`: Line-of-sight occlusion raising `VERIFY_REQUIRED`.
  - `UNKNOWN_OBJECT`: Foreign object introduction raising `UNKNOWN_ACTION`.
- Controls: Start Simulation, Stop Simulation, speed selector (`1x`, `2x`, `5x`), and live terminal output stream.

### 7. System Settings
- Dynamic Backend Server IP and Port configuration with live connection test.
- Optical ingestion source selector (`Simulated Feed`, `Physical USB Webcam`, `Local Video File`).
- Telemetry recording toggle and synthesized voice alert toggle.
- Mission audit log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

---

## 🔒 Offline & Air-Gapped Network Verification

- **Zero Cloud CDNs:** All CSS, vector logos, and fonts are bundled locally.
- **Zero Internet Requirement:** The system operates seamlessly on an isolated wireless router, ad-hoc hotspot, or Ethernet switch with no internet access.
- **Fallback Simulation:** In the event the backend laptop disconnects or restarts, the frontend gracefully preserves state and falls back to deterministic local mock data.
