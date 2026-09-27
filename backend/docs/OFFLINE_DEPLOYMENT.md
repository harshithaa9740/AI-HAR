# Offline Deployment & Edge Hardware Guide

## 1. Zero-Internet Operation
AURAVISION requires zero internet connectivity at runtime:
- **SQLite Database**: Stored in `data/auravision.db`.
- **Video Storage**: Stored in `data/recordings/*.mp4`.
- **Session Logs**: Stored in `data/logs/*.log` and `*.jsonl`.
- **TTS Engine**: Uses offline speech synthesis (Windows SAPI / Linux eSpeak / `pyttsx3`) or Mock Voice.
- **AI Models**: Run locally on CPU/CUDA via PyTorch/ONNX Runtime.

## 2. Hardware Video Sources
Configure `VIDEO_SOURCE` in `.env`:
- **USB Webcam / Fixed Camera**: `VIDEO_SOURCE=0`
- **Pre-recorded Experiment Video**: `VIDEO_SOURCE=/path/to/experiment.mp4`
- **Local Network RTSP Stream**: `VIDEO_SOURCE=rtsp://192.168.1.100:554/live`
- **Synthetic Headless Generator**: `VIDEO_SOURCE=mock`

## 3. Local IP Streaming
To stream payload camera feed to a specific ground station IP:
```ini
STREAM_ENABLED=true
STREAM_DESTINATION_IP=192.168.1.50
STREAM_PORT=8554
```
Frames are transmitted directly via UDP/MJPEG datagrams with zero external cloud routing.
