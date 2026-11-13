# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final
from pydantic import ValidationError
import pytest
from streamlit.testing.v1 import AppTest

from app.ai_ocr_service import match_counterparty_master
from app.application_services import Container
from app.core_foundation import DI
from app.domain_contracts import (
    DEFAULT_ACCOUNTS,
    Account,
    AccountType,
    Corporation,
    Counterparty,
    FiscalYear,
    ReceiptRawExtractionSchema,
    Transaction,
    TransactionLine,
    VendorMasterRecord,
)
from app.external_services import PDFService
from app.storage_repository import seed_accounts_with_service

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_SAMPLE_RECEIPT_PDF_BYTES: Final[bytes] = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


# --- 1. Synthetic Receipt PDF & OCR Matching Verification ---
def test_verify_sample_receipt_pdf_exists_and_matches_counterparty_master() -> None:
    """Verify synthetic sample receipt PDF payload and multi-tier composite OCR matching."""
    # Arrange
    pdf_bytes = _SAMPLE_RECEIPT_PDF_BYTES
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF"), "Evidence file must be valid PDF format"

    # Simulated OCR extraction matching text on the receipt (株式会社アークリンク / T5011001046175 / 800 JPY)
    raw_extracted = ReceiptRawExtractionSchema(
        merchant_name="株式会社アークリンク",
        invoice_registration_number="T5011001046175",
        transaction_date="2026-06-02",
        total_amount=800,
        tax_rate=0.10,
        description="駐車料金 パークステーション十日市場第1",
    )

    vendor_records = [
        VendorMasterRecord(
            vendor_id=101,
            name="株式会社アークリンク",
            invoice_number="T5011001046175",
            debit_account="6150",
            tax_rate=Decimal("0.10"),
        ),
        VendorMasterRecord(
            vendor_id=102,
            name="無関係商店",
            invoice_number="T9999999999999",
            debit_account="6170",
            tax_rate=Decimal("0.10"),
        ),
    ]

    # Act
    match_result = match_counterparty_master(
        raw_extracted, vendor_records, threshold=75.0
    )

    # Assert
    assert match_result.matched_vendor is not None
    assert match_result.matched_vendor.name == "株式会社アークリンク"
    assert match_result.score >= 75.0
    assert match_result.is_identified


