from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

class TransactionLine(BaseModel):
    id: Optional[int] = None
    account_id: int
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    
    # Optional denormalized fields for domain convenience, 
    # though strict composition prefers fetching Account object.
    # We keep it minimal for the entity.
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def amount(self) -> int:
        return self.debit if self.debit > 0 else self.credit

class Transaction(BaseModel):
    id: Optional[int] = None
    date: date
    description: str
    lines: List[TransactionLine] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode='after')
    def check_balance(self) -> 'Transaction':
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"Unbalanced Transaction: Debit({total_debit}) != Credit({total_credit})")
        return self
