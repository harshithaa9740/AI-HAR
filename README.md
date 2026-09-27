# AURAVISION - Offline AI Protocol Sequence Validator (SIH Edition)

AURAVISION is an offline real-time AI perception and sequence validation dashboard designed for laboratory Standard Operating Procedures (SOPs) and Smart India Hackathon (SIH).

## 🚀 Quick Start

### 1. View in Browser
The local server is already running! Open this link in your web browser:
👉 **[http://localhost:8080/](http://localhost:8080/)**

### 2. Launch Anytime
To launch the server manually in the future, simply double-click:
- **`start-app.bat`** (or right-click `server.ps1` -> Run with PowerShell)

---

## 🌟 Key Features

1. **Optical Perception Feed**:
   - **Sample MP4 Video**: Plays real lab experiment recordings from the dataset.
   - **Synthetic AI Canvas**: High-contrast vision engine with simulated hands and keypoints.
   - **Hardware Webcam**: Stream real camera video directly from your webcam with live bounding box overlays.

2. **Deterministic Sequence Validator**:
   - Validates multi-step SOP compliance (`PICK_TOOL` -> `OPEN_CONTAINER` -> `TAKE_SAMPLE` -> `PLACE_SAMPLE` -> `CLOSE_CONTAINER`).
   - Detects violations: `STEP_SKIPPED`, `OUT_OF_SEQUENCE`, `MISSING_OBJECT`, `LOW_CONFIDENCE`, and `UNKNOWN_ACTION`.

3. **Voice Guidance & Audio Alerts**:
   - Built-in Text-to-Speech (TTS) engine speaks instructions and alerts.
   - Synthesized sound effects (Web Audio API) for instant audible feedback.

4. **Scenario Simulator**:
   - Test 6 realistic scenarios: Normal, Skipped Step, Out of Sequence, Low Confidence, Missing Object, Unknown Action.
   - Step-by-Step execution or automated Auto-Play mode.

5. **Unified Audit Log**:
   - Real-time chronological audit trail of all actions, detections, and alerts.
   - One-click JSON export.
