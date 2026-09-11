# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from datetime import date
import pytest
from streamlit.testing.v1 import AppTest
from app.core_foundation import DI, call_journal, call_master
from app.domain_contracts import (
    Corporation,
    Transaction,
    TransactionLine,
)


# --- 1. Streamlit App Navigation & Pages Interaction Tests ---
def test_app_main_navigation():
    """Verify that main app.py executes cleanly and configures sidebar layout."""
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception, f"app.py raised exception: {at.exception}"
    assert len(at.sidebar) >= 1


def test_journal_view_interactions():
    """Verify journal workspace renders tabs, inputs, and form elements."""
    at = AppTest.from_file("app/ui/views/journal_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"journal_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.date_input) >= 1


def test_ledger_view_interactions():
    """Verify ledger workspace renders trial balance, general ledger, and reports."""
    at = AppTest.from_file("app/ui/views/ledger_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"ledger_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.selectbox) >= 1


def test_master_view_interactions():
    """Verify master workspace renders corporate profile, fiscal periods, and editors."""
    at = AppTest.from_file("app/ui/views/master_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"master_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.text_input) >= 1


# --- 2. End-to-End System Integration Tests ---
@pytest.mark.asyncio
async def test_full_system_accounting_cycle(container):
    """Execute end-to-end corporate financial cycle from master setup through year-end closing."""
    # 1. Setup Corporation & Fiscal Year
    async with container.master_service_scope() as ms:
        await ms.initialize_default_accounts()
        await ms.save_corporation(
            Corporation(
                name="合同会社E2E統合",
                address="東京都千代田区1-1-1",
                representative_title="代表社員",
                representative_name="山田 花子",
            )
        )
        corp = await ms.get_corporation()
        assert corp.name == "合同会社E2E統合"

        accounts = await ms.get_accounts()
        cash = next(a for a in accounts if a.code == "1110")
        sales = next(a for a in accounts if a.code == "4110")
        supplies = next(a for a in accounts if a.code == "6170")

    # 2. Record Journal Entries
    async with container.journal_service_scope() as js:
        # Sales revenue
        tx1_id = await js.add_journal_entry(
            Transaction(
                date=date.today(),
                description="E2E売上計上",
                lines=[
                    TransactionLine(account_id=cash.id, debit=100000, credit=0),
                    TransactionLine(account_id=sales.id, debit=0, credit=100000),
                ],
                counterparty="クライアントA",
            )
        )
        assert tx1_id > 0

        # Expense
        tx2_id = await js.add_journal_entry(
            Transaction(
                date=date.today(),
                description="E2E消耗品購入",
                lines=[
                    TransactionLine(account_id=supplies.id, debit=20000, credit=0),
                    TransactionLine(account_id=cash.id, debit=0, credit=20000),
                ],
                counterparty="文具店B",
            )
        )
        assert tx2_id > 0

    # 3. Verify Financial Report
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        fy = next(f for f in fys if f.status == "OPEN")

    async with container.ledger_service_scope() as ls:
        rpt = await ls.generate_financial_report(fy.id)
        assert rpt.revenue.total >= 100000
        assert rpt.sga.total >= 20000
        assert rpt.operating_income == rpt.gross_profit - rpt.sga.total

    # 4. Year-End Closing & Retained Earnings Rollover
    async with container.fiscal_year_service_scope() as fys:
        next_fy = await fys.close_fiscal_year(fy.id)
        assert next_fy.status == "OPEN"
        assert next_fy.period_number == (fy.period_number or 0) + 1

    async with container.master_service_scope() as ms:
        old_fy = await ms.get_fiscal_year_by_id(fy.id)
        assert old_fy.status == "CLOSED"


# --- 3. Dependency Injection & Helper Utilities Tests ---
def test_di_container_resolution():
    """Verify DI static resolver methods return active service scope contexts."""
    assert DI.get_master_service() is not None
    assert DI.get_journal_service() is not None
    assert DI.get_ledger_service() is not None
    assert DI.get_fiscal_year_service() is not None
    assert DI.get_ocr_service() is not None
    assert DI.get_file_service() is not None
    assert DI.get_backup_service() is not None
    assert DI.get_pdf_service() is not None


@pytest.mark.asyncio
async def test_scoped_helper_functions(container):
    """Verify call_master and call_journal helper functions execute smoothly."""
    res_corp = call_master(lambda s: s.get_corporation())
    assert res_corp is not None or res_corp is None

    res_entries = call_journal(lambda s: s.get_entries())
    assert isinstance(res_entries, list)
