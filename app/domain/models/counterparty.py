from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field
from .account import AccountType

class Counterparty(BaseModel):
    id: Optional[int] = None
    name: str
    name_kana: Optional[str] = None
    invoice_number: Optional[str] = Field(None, description="T番号 (T + 13 digits)")
    default_account_type: Optional[str] = None
    
    @computed_field
    def default_account_type_label(self) -> str:
        if not self.default_account_type:
            return ""
        try:
             # AccountType.label works if we cast string to Enum
             return AccountType(self.default_account_type).label
        except:
             return self.default_account_type

    model_config = ConfigDict(from_attributes=True)