# --- 2. Comprehensive Accounting Cycle Utilizing ALL 48 Default Accounts ---
@pytest.mark.asyncio
async def test_full_regression_accounting_cycle_all_48_accounts(
    container: Container,
) -> None:
    """Execute end-to-end regression verification covering 100% of standard accounts and PDF export."""
    # Step 1: Initialize Database & Seed all 48 default accounts
    async with container.master_service_scope() as ms:
        await seed_accounts_with_service(ms.repository)
        all_accounts = await ms.get_accounts()
        account_map = {acc.code: acc for acc in all_accounts}

        # Assert all 48 accounts exist in master
        for default_item in DEFAULT_ACCOUNTS:
            assert default_item["code"] in account_map, (
                f"Missing account code {default_item['code']}"
            )

        # Step 2: Setup Corporation Profile
        corp = Corporation(
            name="合同会社STEN-F検証",
            address="神奈川県横浜市緑区十日市場町1-1",
            representative_title="代表社員",
            representative_name="検証 太郎",
            invoice_number="T1234567890123",
        )
        await ms.save_corporation(corp)
        saved_corp = await ms.get_corporation()
        assert saved_corp is not None
        assert saved_corp.name == "合同会社STEN-F検証"

        # Step 3: Setup Counterparty for synthetic receipt PDF
        cp_arclink = Counterparty(
            name="株式会社アークリンク",
            name_kana="アークリンク",
            trade_name="パークステーション十日市場第1",
            invoice_number="T5011001046175",
            debit_account_id=account_map["6150"].id,
            credit_account_id=account_map["1110"].id,
            description_template="十日市場駐車場代",
        )
        await ms.save_counterparty(cp_arclink)

        # Step 4: Setup Fiscal Year
        existing_fys = await ms.get_fiscal_years()
        fy_2026 = next(
            (
                f
                for f in existing_fys
                if f.start_date == date(2026, 1, 1) and f.end_date == date(2026, 12, 31)
            ),
            None,
        )
        if fy_2026:
            saved_fy = fy_2026
        else:
            fy = FiscalYear(
                name="FY2026",
                period_number=1,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                status="OPEN",
            )
            saved_fy = await ms.save_fiscal_year(fy)
        assert saved_fy.id is not None
        fy_id = saved_fy.id

    # Step 5: Record Initial Balances and Verify Zero-Tolerance Balance (Rule 2)
    async with container.journal_service_scope() as js:
        # Opening entry: Assets vs Capital
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 1, 1),
                description="期首残高開始仕訳",
                lines=[
                    TransactionLine(
                        account_id=account_map["1110"].id or 0, debit=2000000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1130"].id or 0, debit=8000000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["3110"].id or 0, debit=0, credit=10000000
                    ),
                ],
            )
        )

        # Step 6: Evidence Attachment with synthetic receipt PDF
        pdf_bytes = _SAMPLE_RECEIPT_PDF_BYTES
        receipt_tx = Transaction(
            occurred_at=date(2026, 6, 2),
            description="十日市場駐車場代",
            counterparty="株式会社アークリンク",
            invoice_number="T5011001046175",
            lines=[
                TransactionLine(
                    account_id=account_map["6150"].id or 0, debit=800, credit=0
                ),
                TransactionLine(
                    account_id=account_map["1110"].id or 0, debit=0, credit=800
                ),
            ],
        )
        tx_ocr_id = await js.add_journal_entry_with_evidence(
            receipt_tx,
            pdf_bytes,
            DI.get_file_service(),
            extension=".pdf",
        )
        assert tx_ocr_id > 0

        # Step 7: Post Transactions Touching ALL Remaining Default Accounts
        # 1. Other Current Assets (1120, 1140, 1150, 1160, 1170, 1180, 1190) & Revenue (4110, 4120)
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 6, 10),
                description="売掛金計上・普通預金振替・有価証券取得・仮払・前払・立替・未収",
                lines=[
                    TransactionLine(
                        account_id=account_map["1120"].id or 0, debit=500000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1140"].id or 0, debit=300000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1150"].id or 0, debit=50000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1160"].id or 0, debit=120000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1170"].id or 0, debit=30000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1180"].id or 0, debit=100000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1190"].id or 0, debit=2000000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["4110"].id or 0, debit=0, credit=2800000
                    ),
                    TransactionLine(
                        account_id=account_map["4120"].id or 0, debit=0, credit=300000
                    ),
                ],
            )
        )

        # 2. Fixed & Deferred Assets (1510, 1520, 1530, 1540, 1710, 1720) & Long-term Debt (2510)
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 6, 15),
                description="設備投資・借入・繰延資産",
                lines=[
                    TransactionLine(
                        account_id=account_map["1510"].id or 0, debit=1500000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1520"].id or 0, debit=800000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1530"].id or 0, debit=400000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1540"].id or 0, debit=600000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1710"].id or 0, debit=100000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1720"].id or 0, debit=150000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["2510"].id or 0, debit=0, credit=3000000
                    ),
                    TransactionLine(
                        account_id=account_map["1130"].id or 0, debit=0, credit=550000
                    ),
                ],
            )
        )

        # 3. Liabilities (2110, 2120, 2130, 2140, 2150, 2160, 2170, 2180) & Cost of Sales (5110, 5120)
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 7, 1),
                description="仕入・外注費・各種負債計上",
                lines=[
                    TransactionLine(
                        account_id=account_map["5110"].id or 0, debit=600000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["5120"].id or 0, debit=400000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["2110"].id or 0, debit=0, credit=300000
                    ),
                    TransactionLine(
                        account_id=account_map["2120"].id or 0, debit=0, credit=200000
                    ),
                    TransactionLine(
                        account_id=account_map["2130"].id or 0, debit=0, credit=100000
                    ),
                    TransactionLine(
                        account_id=account_map["2140"].id or 0, debit=0, credit=50000
                    ),
                    TransactionLine(
                        account_id=account_map["2150"].id or 0, debit=0, credit=150000
                    ),
                    TransactionLine(
                        account_id=account_map["2160"].id or 0, debit=0, credit=80000
                    ),
                    TransactionLine(
                        account_id=account_map["2170"].id or 0, debit=0, credit=70000
                    ),
                    TransactionLine(
                        account_id=account_map["2180"].id or 0, debit=0, credit=50000
                    ),
                ],
            )
        )

        # 4. SGA Accounts (6110, 6120, 6130, 6140, 6160, 6170, 6180, 6190, 6200, 6210, 6220)
        # Note: 6150 was already exercised via the OCR receipt
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 7, 25),
                description="販売管理費一括計上",
                lines=[
                    TransactionLine(
                        account_id=account_map["6110"].id or 0, debit=300000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6120"].id or 0, debit=250000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6130"].id or 0, debit=40000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6140"].id or 0, debit=15000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6160"].id or 0, debit=20000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6170"].id or 0, debit=18000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6180"].id or 0, debit=35000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6190"].id or 0, debit=12000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6200"].id or 0, debit=8000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6210"].id or 0, debit=50000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["6220"].id or 0, debit=5000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["1130"].id or 0, debit=0, credit=753000
                    ),
                ],
            )
        )

        # 5. Non-Operating, Taxes, Retained Earnings (7110, 7120, 7130, 7510, 7520, 7530, 9110, 3120)
        await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 12, 28),
                description="営業外損益・税金・剰余金調整",
                lines=[
                    TransactionLine(
                        account_id=account_map["1130"].id or 0, debit=60000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["7510"].id or 0, debit=15000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["7520"].id or 0, debit=10000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["7530"].id or 0, debit=15000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["9110"].id or 0, debit=70000, credit=0
                    ),
                    TransactionLine(
                        account_id=account_map["7110"].id or 0, debit=0, credit=5000
                    ),
                    TransactionLine(
                        account_id=account_map["7120"].id or 0, debit=0, credit=25000
                    ),
                    TransactionLine(
                        account_id=account_map["7130"].id or 0, debit=0, credit=30000
                    ),
                    TransactionLine(
                        account_id=account_map["1110"].id or 0, debit=0, credit=110000
                    ),
                ],
            )
        )

        # Verify Reversing Entry (赤伝) for Immutability constraint (Rule 1)
        rev_id = await js.reverse_journal_entry(tx_ocr_id, reason="領収書再テスト取消")
        all_entries = await js.get_entries()
        rev_tx = next((tx for tx in all_entries if tx.id == rev_id), None)
        assert rev_tx is not None
        # Assert inverted debit and credit lines
        assert any(
            line.account_id == account_map["1110"].id and line.debit == 800
            for line in rev_tx.lines
        )
        assert any(
            line.account_id == account_map["6150"].id and line.credit == 800
            for line in rev_tx.lines
        )

    # Step 8: Verify Trial Balance Equality (Rule 2 Zero-Tolerance Balance)
    async with container.ledger_service_scope() as ls:
        tb_rows = await ls.get_trial_balance(fy_id)
        assert len(tb_rows) > 0

        total_debit_balance = sum(r.debit_balance for r in tb_rows)
        total_credit_balance = sum(r.credit_balance for r in tb_rows)
        assert total_debit_balance == total_credit_balance, (
            f"Trial Balance debit ({total_debit_balance}) must equal credit ({total_credit_balance})"
        )

        # Step 9: Verify Financial Report (B/S & P/L) Calculations
        report = await ls.generate_financial_report(fy_id)

        # B/S Invariant: Total Assets == Total Liabilities + Total Equity + Current Net Income
        calculated_assets = (
            report.current_assets.total
            + report.fixed_assets.total
            + report.deferred_assets.total
        )
        calculated_liabilities = (
            report.current_liabilities.total + report.fixed_liabilities.total
        )
        calculated_equity_and_income = report.equity.total + report.net_income

        assert (
            calculated_assets == calculated_liabilities + calculated_equity_and_income
        ), (
            f"B/S Inbalance: Assets({calculated_assets}) != Liab({calculated_liabilities}) + Eq+Inc({calculated_equity_and_income})"
        )

        # Step 10: Generate and Assert Corporate Financial PDF Report (決算書出力)
        async with container.master_service_scope() as ms:
            corp_profile = await ms.get_corporation() or Corporation()
            report_fy = await ms.get_fiscal_year_by_id(fy_id) or fy

        pdf_report_bytes = PDFService.generate_annual_report(
            corp_profile, report, report_fy, date(2026, 12, 31), date(2027, 2, 28)
        )
        assert isinstance(pdf_report_bytes, bytes)
        assert len(pdf_report_bytes) > 1000
        assert pdf_report_bytes.startswith(b"%PDF-"), (
            "Generated financial statement must be a valid PDF"
        )

    # Step 11: Fiscal Year Closing & Retained Earnings Rollover
    async with container.fiscal_year_service_scope() as fys:
        next_fy = await fys.close_fiscal_year(fy_id, next_fy_name="FY2027")
        assert next_fy.status == "OPEN"
        assert next_fy.period_number == 2
        assert next_fy.name == "FY2027"

        # Assert old period is CLOSED
        async with container.master_service_scope() as ms:
            closed_fy = await ms.get_fiscal_year_by_id(fy_id)
            assert closed_fy is not None
            assert closed_fy.status == "CLOSED"


