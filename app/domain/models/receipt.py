from typing import Optional
from pydantic import BaseModel, ConfigDict

class ReceiptData(BaseModel):
    """
    Domain model representing extracted receipt data.
    """
    vendor_name: Optional[str] = None
    date: Optional[str] = None
    account_item: Optional[str] = None
    tax_8_base: Optional[int] = None
    tax_8_amount: Optional[int] = None
    tax_10_base: Optional[int] = None
    tax_10_amount: Optional[int] = None
    total_amount: Optional[int] = None
    invoice_number: Optional[str] = None
    confidence_score: float = 0.0
    needs_manual_review: bool = False
    error_message: Optional[str] = None

    model_config = ConfigDict(extra='ignore')
