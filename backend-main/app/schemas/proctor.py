from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class StartProctorSessionRequest(BaseModel):
    attempt_id: str

class ProctorSessionResponse(BaseModel):
    session_id: str
    attempt_id: str
    initial_trust_score: float
    final_trust_score: Optional[float] = None
    is_flagged: bool
    total_alerts: int = 0
    started_at: datetime

class FrameAnalyzeRequest(BaseModel):
    frame_base64: str = Field(..., description="Base64-encoded webcam frame")
    timestamp: Optional[float] = None

class FrameAnalyzeResponse(BaseModel):
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[float] = 1.0
    current_trust_score: float
    is_flagged: bool

class TrustScoreResponse(BaseModel):
    attempt_id: str
    current_trust_score: float
    is_flagged: bool
    total_alerts: int

class EndProctorSessionResponse(BaseModel):
    session_id: str
    attempt_id: str
    final_trust_score: float
    is_flagged: bool
    total_alerts: int
    message: str
