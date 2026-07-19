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
from datetime import date
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.account import AccountType
from app.domain.models.fiscal_year import FiscalYear


@pytest.mark.asyncio
class TestSystemIntegration:
    async def test_01_services_initialization(self, container):
        """Test that all key services can be initialized."""
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            master_service = await stack.enter_async_context(
                container.master_service_scope()
            )
            ledger_service = await stack.enter_async_context(
                container.ledger_service_scope()
            )
            journal_service = await stack.enter_async_context(
                container.journal_service_scope()
            )
            pdf_service = container.get_pdf_service()

            assert master_service is not None
            assert ledger_service is not None
            assert journal_service is not None
            assert pdf_service is not None

    async def test_02_master_data_integrity(self, container):
        """Test that minimal master data exists."""
        async with container.master_service_scope() as master_service:
            fys = await master_service.get_fiscal_years()
            accounts = await master_service.get_accounts()
            corp = await master_service.get_corporation()

        assert len(fys) > 0, "No Fiscal Years found"
        assert len(accounts) > 0, "No Accounts found"
        # Corporation is optional but expected in this setup
        if corp:
            assert corp.name is not None

    async def test_03_full_journal_entry_cycle(self, container):
        """
        Comprehensive Test:
        1. Create a Test Fiscal Year
        2. Create a Transaction (Journal Entry)
        3. Verify Transaction appears in General Ledger
        4. Verify Transaction affects Trial Balance
        5. Verify Financial Report generation
        6. Clean up (Delete Transaction and FY)
        """
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            master_service = await stack.enter_async_context(
                container.master_service_scope()
            )
            journal_service = await stack.enter_async_context(
                container.journal_service_scope()
            )
            ledger_service = await stack.enter_async_context(
                container.ledger_service_scope()
            )

            # --- A. Setup Test FY ---
            today = date.today()
            test_fy = FiscalYear(
                name="PYTEST_FY",
                start_date=date(today.year, 1, 1),
                end_date=date(today.year, 12, 31),
                status="OPEN",
                period_number=888,
            )

            # Clean up if exists from failed run
            fys = await master_service.get_fiscal_years()
            existing = next((f for f in fys if f.name == "PYTEST_FY"), None)
            if existing:
                await master_service.delete_fiscal_year(existing.id)

            await master_service.save_fiscal_year(test_fy)

            # Fetch updated user
            fys = await master_service.get_fiscal_years()
            target_fy = next((f for f in fys if f.name == "PYTEST_FY"), None)
            assert target_fy is not None

            # --- B. Setup Test Transaction ---
            accounts = await master_service.get_accounts()
            cash_acc = next(
                (a for a in accounts if a.type == AccountType.CURRENT_ASSET),
                accounts[0],
            )
            sales_acc = next(
                (a for a in accounts if a.type == AccountType.REVENUE), accounts[1]
            )

            test_amount = 1000
            tx = Transaction(
                date=today,
                description="PYTEST_TX",
                lines=[
                    TransactionLine(
                        account_id=cash_acc.id, debit=test_amount, credit=0
                    ),
                    TransactionLine(
                        account_id=sales_acc.id, debit=0, credit=test_amount
                    ),
                ],
            )

            tx_id = await journal_service.add_journal_entry(tx)
            assert tx_id is not None

            # --- C. Verify General Ledger ---
            gl_df = await ledger_service.get_general_ledger(target_fy.id, cash_acc.id)
            assert not gl_df.empty
            target_row = gl_df[gl_df["TransactionID"] == tx_id]
            assert not target_row.empty, "Transaction not found in General Ledger"

            # --- D. Verify Trial Balance ---
            tb_rows = await ledger_service.get_trial_balance(target_fy.id)
            cash_row = next((r for r in tb_rows if r.account_id == cash_acc.id), None)
            assert cash_row is not None
            assert cash_row.debit_total >= test_amount

            # --- E. Verify Financial Report (Regression Check) ---
            report = await ledger_service.generate_financial_report(target_fy.id)
            assert report is not None

            # --- F. Cleanup ---
            await journal_service.delete_entry(tx_id)

            # Verify Deletion from View
            gl_df_after = await ledger_service.get_general_ledger(
                target_fy.id, cash_acc.id
            )
            if not gl_df_after.empty:
                assert tx_id not in gl_df_after["TransactionID"].values

            # Verify Soft Delete Persistence and Accessibility
            deleted_entries = await journal_service.get_entries(include_deleted=True)
            target_deleted_entry = next(
                (e for e in deleted_entries if e.id == tx_id), None
            )
            assert target_deleted_entry is not None, (
                "Soft deleted transaction should be retrievable with include_deleted=True"
            )
            assert target_deleted_entry.deleted_at is not None, (
                "deleted_at timestamp should be set"
            )

            await master_service.delete_fiscal_year(target_fy.id)
