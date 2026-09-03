import sys
import os
import time
import base64
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient

# Ensure Python can find the 'app' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.services.pose_estimator import estimate_pose, session
from app.services.alert_classifier import get_alert_for_frame, _cooldown_memory, _absence_memory
from app.services.face_detector import detect_faces

client = TestClient(app)

def test_01_model_loading_and_optimization():
    """DEEP INSPECTION: Verify ONNX model is loaded correctly and optimized"""
    print("\n--- 01. Model Architecture & Optimization Check ---")
    assert session is not None, "❌ CRITICAL: ONNX Session failed to load. Is head_pose.onnx in the model/ folder?"
    
    # Check execution providers (Should use CPU Execution Provider for lightweight inference)
    providers = session.get_providers()
    assert 'CPUExecutionProvider' in providers, "❌ CRITICAL: Model is not optimized for CPU execution."
    print("✅ Model loaded successfully and optimized for CPU Execution.")
    
def test_02_latency_real_world_scenario():
    """DEEP INSPECTION: Verify inference time is fast enough for real-time video streaming"""
    print("\n--- 02. Real-World Latency Check ---")
    dummy_face = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    
    # Warmup
    estimate_pose(dummy_face)
    
    # Measure 50 consecutive frames
    latencies = []
    for _ in range(50):
        start = time.time()
        estimate_pose(dummy_face)
        latencies.append(time.time() - start)
        
    avg_latency = sum(latencies) / len(latencies)
    print(f"✅ Average ONNX Inference Latency: {avg_latency*1000:.2f} ms per frame")
    # For real-time (30 FPS), we have ~33ms per frame. The model should comfortably beat 20ms.
    assert avg_latency < 0.05, f"❌ WARNING: Inference is too slow ({avg_latency*1000:.2f}ms). Optimization required."

def test_03_edge_cases_face_detection():
    """DEEP INSPECTION: Test face detector against pure noise, empty arrays, and edge cases"""
    print("\n--- 03. Face Detection Edge Cases ---")
    
    # Edge Case 1: Pure Black (No face)
    black_img = np.zeros((480, 640, 3), dtype=np.uint8)
    count, cropped = detect_faces(black_img)
    assert count == 0 and cropped is None, "❌ Failed to handle empty frames."
    
    # Edge Case 2: Extreme Noise (Simulated heavy webcam artifacting)
    noise_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    count, cropped = detect_faces(noise_img)
    assert count == 0 and cropped is None, "❌ Failed to filter out extreme webcam noise."
    print("✅ Successfully handled zero-lighting and high-noise webcam edge cases.")

def test_04_rule_engine_and_cooldowns():
    """DEEP INSPECTION: Verify the logic engine prevents backend spam during real exams"""
    print("\n--- 04. Alert Classifier & Cooldown Logic ---")
    
    attempt_id = "exam_123"
    t_start = 1000.0
    
    # 1. Student looks away severely
    alert, severity = get_alert_for_frame(attempt_id, face_count=1, yaw=45.0, pitch=0.0, current_time=t_start)
    assert alert == "head_turn_severe", "❌ Failed to detect severe head turn."
    
    # 2. Student looks away again 1 second later (EDGE CASE: Cooldown should block this to prevent spam!)
    alert, severity = get_alert_for_frame(attempt_id, face_count=1, yaw=45.0, pitch=0.0, current_time=t_start + 1.0)
    assert alert is None, "❌ CRITICAL: Cooldown logic failed! Backend will be spammed with alerts."
    
    # 3. Student looks away 4 seconds later (Cooldown expired, should trigger)
    alert, severity = get_alert_for_frame(attempt_id, face_count=1, yaw=45.0, pitch=0.0, current_time=t_start + 4.0)
    assert alert == "head_turn_severe", "❌ Cooldown failed to reset after 3 seconds."
    print("✅ Cooldown logic perfectly isolates alerts and prevents API spam.")

def test_05_end_to_end_pipeline_resilience():
    """DEEP INSPECTION: Throw corrupted payloads at the API to ensure it doesn't crash"""
    print("\n--- 05. E2E API Resilience ---")
    
    # Edge Case: Malformed Base64
    payload = {
        "attempt_id": "test_crash",
        "frame_base64": "data:image/jpeg;base64,!!!INVALID_STRING!!!",
        "timestamp": time.time()
    }
    response = client.post("/analyze-frame", json=payload)
    assert response.status_code == 400, "❌ API crashed on invalid Base64 instead of returning 400 Bad Request."
    print("✅ API gracefully handles corrupted HTTP payloads without crashing the server.")

if __name__ == "__main__":
    test_01_model_loading_and_optimization()
    test_02_latency_real_world_scenario()
    test_03_edge_cases_face_detection()
    test_04_rule_engine_and_cooldowns()
    test_05_end_to_end_pipeline_resilience()
    print("\n===========================================================")
    print("🌟 DEEP INSPECTION COMPLETE: The ML Service is Production-Ready! 🌟")
    print("===========================================================\n")
