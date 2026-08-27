from pydantic import BaseModel
from typing import Optional

class FrameRequest(BaseModel):
    attempt_id: str
    frame_base64: str
    timestamp: float

class FrameAnalysisResponse(BaseModel):
    face_detected: bool
    face_count: int
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    confidence: float
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
