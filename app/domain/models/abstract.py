from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class Abstract(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    account_id: int = Field(..., description="紐づく勘定科目ID")
    text: str = Field(..., description="摘要内容")
    
    # Optional denormalized field
    account_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')
