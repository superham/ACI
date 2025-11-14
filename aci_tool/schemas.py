from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class Claim(BaseModel):
    source: str
    group: str
    group_alias: Optional[str] = None
    victim_legal_name: Optional[str] = None
    victim_domain: Optional[str] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    claim_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    publish_date: Optional[datetime] = None
    post_url: Optional[str] = None
    extra: Dict[str, Any] = {}

class Payment(BaseModel):
    source: str
    family: Optional[str] = None
    group: Optional[str] = None
    address: str
    first_tx_at: Optional[datetime] = None
    amount_usd: Optional[float] = None
    tx_count: Optional[int] = None
    extra: Dict[str, Any] = {}

class Confirmation(BaseModel):
    source: str
    victim_legal_name: Optional[str] = None
    victim_domain: Optional[str] = None
    notice_date: Optional[datetime] = None
    incident_date: Optional[datetime] = None
    ransomware: Optional[bool] = None
    details_url: Optional[str] = None
    extra: Dict[str, Any] = {}

# NOTE: These are specific for ransomware.live pro and ransomwwhere api responses, will need to be generalized