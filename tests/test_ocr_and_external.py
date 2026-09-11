# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from datetime import date
import io
from PIL import Image
import pytest
from google.genai.errors import APIError
from app.ai_ocr_service import GeminiOCRService, OpenAIOCRService
from app.domain_contracts import (
    AccountType,
    Corporation,
    FinancialReport,
    FinancialSection,
    FiscalYear,
    ReceiptData,
    TaxBreakdownItem,
    TrialBalanceRow,
)
from app.external_services import PDFService


def _create_dummy_image() -> bytes:
    """Generate minimal PNG image byte array for OCR mocking."""
    img = Image.new("RGB", (60, 60), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- 1. OCR Service Extraction & Mocking Tests ---
@pytest.mark.asyncio
async def test_ocr_service_validations_and_aliases(container):
    """Verify OCR input boundary validation and backward compatibility aliases."""
    service = GeminiOCRService()
    assert OpenAIOCRService is GeminiOCRService

    with pytest.raises(ValueError, match="アップロードされたファイルが空です"):
        await service.extract_receipt_data(b"", "png")

    with pytest.raises(ValueError, match="サポートされていないファイル形式です"):
        await service.extract_receipt_data(b"dummy", "exe")


@pytest.mark.asyncio
async def test_ocr_service_extraction_with_mock(container, mocker):
    """Verify Gemini API JSON response parsing and counterparty matching."""
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    mock_resp = mocker.MagicMock()
    mock_resp.text = '{"merchant_name": " ㈱テストストア ", "transaction_date": "2026-05-10", "total_amount_incl_tax": 4800, "invoice_registration_number": "T1234567890123"}'
    mocker.patch("google.genai.models.Models.generate_content", return_value=mock_resp)

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-golden-key"
        await ms.save_system_settings(settings_obj)

    receipt = await service.extract_receipt_data(dummy_img, "png")
    assert receipt.merchant_name == "(株)テストストア"
    assert receipt.transaction_date == "2026-05-10"
    assert receipt.total_amount_incl_tax == 4800
    assert receipt.invoice_registration_number == "T1234567890123"


def test_ocr_api_error_message_formatting():
    """Verify Gemini API error codes format to polite Japanese guidance strings."""
    service = GeminiOCRService()

    err_key = APIError(
        400,
        {
            "error": {
                "message": "API_KEY_INVALID: API key not valid. Please pass a valid API key."
            }
        },
    )
    msg_key = service._format_api_error_message(err_key)
    assert "Gemini API キーが無効または未設定です" in msg_key
    assert "AI・システム設定" in msg_key

    err_429 = APIError(
        429, {"error": {"message": "RESOURCE_EXHAUSTED: quota exceeded"}}
    )
    assert (
        "利用上限（クォータ／レート制限）に達しました"
        in service._format_api_error_message(err_429)
    )

    err_403 = APIError(403, {"error": {"message": "PERMISSION_DENIED"}})
    assert "アクセス権限が拒否されました" in service._format_api_error_message(err_403)

    err_500 = APIError(500, {"error": {"message": "INTERNAL: backend failure"}})
    assert (
        "Google Gemini サーバー側で一時的な障害が発生しています"
        in service._format_api_error_message(err_500)
    )


# --- 2. OCR Structural Validation Tests ---
class TestOCRStructuralValidation:
    def setup_method(self):
        self.service = GeminiOCRService()

    def test_valid_receipt(self):
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=100, amount_excl_tax=1000)
            ],
            total_tax_amount=100,
            total_amount_excl_tax=1000,
            total_amount_incl_tax=1100,
            transaction_date="2023-10-01",
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is False
        assert validated.error_message is None

    def test_tax_math_error(self):
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=50, amount_excl_tax=1000)
            ],
            total_amount_incl_tax=1050,
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "消費税計算不整合" in validated.error_message

    def test_total_tax_mismatch(self):
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=100, amount_excl_tax=1000)
            ],
            total_tax_amount=200,
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "消費税合計不整合" in validated.error_message

    def test_grand_total_mismatch(self):
        data = ReceiptData(
            total_amount_excl_tax=1000, total_tax_amount=100, total_amount_incl_tax=1200
        )
        validated = self.service._validate_receipt(data)
        assert validated.needs_manual_review is True
        assert "支払合計不整合" in validated.error_message

    def test_invalid_date_format(self):
        data = ReceiptData(transaction_date="2023/10/01")
        validated = self.service._validate_receipt(data)
        assert validated.transaction_date is None
        assert validated.needs_manual_review is True
        assert "日付フォーマット不正" in validated.error_message

    def test_invoice_number_cleaning_and_validation(self):
        data_clean = ReceiptData(invoice_registration_number="T1234567890123")
        assert self.service._validate_receipt(data_clean).needs_manual_review is False

        data_dirty = ReceiptData(
            invoice_registration_number="登録番号: T1234567890123 です"
        )
        validated_dirty = self.service._validate_receipt(data_dirty)
        assert validated_dirty.needs_manual_review is False
        assert validated_dirty.invoice_registration_number == "T1234567890123"

        data_invalid = ReceiptData(invoice_registration_number="12345")
        assert (
            "インボイス番号の形式が不正です"
            in self.service._validate_receipt(data_invalid).error_message
        )


