import base64
import cv2
import numpy as np
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import FrameRequest, FrameAnalysisResponse
from app.services.face_detector import detect_faces
from app.services.pose_estimator import estimate_pose
from app.services.alert_classifier import get_alert_for_frame

app = FastAPI(title="AcademiQ ML Proctoring Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze-frame", response_model=FrameAnalysisResponse)
async def analyze_frame(request: FrameRequest):
    try:
        # 1. Decode base64 image
        # Strip data URL prefix if present (e.g., "data:image/jpeg;base64,")
        b64_str = request.frame_base64
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
            
        img_bytes = base64.b64decode(b64_str)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img_bgr is None:
            raise ValueError("Invalid image format")
            
        # 2. Detect Faces
        face_count, cropped_face = detect_faces(img_bgr)
        face_detected = (face_count > 0)
        
        # 3. Estimate Pose (Only if exactly 1 face detected)
        yaw, pitch, roll = None, None, None
        confidence = 1.0 # Placeholder for model confidence
        
        if face_count == 1 and cropped_face is not None:
            yaw, pitch, roll = estimate_pose(cropped_face)
            
        # 4. Classify Alert
        # If timestamp not provided, use current server time
        ts = request.timestamp if request.timestamp > 0 else time.time()
        
        alert_type, severity = get_alert_for_frame(
            attempt_id=request.attempt_id,
            face_count=face_count,
            yaw=yaw,
            pitch=pitch,
            current_time=ts
        )
        
        return FrameAnalysisResponse(
            face_detected=face_detected,
            face_count=face_count,
            alert_type=alert_type,
            severity=severity,
            confidence=confidence,
            yaw=yaw,
            pitch=pitch,
            roll=roll
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Frame analysis failed: {str(e)}")
