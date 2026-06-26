from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class TransactionBase(BaseModel):
    sender: str
    receiver: str
    amount: float = Field(..., gt=0)
    timestamp: Optional[datetime] = None


class TransactionCreate(TransactionBase):
    pass


class Transaction(TransactionBase):
    id: str = Field(default_factory=lambda: f"tx_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ai_score: float = 0.0
    graph_score: float = 0.0
    final_risk: float = 0.0
    flagged: bool = False
    features: dict = {}

    class Config:
        from_attributes = True
