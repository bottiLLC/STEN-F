from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class Counterparty(BaseModel):
    id: Optional[int] = None
    name: str
    name_kana: Optional[str] = None
    invoice_number: Optional[str] = Field(None, description="T番号 (T + 13 digits)")
    debit_account_id: Optional[int] = None
    credit_account_id: Optional[int] = None
    description_template: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
