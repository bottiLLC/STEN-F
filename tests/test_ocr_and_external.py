# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date
import io
from PIL import Image
import pytest
from pytest_mock import MockerFixture
from google.genai.errors import APIError

from app.ai_ocr_service import GeminiOCRService, OpenAIOCRService
from app.application_services import Container
from app.domain_contracts import (
    AccountType,
    Corporation,
    Counterparty,
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
async def test_ocr_service_validations_and_aliases(container: Container) -> None:
    """Verify OCR input boundary validation and backward compatibility aliases."""
    # Arrange
    service = GeminiOCRService()

    # Assert alias
    assert OpenAIOCRService is GeminiOCRService

    # Act & Assert
    with pytest.raises(ValueError, match="アップロードされたファイルが空です"):
        await service.extract_receipt_data(b"", "png")

    with pytest.raises(ValueError, match="サポートされていないファイル形式です"):
        await service.extract_receipt_data(b"dummy", "exe")


@pytest.mark.asyncio
async def test_ocr_service_extraction_without_api_key_raises_value_error(
    container: Container,
) -> None:
    """Ensure OCR extraction fails with actionable error message when AI API key is not configured."""
    # Arrange
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = ""
        await ms.save_system_settings(settings_obj)

    # Act & Assert
    with pytest.raises(ValueError, match="Gemini API キーが無効または未設定です"):
        await service.extract_receipt_data(dummy_img, "png")


@pytest.mark.asyncio
async def test_ocr_service_extraction_with_mock(
    container: Container, mocker: MockerFixture
) -> None:
    """Verify Gemini API JSON response parsing, mocking assertions, and data contracts."""
    # Arrange
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    mock_resp = mocker.MagicMock()
    mock_resp.text = '{"merchant_name": " ㈱テストストア ", "transaction_date": "2026-05-10", "total_amount_incl_tax": 4800, "invoice_registration_number": "T1234567890123"}'
    mock_generate = mocker.patch(
        "google.genai.models.Models.generate_content", return_value=mock_resp
    )

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-golden-key"
        await ms.save_system_settings(settings_obj)

    # Act
    receipt = await service.extract_receipt_data(dummy_img, "png")

    # Assert
    assert mock_generate.call_count == 2
    assert receipt.merchant_name == "(株)テストストア"
    assert receipt.transaction_date == "2026-05-10"
    assert receipt.total_amount_incl_tax == 4800
    assert receipt.invoice_registration_number == "T1234567890123"


@pytest.mark.asyncio
async def test_ocr_service_extraction_parses_markdown_fenced_json(
    container: Container, mocker: MockerFixture
) -> None:
    """Verify JSON block extraction when LLM returns markdown fenced code."""
    # Arrange
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    mock_resp = mocker.MagicMock()
    mock_resp.text = '```json\n{"merchant_name": "マークダウン商店", "transaction_date": "2026-06-01", "total_amount_incl_tax": 3300}\n```'
    mock_generate = mocker.patch(
        "google.genai.models.Models.generate_content", return_value=mock_resp
    )

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-golden-key"
        await ms.save_system_settings(settings_obj)

    # Act
    receipt = await service.extract_receipt_data(dummy_img, "png")

    # Assert
    assert mock_generate.call_count == 2
    assert receipt.merchant_name == "マークダウン商店"
    assert receipt.total_amount_incl_tax == 3300


@pytest.mark.parametrize(
    ("status_code", "error_payload", "expected_keyword"),
    [
        (
            400,
            {"error": {"message": "API_KEY_INVALID: API key not valid."}},
            "Gemini API キーが無効または未設定です",
        ),
        (
            403,
            {"error": {"message": "PERMISSION_DENIED"}},
            "アクセス権限が拒否されました",
        ),
        (
            429,
            {"error": {"message": "RESOURCE_EXHAUSTED: quota exceeded"}},
            "利用上限（クォータ／レート制限）に達しました",
        ),
        (
            500,
            {"error": {"message": "INTERNAL: backend failure"}},
            "Google Gemini サーバー側で一時的な障害が発生しています",
        ),
        (
            503,
            {"error": {"message": "UNAVAILABLE"}},
            "Google Gemini サーバー側で一時的な障害が発生しています",
        ),
    ],
)
def test_ocr_api_error_message_formatting_per_status_code(
    status_code: int, error_payload: dict[str, object], expected_keyword: str
) -> None:
    """Verify Gemini API error codes format to accurate, user-friendly Japanese messages."""
    # Arrange
    service = GeminiOCRService()
    api_err = APIError(status_code, error_payload)

    # Act
    msg = service._format_api_error_message(api_err)

    # Assert
    assert expected_keyword in msg


def test_ocr_api_error_message_formatting_unrecognized_error() -> None:
    """Verify unrecognized APIError formats with standard error prefix and code."""
    # Arrange
    service = GeminiOCRService()
    generic_err = APIError(418, {"error": {"message": "I'm a teapot"}})

    # Act
    msg = service._format_api_error_message(generic_err)

    # Assert
    assert "Gemini API エラー (Code: 418)" in msg
    assert "I'm a teapot" in msg


# --- 2. OCR Structural Validation Tests ---
class TestOCRStructuralValidation:
    """Test suite ensuring fail-fast semantic validation of parsed receipts."""

    def setup_method(self) -> None:
        self.service = GeminiOCRService()

    def test_valid_receipt_passes_without_manual_review(self) -> None:
        # Arrange
        data = ReceiptData(
            tax_breakdown=[
                TaxBreakdownItem(tax_rate="10%", tax_amount=100, amount_excl_tax=1000)
            ],
            total_tax_amount=100,
            total_amount_excl_tax=1000,
            total_amount_incl_tax=1100,
            transaction_date="2023-10-01",
        )

        # Act
        validated = self.service._validate_receipt(data)

        # Assert
        assert validated.needs_manual_review is False
        assert validated.error_message is None

    @pytest.mark.parametrize(
        ("invalid_data", "expected_err"),
        [
            (
                ReceiptData(
                    tax_breakdown=[
                        TaxBreakdownItem(
                            tax_rate="10%", tax_amount=50, amount_excl_tax=1000
                        )
                    ],
                    total_amount_incl_tax=1050,
                ),
                "消費税計算不整合",
            ),
            (
                ReceiptData(
                    tax_breakdown=[
                        TaxBreakdownItem(
                            tax_rate="10%", tax_amount=100, amount_excl_tax=1000
                        )
                    ],
                    total_tax_amount=200,
                ),
                "消費税合計不整合",
            ),
            (
                ReceiptData(
                    total_amount_excl_tax=1000,
                    total_tax_amount=100,
                    total_amount_incl_tax=1200,
                ),
                "支払合計不整合",
            ),
            (
                ReceiptData(transaction_date="2023/10/01"),
                "日付フォーマット不正",
            ),
            (
                ReceiptData(invoice_registration_number="12345"),
                "インボイス番号の形式が不正です",
            ),
        ],
    )
    def test_structural_validation_rules_flag_manual_review(
        self, invalid_data: ReceiptData, expected_err: str
    ) -> None:
        """Verify individual validation anomalies flag needs_manual_review and set error message."""
        # Act
        validated = self.service._validate_receipt(invalid_data)

        # Assert
        assert validated.needs_manual_review is True
        assert validated.error_message is not None
        assert expected_err in validated.error_message

    def test_invoice_number_cleaning_and_whitespace_removal(self) -> None:
        """Verify that dirty invoice number strings are cleansed to valid T-numbers."""
        # Arrange
        data_dirty = ReceiptData(
            invoice_registration_number="登録番号: T1234567890123 です"
        )

        # Act
        validated_dirty = self.service._validate_receipt(data_dirty)

        # Assert
        assert validated_dirty.needs_manual_review is False
        assert validated_dirty.invoice_registration_number == "T1234567890123"


# --- 3. PDF Financial Report Generation & Dencho Compliance Tests ---
def test_pdf_service_generation_with_standard_profit_report() -> None:
    """Verify ReportLab rendering of financial report PDF with positive net income."""
    # Arrange
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

    def make_sec(title: str, t: AccountType, amount: int = 100) -> FinancialSection:
        return FinancialSection(
            title=title,
            rows=[
                TrialBalanceRow(
                    account_id=1,
                    account_code="1110",
                    account_name="現金",
                    account_type=t,
                    debit_total=amount,
                    credit_total=0,
                    balance=amount,
                    debit_balance=amount,
                    credit_balance=0,
                )
            ],
            total=amount,
        )

    rpt = FinancialReport(
        fiscal_year=fy,
        current_assets=make_sec("流動資産", AccountType.CURRENT_ASSET, 300),
        fixed_assets=make_sec("固定資産", AccountType.FIXED_ASSET, 0),
        deferred_assets=make_sec("繰延資産", AccountType.DEFERRED_ASSET, 0),
        current_liabilities=make_sec("流動負債", AccountType.CURRENT_LIABILITY, 100),
        fixed_liabilities=make_sec("固定負債", AccountType.FIXED_LIABILITY, 0),
        equity=make_sec("純資産", AccountType.EQUITY, 200),
        revenue=make_sec("売上高", AccountType.REVENUE, 500),
        cost_of_sales=make_sec("売上原価", AccountType.COST_OF_SALES, 200),
        sga=make_sec("販売管理費", AccountType.SGA, 100),
        non_op_income=make_sec("営業外収益", AccountType.NON_OPERATING_INCOME, 0),
        non_op_expense=make_sec("営業外費用", AccountType.NON_OPERATING_EXPENSE, 0),
        extra_income=make_sec("特別利益", AccountType.EXTRAORDINARY_INCOME, 0),
        extra_loss=make_sec("特別損失", AccountType.EXTRAORDINARY_LOSS, 0),
        total_assets=300,
        total_liabilities=100,
        total_equity=200,
        gross_profit=300,
        operating_income=200,
        ordinary_income=200,
        income_before_tax=200,
        net_income=200,
    )

    # Act
    pdf_bytes = PDFService.generate_annual_report(
        corp=corp,
        rpt=rpt,
        fiscal_year=fy,
        report_date=date(2026, 12, 31),
        audit_date=date(2026, 12, 31),
    )

    # Assert
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_service_generation_with_deficit_and_missing_representative() -> None:
    """Verify ReportLab rendering of financial report with net loss and minimal corporation profile."""
    # Arrange
    corp = Corporation(name="合同会社赤字テスト")
    fy = FiscalYear(
        id=2,
        name="第2期",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        period_number=2,
        status="OPEN",
    )
    empty_sec = FinancialSection(title="空セクション", rows=[], total=0)
    rpt = FinancialReport(
        fiscal_year=fy,
        current_assets=empty_sec,
        fixed_assets=empty_sec,
        deferred_assets=empty_sec,
        current_liabilities=empty_sec,
        fixed_liabilities=empty_sec,
        equity=empty_sec,
        revenue=empty_sec,
        cost_of_sales=empty_sec,
        sga=FinancialSection(
            title="販売管理費",
            rows=[
                TrialBalanceRow(
                    account_id=1,
                    account_code="6110",
                    account_name="給料手当",
                    account_type=AccountType.SGA,
                    balance=50000,
                    debit_balance=50000,
                )
            ],
            total=50000,
        ),
        non_op_income=empty_sec,
        non_op_expense=empty_sec,
        extra_income=empty_sec,
        extra_loss=empty_sec,
        total_assets=0,
        total_liabilities=0,
        total_equity=0,
        gross_profit=0,
        operating_income=-50000,
        ordinary_income=-50000,
        income_before_tax=-50000,
        net_income=-50000,
    )

    # Act
    pdf_bytes = PDFService.generate_annual_report(
        corp=corp,
        rpt=rpt,
        fy=fy,
    )

    # Assert
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


# --- 4. Filename Sanitization & OCR Defensive Handling ---
@pytest.mark.parametrize(
    ("raw_name", "expected_clean"),
    [
        ("領収書 / PC購入: 2026", "領収書  PC購入 2026"),
        ("Invoice*?<>|", "Invoice"),
        ("  test-file_01  ", "test-file_01"),
        ("", ""),
    ],
)
def test_sanitize_file_name_cleans_forbidden_filesystem_characters(
    raw_name: str, expected_clean: str
) -> None:
    """Verify filename sanitizer strips characters invalid in standard filesystem paths."""
    # Arrange
    from app.external_services import _sanitize_file_name

    # Act
    cleaned = _sanitize_file_name(raw_name)

    # Assert
    assert cleaned == expected_clean


@pytest.mark.parametrize(
    ("raw_text", "expected_contains"),
    [
        ("", ""),
        ("   ", ""),
        ('{"merchant": "A"}', '{"merchant": "A"}'),
        ('```json\n{"merchant": "B"}\n```', '{"merchant": "B"}'),
        ('```\n{"merchant": "C"}\n```', '{"merchant": "C"}'),
        ('  {"merchant": "D"}  ', '{"merchant": "D"}'),
    ],
)
def test_ocr_clean_json_codeblock_extracts_clean_json_payload(
    raw_text: str, expected_contains: str
) -> None:
    """Verify markdown code fence stripping and whitespace trimming from LLM responses."""
    # Arrange
    from app.ai_ocr_service import clean_json_codeblock

    # Act
    extracted = clean_json_codeblock(raw_text)

    # Assert
    assert extracted == expected_contains


@pytest.mark.asyncio
async def test_ocr_service_handles_safety_blocked_response_raises_value_error(
    container: Container, mocker: MockerFixture
) -> None:
    """Verify OCR handles candidate safety blocking by raising informative ValueError."""
    # Arrange
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    mock_candidate = mocker.MagicMock()
    mock_candidate.finish_reason = "SAFETY"

    mock_resp = mocker.MagicMock()
    mock_resp.text = ""
    mock_resp.candidates = [mock_candidate]
    mocker.patch("google.genai.models.Models.generate_content", return_value=mock_resp)

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-key"
        await ms.save_system_settings(settings_obj)

    # Act & Assert
    with pytest.raises(
        ValueError, match="コンテンツ安全フィルターにより生成がブロックされました"
    ):
        await service.extract_receipt_data(dummy_img, "png")


@pytest.mark.asyncio
async def test_ocr_service_extraction_with_registered_counterparty_sets_dictionary_matched(
    container: Container, mocker: MockerFixture
) -> None:
    """Verify OCR matches registered counterparty dictionary and sets matching flags."""
    # Arrange
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    mock_resp = mocker.MagicMock()
    mock_resp.text = '{"merchant_name": "登録済み珈琲店", "transaction_date": "2026-05-15", "total_amount_incl_tax": 650}'
    mocker.patch("google.genai.models.Models.generate_content", return_value=mock_resp)

    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-key"
        await ms.save_system_settings(settings_obj)
        await ms.save_counterparty(Counterparty(name="登録済み珈琲店"))

    # Act
    receipt = await service.extract_receipt_data(dummy_img, "png")

    # Assert
    assert receipt.merchant_name == "登録済み珈琲店"
    assert receipt.is_registered_merchant is True
    assert receipt.is_dictionary_matched is True
