from pydantic import BaseModel
from typing import Optional

# Pydantic config - stores app settings and API keys
class Config(BaseModel):
    data_dir: str = "data"
    rlive_api_key: Optional[str] = None
    user_agent: str = "ACI-Research-Toolkit/0.1 (contact: you@example.com)"
