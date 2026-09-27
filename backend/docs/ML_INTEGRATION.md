# Machine Learning & AI Integration Guide

AURAVISION provides clean abstract interfaces to plug in production models without altering the core sequence validation engine.

---

## 1. Object Detection (`app/ml/yolo_detector.py`)
To integrate custom YOLO weights (e.g. YOLOv8, YOLOv11 trained on lab objects):
1. Place weights in `models/best.pt`.
2. Configure `.env`:
   ```ini
   AI_MODE=production
   MODEL_OBJECT_PATH=models/best.pt
   ```
3. Install ultralytics:
   ```bash
   pip install ultralytics
   ```

---

## 2. Pose & Hand Tracking (`app/ml/pose_estimator.py`)
AURAVISION includes a MediaPipe Pose and Hand tracker wrapper with automatic fallback.
Install MediaPipe:
```bash
pip install mediapipe
```

---

## 3. Human Activity Recognition (`app/ml/activity_model.py`)
The HAR engine consumes:
- Sliding window of video frames (`List[np.ndarray]`)
- Detected object bounding boxes (`List[BoundingBox]`)
- Hand keypoints (`PoseResult`)

It performs spatio-temporal rule and model fusion to output standardized `ActivityDetection` events:
```json
{
  "action": "TAKE_SAMPLE",
  "confidence": 0.94,
  "objects": ["container", "sample"]
}
```
