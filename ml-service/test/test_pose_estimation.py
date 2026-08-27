import numpy as np
import os
from app.services.pose_estimator import estimate_pose, MODEL_PATH

def test_pose_estimation_shape():
    # Provide a dummy cropped face image
    face_bgr = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    
    yaw, pitch, roll = estimate_pose(face_bgr)
    
    assert isinstance(yaw, float)
    assert isinstance(pitch, float)
    assert isinstance(roll, float)

def test_missing_model_fallback():
    # If the model doesn't exist, it should return (0.0, 0.0, 0.0) safely
    face_bgr = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    
    yaw, pitch, roll = estimate_pose(face_bgr)
    
    if not os.path.exists(MODEL_PATH):
        assert yaw == 0.0
        assert pitch == 0.0
        assert roll == 0.0
