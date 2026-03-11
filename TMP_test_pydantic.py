import asyncio
from datetime import date
from pydantic import BaseModel, Field, ValidationError

class Transaction(BaseModel):
    date: date
    description: str
    invoice_number: str | None = Field(None, pattern=r'^T[0-9]{13}$')

try:
    tx = Transaction(
        date=date.today(),
        description="test",
        invoice_number=""
    )
    print("Success:", tx)
except ValidationError as e:
    print("ValidationError:", e)
    
try:
    tx2 = Transaction(
        date=date.today(),
        description="test",
        invoice_number=None
    )
    print("Success:", tx2)
except ValidationError as e:
    print("ValidationError:", e)
