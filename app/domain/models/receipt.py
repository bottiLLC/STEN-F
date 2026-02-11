from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class TaxBreakdownItem(BaseModel):
    tax_rate: str
    tax_amount: int
    amount_excl_tax: int

class ReceiptData(BaseModel):
    """
    Domain model representing extracted receipt data.
    """
    merchant_name: Optional[str] = None
    transaction_date: Optional[str] = None
    total_amount_incl_tax: Optional[int] = None
    invoice_registration_number: Optional[str] = None
    tax_breakdown: List[TaxBreakdownItem] = []
    total_tax_amount: Optional[int] = None
    total_amount_excl_tax: Optional[int] = None
    
    # Internal fields for validation/UI
    confidence_score: float = 0.0
    needs_manual_review: bool = False
    error_message: Optional[str] = None

    model_config = ConfigDict(extra='ignore')
