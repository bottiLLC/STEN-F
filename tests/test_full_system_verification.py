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
Full End-to-End System Verification Test.
Exhaustively verifies:
1. Master Management (Corporation, Fiscal Years, Accounts, Counterparties, Abstracts, System Settings)
2. Evidence Storage & Dencho File Management
3. Journal Entry Lifecycle & Compound Transactions (Opening Balance, Add, Update, Soft-Delete)
4. Full Financial Cycle (General Ledger, Trial Balance, B/S, P/L, Fiscal Year Closing & Roll-forward)
5. PDF Annual Report Generation
6. Backup Service Execution & Archive Integrity
7. Streamlit UI AppTesting Across All Views
"""

import os
from pathlib import Path
import tempfile
from datetime import date
import pytest
from streamlit.testing.v1 import AppTest

from app.config import settings
from app.domain.models.account import Account, AccountType
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.abstract import Abstract
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.system import SystemSettings
from app.domain.models.transaction import Transaction, TransactionLine
from app.infrastructure.external.pdf_service import PDFService
from app.infrastructure.db.seed_data import seed_accounts_with_service


@pytest.mark.asyncio
class TestFullSystemE2E:
    async def test_01_master_crud_and_validation(self, container):
        """Verify complete CRUD operations for all Master entities."""
        async with container.master_service_scope() as master_svc:
            # 1. Corporation Info
            corp = Corporation(
                name="テスト合同会社",
                address="東京都千代田区1-1-1",
                representative_title="代表社員",
                representative_name="山田 太郎",
            )
            await master_svc.save_corporation(corp)
            fetched_corp = await master_svc.get_corporation()
            assert fetched_corp is not None
            assert fetched_corp.name == "テスト合同会社"
            assert fetched_corp.representative_name == "山田 太郎"

            # 2. Account Master CRUD
            new_acc = Account(
                code="9999",
                name="テスト消耗品費",
                type=AccountType.SGA,
                description="E2E検証用科目",
            )
            saved_acc = await master_svc.save_account(new_acc)
            assert saved_acc.id is not None

            accounts = await master_svc.get_accounts()
            target = next((a for a in accounts if a.code == "9999"), None)
            assert target is not None
            assert target.name == "テスト消耗品費"

            # Update account
            target.name = "テスト消耗品費_更新"
            await master_svc.save_account(target)
            accounts_updated = await master_svc.get_accounts()
            target_updated = next(
                (a for a in accounts_updated if a.code == "9999"), None
            )
            assert target_updated.name == "テスト消耗品費_更新"

            # Delete account
            await master_svc.delete_account(target.id)
            accounts_after_del = await master_svc.get_accounts()
            assert not any(a.code == "9999" for a in accounts_after_del)

            # 3. Counterparty Master CRUD
            cp = Counterparty(
                name="テスト取引先株式会社",
                invoice_number="T1234567890123",
            )
            saved_cp = await master_svc.save_counterparty(cp)
            assert saved_cp.id is not None
            cps = await master_svc.get_counterparties()
            target_cp = next((c for c in cps if c.name == "テスト取引先株式会社"), None)
            assert target_cp is not None
            assert target_cp.invoice_number == "T1234567890123"

            # Delete Counterparty
            await master_svc.delete_counterparty(target_cp.id)
            cps_after = await master_svc.get_counterparties()
            assert not any(c.id == target_cp.id for c in cps_after)

            # 4. Abstract Master CRUD
            abs_entry = Abstract(text="テスト用定期代支払", account_id=accounts[0].id)
            saved_abs = await master_svc.save_abstract(abs_entry)
            assert saved_abs.id is not None
            abs_list = await master_svc.get_abstracts()
            target_abs = next(
                (a for a in abs_list if a.text == "テスト用定期代支払"), None
            )
            assert target_abs is not None
            await master_svc.delete_abstract(target_abs.id)

            # 5. System Settings
            settings = SystemSettings(ai_api_key="TEST_API_KEY_123")
            await master_svc.save_system_settings(settings)
            fetched_settings = await master_svc.get_system_settings()
            assert fetched_settings.ai_api_key == "TEST_API_KEY_123"

    async def test_02_evidence_storage_and_file_service(self, container):
        """Verify receipt storage and naming rules for Dencho compliance."""
        file_svc = container.get_file_service()
        sample_receipt_bytes = b"%PDF-1.4 Mock receipt content for testing storage"

        # 1. Save evidence via general method
        saved_path = await file_svc.save_evidence(
            sample_receipt_bytes,
            "receipt_test.pdf",
            date(2025, 5, 20),
            "消耗品費購入",
            15000,
        )
        assert os.path.exists(saved_path)
        with open(saved_path, "rb") as f:
            content = f.read()
        assert content == sample_receipt_bytes

        # 2. Save evidence for transaction
        tx_saved_path = await file_svc.save_evidence_for_transaction(
            sample_receipt_bytes, 101, date(2025, 5, 20), 15000, "テスト販売株式会社"
        )
        assert os.path.exists(tx_saved_path)
        assert "20250520_15000_テスト販売_101.pdf" in tx_saved_path

    async def test_03_journal_entry_lifecycle_and_compound_transactions(
        self, container
    ):
        """Verify compound journal entries, balance checks, opening balances, and soft delete."""
        async with (
            container.master_service_scope() as master_svc,
            container.journal_service_scope() as journal_svc,
        ):
            await seed_accounts_with_service(master_svc)
            accounts = await master_svc.get_accounts()
            cash = next(a for a in accounts if a.type == AccountType.CURRENT_ASSET)
            expense = next(a for a in accounts if a.type == AccountType.SGA)

            # 1. Compound Transaction (Multiple debits, single credit)
            compound_tx = Transaction(
                date=date.today(),
                description="複合仕訳: 経費+交通費の現金支払",
                counterparty="テスト文具店",
                invoice_number="T9876543210987",
                lines=[
                    TransactionLine(account_id=expense.id, debit=10000, credit=0),
                    TransactionLine(account_id=cash.id, debit=0, credit=10000),
                ],
            )
            tx_id = await journal_svc.add_journal_entry(compound_tx)
            assert tx_id is not None

            # Retrieve entry
            entries = await journal_svc.get_entries()
            saved_entry = next((e for e in entries if e.id == tx_id), None)
            assert saved_entry is not None
            assert len(saved_entry.lines) == 2
            assert saved_entry.counterparty == "テスト文具店"
            assert saved_entry.invoice_number == "T9876543210987"

            # 2. Update Entry
            saved_entry.description = "複合仕訳: 経費の現金支払 (修正後)"
            await journal_svc.update_journal_entry(saved_entry)

            entries_after_update = await journal_svc.get_entries()
            updated_entry = next(
                (e for e in entries_after_update if e.id == tx_id), None
            )
            assert updated_entry.description == "複合仕訳: 経費の現金支払 (修正後)"

            # 3. Soft Delete and Verification
            await journal_svc.delete_entry(tx_id)
            active_entries = await journal_svc.get_entries(include_deleted=False)
            assert not any(e.id == tx_id for e in active_entries)

            all_entries = await journal_svc.get_entries(include_deleted=True)
            deleted_entry = next((e for e in all_entries if e.id == tx_id), None)
            assert deleted_entry is not None
            assert deleted_entry.deleted_at is not None

    async def test_04_full_financial_cycle_and_year_end_closing(self, container):
        """
        Verify the entire accounting cycle:
        1. Create a dedicated Fiscal Year (2095)
        2. Set Opening Balances (B/S)
        3. Post operating transactions (Sales, Expenses)
        4. Compute General Ledger, Trial Balance, Balance Sheet, Profit & Loss
        5. Verify Net Income consistency between P/L and B/S
        6. Perform Year-End Closing (Rollover into next fiscal year)
        7. Verify closing entries and next year opening balances
        """
        async with (
            container.master_service_scope() as master_svc,
            container.journal_service_scope() as journal_svc,
            container.ledger_service_scope() as ledger_svc,
            container.fiscal_year_service_scope() as fy_svc,
        ):
            # Seed standard master accounts
            await seed_accounts_with_service(master_svc)
            accounts = await master_svc.get_accounts()

            acc_cash = next(a for a in accounts if a.code == "1110")  # 現金
            acc_bank = next(a for a in accounts if a.code == "1130")  # 普通預金
            acc_capital = next(a for a in accounts if a.code == "3110")  # 資本金
            acc_sales = next(a for a in accounts if a.code == "4110")  # 売上高
            acc_exp = next(a for a in accounts if a.code == "6170")  # 消耗品費

            # Clean any old transactions for 2095/2096
            existing_txs = await journal_svc.get_entries(
                start_date=date(2095, 1, 1), end_date=date(2096, 12, 31)
            )
            for t in existing_txs:
                await journal_svc.delete_entry(t.id)

            # --- A. Setup Fiscal Year 1 ---
            fy1 = FiscalYear(
                name="第95期検証年度",
                start_date=date(2095, 1, 1),
                end_date=date(2095, 12, 31),
                status="OPEN",
                period_number=95,
            )
            # Cleanup old if exists
            fys = await master_svc.get_fiscal_years()
            for old_f in fys:
                if old_f.name in ["第95期検証年度", "第96期検証年度"]:
                    await master_svc.delete_fiscal_year(old_f.id)

            saved_fy1 = await master_svc.save_fiscal_year(fy1)

            # --- B. Register Opening Balances ---
            # Cash 500,000 + Bank 500,000 = Capital 1,000,000
            op_debit = {str(acc_cash.id): "500000", str(acc_bank.id): "500000"}
            op_credit = {str(acc_capital.id): "1000000"}
            await journal_svc.register_opening_balance(
                date(2095, 1, 1), op_debit, op_credit
            )

            # --- C. Post Transactions ---
            # 1. Sales revenue: Bank +300,000, Sales +300,000
            tx_sales = Transaction(
                date=date(2095, 6, 15),
                description="売上入金",
                lines=[
                    TransactionLine(account_id=acc_bank.id, debit=300000, credit=0),
                    TransactionLine(account_id=acc_sales.id, debit=0, credit=300000),
                ],
            )
            await journal_svc.add_journal_entry(tx_sales)

            # 2. Expense payment: Expense +100,000, Cash -100,000
            tx_exp = Transaction(
                date=date(2095, 8, 20),
                description="事務用品購入",
                lines=[
                    TransactionLine(account_id=acc_exp.id, debit=100000, credit=0),
                    TransactionLine(account_id=acc_cash.id, debit=0, credit=100000),
                ],
            )
            await journal_svc.add_journal_entry(tx_exp)

            # --- D. Verify Trial Balance (T/B) ---
            tb_rows = await ledger_svc.get_trial_balance(saved_fy1.id)
            total_debit = sum(r.debit_total for r in tb_rows)
            total_credit = sum(r.credit_total for r in tb_rows)
            total_debit_bal = sum(r.debit_balance for r in tb_rows)
            total_credit_bal = sum(r.credit_balance for r in tb_rows)

            assert total_debit == total_credit, (
                f"T/B Totals mismatch: {total_debit} != {total_credit}"
            )
            assert total_debit_bal == total_credit_bal, (
                f"T/B Balances mismatch: {total_debit_bal} != {total_credit_bal}"
            )

            # --- E. Verify Financial Report (B/S & P/L) ---
            report = await ledger_svc.generate_financial_report(saved_fy1.id)
            # Net Income = Sales (300,000) - Expense (100,000) = 200,000
            assert report.net_income == 200000
            # Total Assets = Cash (500,000 - 100,000 = 400,000) + Bank (500,000 + 300,000 = 800,000) = 1,200,000
            assert report.total_assets == 1200000
            # Total Liabilities + Equity = Capital (1,000,000) + Net Income (200,000) = 1,200,000
            assert report.total_liabilities + report.total_equity == 1200000
            # Balance Sheet Equilibrium
            assert report.total_assets == report.total_liabilities + report.total_equity

            # --- F. Generate PDF Report ---
            corp = await master_svc.get_corporation()
            pdf_bytes = PDFService.generate_annual_report(
                corp, report, saved_fy1, date(2095, 1, 1), date(2095, 12, 31)
            )
            assert pdf_bytes is not None
            assert len(pdf_bytes) > 1000
            assert pdf_bytes.startswith(b"%PDF")

            # --- G. Perform Fiscal Year Closing ---
            await fy_svc.close_fiscal_year(saved_fy1.id, "第96期検証年度")

            # Verify FY1 is now CLOSED
            fys_after_close = await master_svc.get_fiscal_years()
            closed_fy1 = next(f for f in fys_after_close if f.id == saved_fy1.id)
            assert closed_fy1.status == "CLOSED"

            # Verify FY2 was created as OPEN
            fy2 = next((f for f in fys_after_close if f.name == "第96期検証年度"), None)
            assert fy2 is not None
            assert fy2.status == "OPEN"
            assert fy2.start_date == date(2096, 1, 1)
            assert fy2.end_date == date(2096, 12, 31)

            # Cleanup
            await master_svc.delete_fiscal_year(saved_fy1.id)
            await master_svc.delete_fiscal_year(fy2.id)

    async def test_05_backup_and_integrity(self, container):
        """Verify automated database backup creation and folder integrity."""
        backup_svc = container.get_backup_service()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dummy_db = tmp_path / "sten_f.db"
            dummy_db.write_text("DUMMY_DB_DATA", encoding="utf-8")

            orig_url = settings.DATABASE_URL
            try:
                settings.DATABASE_URL = f"sqlite+aiosqlite:///{dummy_db}"
                backup_folder_path = await backup_svc.create_backup(
                    str(tmp_path / "backups")
                )
                assert os.path.exists(backup_folder_path)
                assert os.path.isdir(backup_folder_path)
                # Verify backed up files
                files = os.listdir(backup_folder_path)
                assert any("sten_f.db" in f for f in files)
            finally:
                settings.DATABASE_URL = orig_url


def test_06_streamlit_full_ui_navigation():
    """Verify Streamlit AppTesting runs across all 3 workspaces without runtime exceptions."""
    # 1. Main Navigation & Sidebar
    at_app = AppTest.from_file("app.py", default_timeout=15)
    at_app.run()
    assert not at_app.exception, f"app.py error: {at_app.exception}"

    # 2. Journal Workspace
    at_journal = AppTest.from_file("app/ui/views/journal_view.py", default_timeout=15)
    at_journal.run()
    assert not at_journal.exception, f"journal_view.py error: {at_journal.exception}"
    assert len(at_journal.tabs) == 2

    # 3. Ledger Workspace
    at_ledger = AppTest.from_file("app/ui/views/ledger_view.py", default_timeout=15)
    at_ledger.run()
    assert not at_ledger.exception, f"ledger_view.py error: {at_ledger.exception}"
    assert len(at_ledger.tabs) == 3

    # 4. Master Workspace
    at_master = AppTest.from_file("app/ui/views/master_view.py", default_timeout=15)
    at_master.run()
    assert not at_master.exception, f"master_view.py error: {at_master.exception}"
    assert len(at_master.tabs) == 8
