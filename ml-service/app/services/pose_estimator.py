import os
import cv2
import numpy as np
import onnxruntime as ort
from typing import Tuple

MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(os.path.dirname(__file__), "..", "model", "head_pose.onnx"))

# Load model globally to avoid reloading on every request
session = None
try:
    if os.path.exists(MODEL_PATH):
        session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
    else:
        print(f"WARNING: Model not found at {MODEL_PATH}. Inference will return (0,0,0). Please run the Colab training notebook.")
except Exception as e:
    print(f"Error loading ONNX model: {e}")

def estimate_pose(face_bgr: np.ndarray) -> Tuple[float, float, float]:
    """
    Runs ONNX inference on a cropped face.
    Returns: yaw, pitch, roll in degrees.
    """
    if session is None:
        return 0.0, 0.0, 0.0
        
    # Preprocess image for MobileNetV2 / ResNet18 (224x224, RGB, normalized)
    face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
    face_resized = cv2.resize(face_rgb, (224, 224))
    
    # Normalize with ImageNet stats
    img_array = face_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img_array = (img_array - mean) / std
    
    # HWC to CHW format
    img_array = np.transpose(img_array, (2, 0, 1))
    
    # Add batch dimension
    input_tensor = np.expand_dims(img_array, axis=0)
    
    # Run inference
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    
    # Assuming output is shape (1, 3) [yaw, pitch, roll]
    yaw, pitch, roll = outputs[0][0]
    
    return float(yaw), float(pitch), float(roll)
