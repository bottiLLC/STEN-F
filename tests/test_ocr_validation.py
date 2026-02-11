
import pytest
from app.infrastructure.external.ocr_service import GoogleOCRService
from app.domain.models.receipt import ReceiptData

class TestOCRValidation:
    
    def setup_method(self):
        self.service = GoogleOCRService()

    def test_valid_receipt(self):
        data = ReceiptData(
            tax_8_base=1000, tax_8_amount=80,
            tax_10_base=2000, tax_10_amount=200,
            total_amount=3280,
            date="2023-10-01"
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False
        assert validated.error_message is None

    def test_tax_math_error(self):
        # 1000 * 0.08 = 80, but provided 50
        data = ReceiptData(
            tax_8_base=1000, tax_8_amount=50,
            total_amount=1050
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "8% Tax Mismatch" in validated.error_message

    def test_total_math_error(self):
        # 1000 + 80 = 1080, but total is 2000
        data = ReceiptData(
            tax_8_base=1000, tax_8_amount=80,
            total_amount=2000
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "Total Mismatch" in validated.error_message

    def test_invalid_date(self):
        data = ReceiptData(date="2023/10/01") # Not ISO
        validated = self.service._validate_receipt(data)
        assert validated.date is None
        assert validated.needs_manual_review is True
        assert "Invalid Date Format" in validated.error_message

    def test_rounding_tolerance(self):
        # 1008 * 0.08 = 80.64 -> 81 (Round up)
        # 1008 + 81 = 1089
        data = ReceiptData(
            tax_8_base=1008, tax_8_amount=81,
            total_amount=1089,
            date="2023-10-01"
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False

    def test_account_item_validation(self):
        # "Foo" is not in the list
        data = ReceiptData(account_item="Foo")
        account_list = ["Bar", "Baz"]
        validated = self.service._validate_receipt(data, account_list)
        assert validated.needs_manual_review is True
        assert "Account 'Foo' not in master list" in validated.error_message

        # "Bar" is in the list
        data2 = ReceiptData(account_item="Bar")
        validated2 = self.service._validate_receipt(data2, account_list)
        assert validated2.needs_manual_review is False

    def test_invoice_number_validation(self):
        # Invalid format
        data = ReceiptData(invoice_number="12345")
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "Invalid Invoice Num" in validated.error_message

        # Valid format
        data2 = ReceiptData(invoice_number="T1234567890123")
        validated2 = self.service._validate_receipt(data2)
        assert validated2.needs_manual_review is False
