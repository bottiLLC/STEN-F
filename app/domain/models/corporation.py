from typing import Optional
from datetime import date
from pydantic import BaseModel, ConfigDict, Field

class Corporation(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    name: str = Field(..., description="法人名")
    address: Optional[str] = Field(None, description="本店所在地")
    representative_title: Optional[str] = Field(None, description="代表役職名")
    representative_name: Optional[str] = Field(None, description="代表者氏名")
    
    model_config = ConfigDict(from_attributes=True)
