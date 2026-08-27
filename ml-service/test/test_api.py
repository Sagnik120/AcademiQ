import base64
import numpy as np
import cv2
import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_base64_image(color=(0, 0, 0)):
    # Create a solid color image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = color
    
    # Encode to JPEG
    _, buffer = cv2.imencode('.jpg', img)
    b64_str = base64.b64encode(buffer).decode('utf-8')
    return b64_str

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_analyze_frame_no_face():
    b64_str = create_base64_image(color=(0,0,0)) # Black image, no face
    
    payload = {
        "attempt_id": "test_attempt_123",
        "frame_base64": b64_str,
        "timestamp": time.time()
    }
    
    response = client.post("/analyze-frame", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["face_detected"] is False
    assert data["face_count"] == 0
    # First time no face: should trigger "absent" alert after 1 second, but we pass current time
    # Wait, the alert classifier requires absence > 1.0s to trigger 'absent'.
    # Because it's the first frame, absence_duration = 0, so alert_type might be None.
    
def test_analyze_frame_extended_absence():
    # Simulate time passing to trigger absent alert
    attempt_id = "test_attempt_456"
    b64_str = create_base64_image()
    
    t0 = time.time()
    # First frame (sets memory)
    client.post("/analyze-frame", json={"attempt_id": attempt_id, "frame_base64": b64_str, "timestamp": t0})
    
    # Second frame 2 seconds later (should trigger "absent")
    response2 = client.post("/analyze-frame", json={"attempt_id": attempt_id, "frame_base64": b64_str, "timestamp": t0 + 2.0})
    
    data = response2.json()
    assert data["alert_type"] == "absent"
    assert data["severity"] == "high"

    # Third frame 4 seconds later (should trigger "absent_extended")
    response3 = client.post("/analyze-frame", json={"attempt_id": attempt_id, "frame_base64": b64_str, "timestamp": t0 + 4.0})
    
    data3 = response3.json()
    assert data3["alert_type"] == "absent_extended"
    assert data3["severity"] == "critical"
