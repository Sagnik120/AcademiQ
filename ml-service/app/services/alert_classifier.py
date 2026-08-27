import time
from typing import Tuple, Optional, Dict
from pydantic import BaseModel

# Memory store for cooldowns: attempt_id -> {alert_type -> timestamp}
# In production with multiple workers, use Redis. For a simple demo microservice, in-memory is fine.
_cooldown_memory: Dict[str, Dict[str, float]] = {}
COOLDOWN_SECONDS = 3.0

# Track how long a face has been absent for the 'absent_extended' alert
_absence_memory: Dict[str, float] = {}

def get_alert_for_frame(attempt_id: str, face_count: int, yaw: Optional[float], pitch: Optional[float], current_time: float) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (alert_type, severity) based on thresholds.
    Applies a 3-second cooldown per alert type per attempt.
    """
    alert_type = None
    severity = None
    
    # Initialize memory
    if attempt_id not in _cooldown_memory:
        _cooldown_memory[attempt_id] = {}
        
    if face_count == 0:
        # Handle Absence
        if attempt_id not in _absence_memory:
            _absence_memory[attempt_id] = current_time
            
        absence_duration = current_time - _absence_memory[attempt_id]
        if absence_duration > 3.0:
            alert_type, severity = "absent_extended", "critical"
        elif absence_duration > 1.0:
            alert_type, severity = "absent", "high"
    else:
        # Face is present, clear absence memory
        if attempt_id in _absence_memory:
            del _absence_memory[attempt_id]
            
        if face_count >= 2:
            alert_type, severity = "multiple_face", "critical"
        elif yaw is not None and pitch is not None:
            # Check Head Pose (Only if 1 face detected)
            if abs(yaw) > 30:
                alert_type, severity = "head_turn_severe", "high"
            elif abs(yaw) > 15:
                alert_type, severity = "head_turn_mild", "medium"
            elif pitch < -20:
                alert_type, severity = "head_down", "medium"
                
    # Cooldown Logic
    if alert_type:
        last_fired = _cooldown_memory[attempt_id].get(alert_type, 0.0)
        if current_time - last_fired < COOLDOWN_SECONDS:
            # Suppress alert due to cooldown
            return None, None
        else:
            # Fire alert and update cooldown
            _cooldown_memory[attempt_id][alert_type] = current_time
            return alert_type, severity
            
    return None, None