# --- 3. PDF Financial Report Generation & Dencho Compliance Tests ---
def test_pdf_service_generation_and_dencho():
    """Verify ReportLab rendering of financial report PDF and statutory compliance."""
    corp = Corporation(
        name="合同会社テスト",
        address="東京都渋谷区1-2-3",
        representative_title="代表社員",
        representative_name="山田 太郎",
    )
    fy = FiscalYear(
        id=1,
        name="第1期",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        period_number=1,
        status="OPEN",
    )

    def make_sec(title: str, t: AccountType) -> FinancialSection:
        return FinancialSection(
            title=title,
            rows=[
                TrialBalanceRow(
                    account_id=1,
                    account_code="1110",
                    account_name="現金",
                    account_type=t,
                    debit_total=100,
                    credit_total=0,
                    balance=100,
                    debit_balance=100,
                    credit_balance=0,
                )
            ],
            total=100,
        )

    rpt = FinancialReport(
        fiscal_year=fy,
        current_assets=make_sec("流動資産", AccountType.CURRENT_ASSET),
        fixed_assets=make_sec("固定資産", AccountType.FIXED_ASSET),
        deferred_assets=make_sec("繰延資産", AccountType.DEFERRED_ASSET),
        current_liabilities=make_sec("流動負債", AccountType.CURRENT_LIABILITY),
        fixed_liabilities=make_sec("固定負債", AccountType.FIXED_LIABILITY),
        equity=make_sec("純資産", AccountType.EQUITY),
        revenue=make_sec("売上高", AccountType.REVENUE),
        cost_of_sales=make_sec("売上原価", AccountType.COST_OF_SALES),
        sga=make_sec("販売管理費", AccountType.SGA),
        non_op_income=make_sec("営業外収益", AccountType.NON_OPERATING_INCOME),
        non_op_expense=make_sec("営業外費用", AccountType.NON_OPERATING_EXPENSE),
        extra_income=make_sec("特別利益", AccountType.EXTRAORDINARY_INCOME),
        extra_loss=make_sec("特別損失", AccountType.EXTRAORDINARY_LOSS),
        total_assets=300,
        total_liabilities=200,
        total_equity=100,
        gross_profit=0,
        operating_income=0,
        ordinary_income=0,
        income_before_tax=0,
        net_income=0,
    )

    pdf_bytes = PDFService.generate_annual_report(
        corp=corp,
        rpt=rpt,
        fiscal_year=fy,
        report_date=date(2026, 12, 31),
        audit_date=date(2026, 12, 31),
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
