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
First Stage Golden Master Test: Application Services
Testing ONLY public API of JournalService, LedgerService, FiscalYearService, MasterService.
"""

from datetime import date
import pytest

from app.domain.models.account import Account, AccountType
from app.domain.models.transaction import Transaction, TransactionLine


@pytest.mark.asyncio
async def test_golden_master_service(container):
    async with container.master_service_scope() as ms:
        # Default accounts initialization
        added_count = await ms.initialize_default_accounts()
        assert added_count >= 0

        # Accounts check
        accounts = await ms.get_accounts()
        assert len(accounts) >= 2

        # Abstract
        first_acc = accounts[0]
        from app.domain.models.abstract import Abstract
        ab = await ms.save_abstract(Abstract(account_id=first_acc.id, text="金物代"))
        assert ab.id is not None
        fetched_abs = await ms.get_abstracts()
        assert any(a.id == ab.id for a in fetched_abs)
        await ms.delete_abstract(ab.id)


@pytest.mark.asyncio
async def test_golden_journal_service(container):
    async with container.master_service_scope() as ms:
        accounts = await ms.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]

    async with container.journal_service_scope() as js:
        # 1. Add Journal Entry
        tx = Transaction(
            date=date.today(),
            description="Golden Service Transaction",
            lines=[
                TransactionLine(account_id=acc1.id, debit=12000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=12000),
            ],
            counterparty="ゴールデン仕入先",
        )
        tx_id = await js.add_journal_entry(tx)
        assert tx_id > 0

        # 2. Get entries
        entries = await js.get_entries()
        assert any(e.id == tx_id for e in entries)

        # 3. CSV Export
        csv_str = await js.export_journal_entries_csv()
        assert "取引日,ID,摘要,取引先" in csv_str
        assert "Golden Service Transaction" in csv_str

        # 4. Opening Balance Registration
        op_id = await js.register_opening_balance(
            opening_date=date.today(),
            debit_balances={str(acc1.id): "50000"},
            credit_balances={str(acc2.id): "50000"},
        )
        assert op_id > 0

        # 5. Frequent Account IDs
        freq = await js.get_frequent_account_ids(limit=5)
        assert isinstance(freq, list)


@pytest.mark.asyncio
async def test_golden_ledger_service(container):
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        fy = fys[0]
        accounts = await ms.get_accounts()

    async with container.ledger_service_scope() as ls:
        # 1. Trial Balance
        tb_rows = await ls.get_trial_balance(fy.id)
        assert isinstance(tb_rows, list)
        assert len(tb_rows) == len(accounts)

        # 2. General Ledger
        df_gl = await ls.get_general_ledger(fy.id, accounts[0].id)
        assert hasattr(df_gl, "columns")

        # 3. Financial Report
        report = await ls.generate_financial_report(fy.id)
        assert report.fiscal_year.id == fy.id
        assert report.total_assets >= 0


@pytest.mark.asyncio
async def test_golden_fiscal_year_closing(container):
    async with container.master_service_scope() as ms:
        # Create a specific closed trial year and run closing
        today = date.today()
        from app.domain.models.fiscal_year import FiscalYear
        test_fy = await ms.save_fiscal_year(
            FiscalYear(
                name="締めテスト期",
                start_date=date(today.year - 2, 1, 1),
                end_date=date(today.year - 2, 12, 31),
                status="OPEN",
                period_number=99,
            )
        )
        # Ensure 繰越利益剰余金 exists
        accs = await ms.get_accounts()
        re_acc = next((a for a in accs if a.name == "繰越利益剰余金" or a.code == "3120"), None)
        if not re_acc:
            await ms.save_account(
                Account(code="3120", name="繰越利益剰余金", type=AccountType.EQUITY)
            )

    async with container.fiscal_year_service_scope() as fys:
        next_fy = await fys.close_fiscal_year(test_fy.id)
        assert next_fy is not None
        assert next_fy.period_number == 100