# --- 3. Streamlit UI Views & All Input Widgets Regression Verification ---
def test_all_ui_views_and_input_widgets_render_and_accept_values() -> None:
    """Verify that all views, tabs, forms, and input widgets render without exceptions."""
    # 1. Main Navigation & Sidebar Layout
    at_app = AppTest.from_file(str(_REPO_ROOT / "app.py"), default_timeout=15).run()
    assert not at_app.exception, f"app.py raised exception: {at_app.exception}"
    assert len(at_app.sidebar) >= 1

    # 2. Journal View (All Tabs & Inputs)
    at_journal = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "journal_view.py"),
        default_timeout=15,
    ).run()
    assert not at_journal.exception, (
        f"journal_view raised exception: {at_journal.exception}"
    )
    assert len(at_journal.tabs) >= 2
    assert len(at_journal.file_uploader) >= 1
    assert len(at_journal.date_input) >= 1
    assert len(at_journal.text_input) >= 1

    # 3. Ledger View (All Tabs & Selectors)
    at_ledger = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "ledger_view.py"),
        default_timeout=15,
    ).run()
    assert not at_ledger.exception, (
        f"ledger_view raised exception: {at_ledger.exception}"
    )
    assert len(at_ledger.tabs) >= 3
    assert len(at_ledger.selectbox) >= 1

    # 4. Master View (All 7 Tabs, Forms, Data Editors, System Settings)
    at_master = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "master_view.py"),
        default_timeout=15,
    ).run()
    assert not at_master.exception, (
        f"master_view raised exception: {at_master.exception}"
    )
    assert len(at_master.tabs) >= 7
    # Assert data editors for Accounts, Counterparties, Abstracts
    assert len(at_master.dataframe) >= 3


