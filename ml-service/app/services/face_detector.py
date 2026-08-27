import cv2
import numpy as np
import os
import urllib.request
from typing import Tuple, Optional

# Download the Haar cascade XML directly if it doesn't exist locally
# This bypasses issues with OpenCV 5.0+ where cv2.data.haarcascades might be broken
cascade_path = os.path.join(os.path.dirname(__file__), 'haarcascade_frontalface_default.xml')

if not os.path.exists(cascade_path):
    url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
    urllib.request.urlretrieve(url, cascade_path)

face_cascade = cv2.CascadeClassifier(cascade_path)

def detect_faces(image_bgr: np.ndarray) -> Tuple[int, Optional[np.ndarray]]:
    """
    Detects faces in a BGR image using OpenCV Haar Cascades.
    Returns:
        face_count: integer (0, 1, 2+)
        cropped_face: BGR image of the primary face (if exactly 1 detected)
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    
    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    face_count = len(faces)
    
    if face_count != 1:
        # If multiple faces or no face, just alert, no need to crop for pose estimation
        return face_count, None
        
    # Get bounding box of the single face
    (x, y, w, h) = faces[0]
    
    # Add padding (20%)
    padding_x = int(w * 0.2)
    padding_y = int(h * 0.2)
    
    img_h, img_w, _ = image_bgr.shape
    
    x_min = max(0, x - padding_x)
    y_min = max(0, y - padding_y)
    x_max = min(img_w, x + w + padding_x)
    y_max = min(img_h, y + h + padding_y)
    
    cropped_face = image_bgr[y_min:y_max, x_min:x_max]
    return face_count, cropped_face
