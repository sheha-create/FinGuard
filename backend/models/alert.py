from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class AlertBase(BaseModel):
    pattern: str  # loop, fan_out, fan_in, rapid_passthrough
    involved_accounts: List[str]
    tx_ids: List[str]
    risk_score: float
    description: Optional[str] = None


class AlertCreate(AlertBase):
    pass


class Alert(AlertBase):
    id: str = Field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:12]}")
    status: str = "open"  # open, resolved_false_positive, confirmed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True
