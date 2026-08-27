import numpy as np
from app.services.face_detector import detect_faces

def test_no_face_detected():
    # Create a blank black image (no faces)
    img_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
    
    face_count, cropped_face = detect_faces(img_bgr)
    
    assert face_count == 0
    assert cropped_face is None

def test_random_noise_image():
    # Create random noise (still no valid face)
    img_bgr = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    face_count, cropped_face = detect_faces(img_bgr)
    
    assert face_count == 0
    assert cropped_face is None
