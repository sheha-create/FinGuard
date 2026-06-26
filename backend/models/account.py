from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class AccountBase(BaseModel):
    kyc_tier: str = "low"
    account_type: str = "personal"


class AccountCreate(AccountBase):
    id: Optional[str] = None


class Account(AccountBase):
    id: str = Field(default_factory=lambda: f"acct_{uuid.uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    risk_velocity_matrix: Dict[str, Any] = {}
    transaction_count: int = 0
    total_sent: float = 0.0
    total_received: float = 0.0

    class Config:
        from_attributes = True
