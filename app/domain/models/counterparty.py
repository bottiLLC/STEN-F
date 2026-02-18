from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field
from .account import AccountType

class Counterparty(BaseModel):
    id: Optional[int] = None
    name: str
    name_kana: Optional[str] = None
    invoice_number: Optional[str] = Field(None, description="T番号 (T + 13 digits)")
    invoice_number: Optional[str] = Field(None, description="T番号 (T + 13 digits)")
    default_account_id: Optional[int] = None
    


    model_config = ConfigDict(from_attributes=True)
