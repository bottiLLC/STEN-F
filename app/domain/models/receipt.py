# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class TaxBreakdownItem(BaseModel):
    tax_rate: str
    tax_amount: Optional[int] = None
    amount_excl_tax: Optional[int] = None
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ReceiptData(BaseModel):
    """
    Domain model representing extracted receipt data.
    """

    merchant_name: Optional[str] = None
    transaction_date: Optional[str] = None
    total_amount_incl_tax: Optional[int] = None
    invoice_registration_number: Optional[str] = None
    tax_breakdown: Optional[List[TaxBreakdownItem]] = None
    total_tax_amount: Optional[int] = None
    total_amount_excl_tax: Optional[int] = None

    # Internal fields for validation/UI
    confidence_score: float = 0.0
    needs_manual_review: bool = False
    is_registered_merchant: bool = False
    error_message: Optional[str] = None

    # Hybrid Matching fields
    inferred_debit_account_id: Optional[str] = None
    inferred_credit_account_id: Optional[str] = None
    description: Optional[str] = None
    is_dictionary_matched: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")