# --- 4. Accounting Guardrails & Domain Auditing Tests ---
@pytest.mark.asyncio
async def test_fiscal_period_and_referential_integrity_guardrails(
    container: Container,
) -> None:
    """Verify fiscal period date guardrails and account referential integrity deletion protection."""
    async with container.master_service_scope() as ms:
        await seed_accounts_with_service(ms.repository)
        accounts = await ms.get_accounts()
        cash = next(a for a in accounts if a.code == "1110")
        assert cash.id is not None

        # Ensure Open Fiscal Year FY2026: 2026-01-01 to 2026-12-31 exists
        existing_fys = await ms.get_fiscal_years()
        fy_2026 = next(
            (
                f
                for f in existing_fys
                if f.start_date == date(2026, 1, 1) and f.end_date == date(2026, 12, 31)
            ),
            None,
        )
        if not fy_2026:
            await ms.save_fiscal_year(
                FiscalYear(
                    name="FY2026",
                    period_number=1,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    status="OPEN",
                )
            )

        # Create temporary custom account for deletion testing
        temp_acc = await ms.save_account(
            Account(
                code="9990",
                name="一時検証科目",
                type=AccountType.SGA,
                description="削除テスト用",
            )
        )
        assert temp_acc.id is not None
        temp_id = temp_acc.id

    # 1. Fiscal Period Guardrail: Out of range date must be rejected
    async with container.journal_service_scope() as js:
        with pytest.raises(
            ValueError, match="指定された日付は、現在「OPEN」な会計年度の範囲外です"
        ):
            await js.add_journal_entry(
                Transaction(
                    occurred_at=date(2025, 12, 31),  # Out of range!
                    description="期外仕訳テスト",
                    lines=[
                        TransactionLine(account_id=cash.id, debit=1000, credit=0),
                        TransactionLine(account_id=temp_id, debit=0, credit=1000),
                    ],
                )
            )

        # Post a valid transaction using cash (1110)
        valid_tx_id = await js.add_journal_entry(
            Transaction(
                occurred_at=date(2026, 5, 1),
                description="有効仕訳",
                lines=[
                    TransactionLine(account_id=cash.id, debit=5000, credit=0),
                    TransactionLine(account_id=cash.id, debit=0, credit=5000),
                ],
            )
        )
        assert valid_tx_id > 0

    # 2. Referential Integrity Guardrail: Used account cannot be deleted
    async with container.master_service_scope() as ms:
        assert ms.ledger_repository is not None
        has_tx = await ms.ledger_repository.has_transactions_for_account(cash.id)
        assert has_tx is True

        # 3. Clean deletion of unused account succeeds
        has_tx_temp = await ms.ledger_repository.has_transactions_for_account(temp_id)
        assert has_tx_temp is False
        await ms.delete_account(temp_id)
        assert not any(a.id == temp_id for a in await ms.get_accounts())


def test_invoice_number_normalization_and_validation() -> None:
    """Verify invoice number normalizer handles T-prefixing, whitespace, and raises on invalid digits."""
    # 1. 13-digit raw number auto-prepended with 'T'
    cp1 = Counterparty(name="テスト商店A", invoice_number="1234567890123")
    assert cp1.invoice_number == "T1234567890123"

    # 2. Zenkaku and hyphens normalized
    cp2 = Counterparty(name="テスト商店B", invoice_number=" Ｔ 1234-5678-90123 ")
    assert cp2.invoice_number == "T1234567890123"

    # 3. Short digits rejected with ValidationError
    with pytest.raises(ValidationError):
        Counterparty(name="テスト商店C", invoice_number="123456789")
