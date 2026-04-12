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

from app.infrastructure.external.ocr_service import GoogleOCRService
from app.domain.models.receipt import ReceiptData, TaxBreakdownItem

class TestOCRValidation:
    
    def setup_method(self):
        self.service = GoogleOCRService()

    def test_valid_receipt(self):
        # 1000 + 100 (10%) = 1100
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=100, amount_excl_tax=1000)
            ],
            total_tax_amount=100,
            total_amount_excl_tax=1000,
            total_amount_incl_tax=1100,
            transaction_date="2023-10-01"
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False
        assert validated.error_message is None

    def test_tax_math_error(self):
        # 1000 * 0.10 = 100, but provided 50
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=50, amount_excl_tax=1000)
            ],
            total_amount_incl_tax=1050
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "消費税計算不整合" in validated.error_message

    def test_total_tax_mismatch(self):
        # Breakdown sum = 100, but total_tax_amount = 200
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=100, amount_excl_tax=1000)
            ],
            total_tax_amount=200
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "消費税合計不整合" in validated.error_message

    def test_grand_total_mismatch(self):
        # 1000 + 100 = 1100, but total_incl = 1200
        data = ReceiptData(
            total_amount_excl_tax=1000,
            total_tax_amount=100,
            total_amount_incl_tax=1200
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "支払合計不整合" in validated.error_message

    def test_invalid_date(self):
        data = ReceiptData(transaction_date="2023/10/01") # Not ISO
        validated = self.service._validate_receipt(data)
        assert validated.transaction_date is None
        assert validated.needs_manual_review is True
        assert "日付フォーマット不正" in validated.error_message

    def test_invoice_number_validation_clean(self):
        # Valid format
        data = ReceiptData(invoice_registration_number="T1234567890123")
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False

    def test_invoice_number_validation_dirty(self):
        # Dirty format (Auto-extraction)
        data = ReceiptData(invoice_registration_number="登録番号: T1234567890123 です")
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False
        assert validated.invoice_registration_number == "T1234567890123"

    def test_invoice_number_validation_invalid(self):
        # Invalid format
        data = ReceiptData(invoice_registration_number="12345")
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "インボイス番号の形式が不正です" in validated.error_message
