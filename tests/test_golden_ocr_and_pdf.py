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

"""
First Stage Golden Master Test: OCR Service & PDF Service
Testing ONLY public API, mocking ONLY external boundary (Gemini API network calls).
"""

from datetime import date
import io
from PIL import Image
import pytest

from app.domain.models.corporation import Corporation
from app.domain.models.financial_report import FinancialReport, FinancialSection, TrialBalanceRow
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import AccountType
from app.infrastructure.external.ocr_service import GeminiOCRService, OpenAIOCRService
from app.infrastructure.external.pdf_service import PDFService


def _create_dummy_image() -> bytes:
    img = Image.new("RGB", (60, 60), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_golden_ocr_service_validations(container):
    service = GeminiOCRService()
    assert OpenAIOCRService is GeminiOCRService

    # 1. Empty file
    with pytest.raises(ValueError, match="アップロードされたファイルが空です"):
        await service.extract_receipt_data(b"", "png")

    # 2. Unsupported format
    with pytest.raises(ValueError, match="サポートされていないファイル形式です"):
        await service.extract_receipt_data(b"dummy", "exe")


@pytest.mark.asyncio
async def test_golden_ocr_service_extraction(container, mocker):
    service = GeminiOCRService()
    dummy_img = _create_dummy_image()

    # Mock external Gemini API network call
    mock_resp = mocker.MagicMock()
    mock_resp.text = '{"merchant_name": " ㈱テストストア ", "transaction_date": "2026-05-10", "total_amount_incl_tax": 4800, "invoice_registration_number": "T1234567890123"}'

    mocker.patch("google.genai.models.Models.generate_content", return_value=mock_resp)

    # Seed an API key in system settings so it doesn't fail
    async with container.master_service_scope() as ms:
        settings_obj = await ms.get_system_settings()
        settings_obj.ai_api_key = "test-golden-key"
        await ms.save_system_settings(settings_obj)

    receipt = await service.extract_receipt_data(dummy_img, "png")
    assert receipt.merchant_name == "(株)テストストア"
    assert receipt.transaction_date == "2026-05-10"
    assert receipt.total_amount_incl_tax == 4800
    assert receipt.invoice_registration_number == "T1234567890123"


def test_golden_pdf_service_generation():
    corp = Corporation(name="合同会社テスト", address="東京都渋谷区1-2-3", representative_title="代表社員", representative_name="山田 太郎")
    fy = FiscalYear(id=1, name="第1期", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), period_number=1, status="OPEN")

    def make_sec(title, t):
        return FinancialSection(
            title=title,
            rows=[TrialBalanceRow(account_id=1, account_code="1110", account_name="現金", account_type=t, debit_total=100, credit_total=0, balance=100, debit_balance=100, credit_balance=0)],
            total=100
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
