# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from app.ai_ocr_service import GeminiOCRService
from app.application_services import Container
from app.core_foundation import DI, call_journal, call_master
from app.domain_contracts import (
    Corporation,
    FiscalYear,
    Transaction,
    TransactionLine,
)
from app.external_services import BackupService, LocalFileService, PDFService


from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent


# --- 1. Streamlit App Navigation & Pages Interaction Tests ---
def test_app_main_navigation_executes_without_exception() -> None:
    """Verify that main app.py executes cleanly and configures sidebar layout."""
    # Arrange
    at = AppTest.from_file(str(_REPO_ROOT / "app.py"), default_timeout=15)

    # Act
    at.run()

    # Assert
    assert not at.exception, f"app.py raised exception: {at.exception}"
    assert len(at.sidebar) >= 1


def test_journal_view_interactions_renders_essential_widgets() -> None:
    """Verify journal workspace renders tabs, inputs, and form elements."""
    # Arrange
    at = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "journal_view.py"),
        default_timeout=15,
    )

    # Act
    at.run()

    # Assert
    assert not at.exception, f"journal_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.date_input) >= 1


def test_ledger_view_interactions_renders_essential_widgets() -> None:
    """Verify ledger workspace renders trial balance, general ledger, and reports."""
    # Arrange
    at = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "ledger_view.py"),
        default_timeout=15,
    )

    # Act
    at.run()

    # Assert
    assert not at.exception, f"ledger_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.selectbox) >= 1


def test_master_view_interactions_renders_essential_widgets() -> None:
    """Verify master workspace renders corporate profile, fiscal periods, and editors."""
    # Arrange
    at = AppTest.from_file(
        str(_REPO_ROOT / "app" / "ui" / "views" / "master_view.py"),
        default_timeout=15,
    )

    # Act
    at.run()

    # Assert
    assert not at.exception, f"master_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.text_input) >= 1


# --- 2. End-to-End System Integration Tests ---
@pytest.mark.asyncio
async def test_full_system_accounting_cycle(container: Container) -> None:
    """Execute end-to-end corporate financial cycle from master setup through year-end closing."""
    # Arrange: 1. Setup Corporation & Fiscal Year
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
        assert isinstance(corp, Corporation)
        assert corp.name == "合同会社E2E統合"
        assert corp.address == "東京都千代田区1-1-1"
        assert corp.representative_title == "代表社員"
        assert corp.representative_name == "山田 花子"

        accounts = await ms.get_accounts()
        cash = next(a for a in accounts if a.code == "1110")
        sales = next(a for a in accounts if a.code == "4110")
        supplies = next(a for a in accounts if a.code == "6170")
        assert cash.id is not None and sales.id is not None and supplies.id is not None

    # Act: 2. Record Journal Entries
    async with container.journal_service_scope() as js:
        # Sales revenue: 100,000 yen
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
        # Expense: 20,000 yen
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

    # Assert: 2. Journal Entry IDs
    assert tx1_id > 0
    assert tx2_id > 0

    # Act & Assert: 3. Verify Financial Report Invariants
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        fy = next(f for f in fys if f.status == "OPEN")
        assert fy.id is not None

    async with container.ledger_service_scope() as ls:
        rpt = await ls.generate_financial_report(fy.id)
        assert rpt.revenue.total == 100000
        assert rpt.cost_of_sales.total == 0
        assert rpt.gross_profit == 100000
        assert rpt.sga.total == 20000
        assert rpt.operating_income == 80000
        assert rpt.ordinary_income == 80000
        assert rpt.net_income == 80000
        assert rpt.total_assets == 80000
        assert rpt.total_liabilities == 0
        assert rpt.total_equity == 80000

    # Act & Assert: 4. Year-End Closing & Retained Earnings Rollover
    async with container.fiscal_year_service_scope() as fy_svc:
        next_fy = await fy_svc.close_fiscal_year(fy.id)
        assert next_fy.status == "OPEN"
        assert next_fy.period_number == (fy.period_number or 0) + 1

    async with container.master_service_scope() as ms:
        old_fy = await ms.get_fiscal_year_by_id(fy.id)
        assert isinstance(old_fy, FiscalYear)
        assert old_fy.id == fy.id
        assert old_fy.status == "CLOSED"


# --- 3. Dependency Injection & Helper Utilities Tests ---
def test_di_container_resolution_returns_active_service_instances() -> None:
    """Verify DI static resolver methods return active instances with expected contracts."""
    # Assert
    assert hasattr(DI.get_master_service(), "__aenter__")
    assert hasattr(DI.get_journal_service(), "__aenter__")
    assert hasattr(DI.get_ledger_service(), "__aenter__")
    assert hasattr(DI.get_fiscal_year_service(), "__aenter__")
    assert isinstance(DI.get_ocr_service(), GeminiOCRService)
    assert isinstance(DI.get_file_service(), LocalFileService)
    assert isinstance(DI.get_backup_service(), BackupService)
    assert isinstance(DI.get_pdf_service(), PDFService)


@pytest.mark.asyncio
async def test_scoped_helper_functions_execute_under_isolated_di_scope(
    container: Container,
) -> None:
    """Verify call_master and call_journal helper functions execute smoothly with strict assertions."""
    # Arrange
    async with container.master_service_scope() as ms:
        await ms.save_corporation(Corporation(name="スコープヘルパー検証法人"))

    # Act
    res_corp = call_master(lambda s: s.get_corporation())
    res_entries = call_journal(lambda s: s.get_entries())

    # Assert
    assert isinstance(res_corp, Corporation)
    assert res_corp.name == "スコープヘルパー検証法人"
    assert isinstance(res_entries, list)
    assert len(res_entries) == 0


_app_spec = importlib.util.spec_from_file_location(
    "sten_root_app", Path(__file__).resolve().parent.parent / "app.py"
)
if _app_spec is None or _app_spec.loader is None:
    raise ImportError("Failed to load app.py specification")
_app_mod = importlib.util.module_from_spec(_app_spec)
_app_spec.loader.exec_module(_app_mod)
resolve_active_fiscal_year = _app_mod.resolve_active_fiscal_year
load_sidebar_metadata = _app_mod.load_sidebar_metadata


def test_resolve_active_fiscal_year_with_mixed_statuses_returns_open_instance() -> None:
    """Verify resolve_active_fiscal_year returns the open fiscal year or None."""
    # Arrange
    fy_closed = FiscalYear(
        name="過去期",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        status="CLOSED",
        period_number=1,
    )
    fy_open = FiscalYear(
        name="現在期",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status="OPEN",
        period_number=2,
    )

    # Act & Assert
    assert resolve_active_fiscal_year([fy_closed, fy_open]) == fy_open
    assert resolve_active_fiscal_year([fy_closed]) is None
    assert resolve_active_fiscal_year([]) is None


@pytest.mark.asyncio
async def test_load_sidebar_metadata_with_structured_concurrency_returns_corp_and_fys(
    container: Container,
) -> None:
    """Verify load_sidebar_metadata retrieves corporation and fiscal years via TaskGroup."""
    # Arrange
    async with container.master_service_scope() as ms:
        await ms.save_corporation(Corporation(name="サイドバー検証会社"))
        corp, fys = await load_sidebar_metadata(ms.repository)

    # Assert
    assert isinstance(corp, Corporation)
    assert corp.name == "サイドバー検証会社"
    assert isinstance(fys, list)
    assert len(fys) > 0
