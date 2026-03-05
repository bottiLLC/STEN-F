from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

class TransactionLine(BaseModel):
    id: Optional[int] = None
    account_id: int
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    
    # Optional loaded relationship
    account: Optional['Account'] = None
    
    # Optional denormalized fields for domain convenience, 
    # though strict composition prefers fetching Account object.
    # We keep it minimal for the entity.
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
    
    @property
    def amount(self) -> int:
        return self.debit if self.debit > 0 else self.credit

class Transaction(BaseModel):
    id: Optional[int] = None
    date: date
    description: str
    lines: List[TransactionLine] = Field(default_factory=list)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    counterparty: Optional[str] = None
    invoice_number: Optional[str] = None
    evidence_path: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
    
    @model_validator(mode='after')
    def check_balance(self) -> 'Transaction':
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"Unbalanced Transaction: Debit({total_debit}) != Credit({total_credit})")
        return self

# Fix for forward reference 'Account'
from domain.models.account import Account
TransactionLine.model_rebuild()
Transaction.model_rebuild()
