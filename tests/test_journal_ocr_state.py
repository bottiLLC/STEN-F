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

import pytest
from unittest.mock import patch
from app.ui.view_models.journal.ocr import JournalOCRState
from app.ui.view_models.journal.form import JournalFormState
from app.domain.models.receipt import ReceiptData


@pytest.mark.asyncio
async def test_ocr_state_clear_upload_state():
    """Test clear_upload_state resets internal uploaded file variables."""
    state = JournalOCRState()
    state._uploaded_file_data = b"dummy"
    state._uploaded_filename = "receipt.pdf"

    res = await state.clear_upload_state()
    assert state._uploaded_file_data is None
    assert state._uploaded_filename is None
    assert res is not None


@pytest.mark.asyncio
async def test_ocr_state_apply_ocr_result(container):
    """Test _apply_ocr_result populates JournalFormState with extracted fields."""
    ocr_state = JournalOCRState()
    form_state = JournalFormState()

    receipt_data = ReceiptData(
        transaction_date="2026-05-15",
        merchant_name="OCR Merchant",
        description="タクシー代（移動）",
        invoice_registration_number="T1234567890123",
        total_amount_incl_tax=3500,
        inferred_debit_account_id="1",
        inferred_credit_account_id="2",
        needs_manual_review=False,
    )

    async def mock_get_state(self_ref, state_cls):
        if state_cls == JournalFormState:
            return form_state
        return self_ref

    with patch.object(JournalOCRState, "get_state", mock_get_state):
        events = []
        async for ev in ocr_state._apply_ocr_result(receipt_data):
            events.append(ev)

    assert form_state.transaction_date == "2026-05-15"
    assert form_state.counterparty == "OCR Merchant"
    assert form_state.description == "タクシー代（移動）"
    assert form_state.invoice_number == "T1234567890123"
    assert len(form_state.lines) == 2
    assert form_state.lines[0]["account_id"] == "1"
    assert form_state.lines[0]["debit"] == 3500
    assert form_state.lines[1]["account_id"] == "2"
    assert form_state.lines[1]["credit"] == 3500
