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
from sqlalchemy import delete
from app.domain.models.account import Account, AccountType
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.fiscal_year import FiscalYear
from app.infrastructure.db.models import AccountTable, TransactionTable, TransactionLineTable, FiscalYearTable

@pytest.mark.asyncio
async def test_fiscal_year_closing_flow(container):
    """
    Test the full fiscal year closing process.
    Scenario:
    - Current FY: 2025-04-01 to 2026-03-31
    - Transactions:
        - Sales (Revenue): 10,000
        - Expense (SGA): 3,000
        - Net Income: 7,000
        - Cash (Asset): 12,000 (10k sales + 2k initial)
        - Liability: 2,000
        - Capital (Equity): 3,000 (Initial)
        - Retained Earnings: 0 (Initial)
    - Expectation:
        - Next FY Created (2026-04-01 ~)
        - Opening Entry:
            - Dr Cash 12,000
            - Cr Liability 2,000
            - Cr Capital 3,000
            - Cr Retained Earnings 7,000 (0 + 7,000)
    """
    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(container.master_service_scope())
        journal_service = await stack.enter_async_context(container.journal_service_scope())
        fy_service = await stack.enter_async_context(container.fiscal_year_service_scope())

        # 0. Cleanup (Simulate Empty DB)
        # Using repository session to delete all data
        session = master_service.repository.session
        await session.execute(delete(TransactionLineTable))
        await session.execute(delete(TransactionTable))
        await session.execute(delete(FiscalYearTable))
        await session.execute(delete(AccountTable))
        await session.commit()
        
        # 1. Setup Data
        # 1.1 Accounts
        # We need to ensure specific accounts exist or create them.
        # Check for Capital and Retained Earnings (3110, 3120)
        accounts = await master_service.get_accounts()
        
        def get_or_create(code, name, type):
            acc = next((a for a in accounts if a.code == code), None)
            if not acc:
                return Account(code=code, name=name, type=type)
            return acc

        acc_cash = get_or_create("1110", "Cash", AccountType.CURRENT_ASSET)
        if not acc_cash.id: 
            await master_service.save_account(acc_cash)

        acc_sales = get_or_create("4110", "Sales", AccountType.REVENUE)
        if not acc_sales.id: 
            await master_service.save_account(acc_sales)

        acc_expense = get_or_create("6110", "Expense", AccountType.SGA)
        if not acc_expense.id: 
            await master_service.save_account(acc_expense)

        acc_capital = get_or_create("3110", "Capital", AccountType.EQUITY)
        if not acc_capital.id: 
            await master_service.save_account(acc_capital)

        acc_re = get_or_create("3120", "Retained Earnings", AccountType.EQUITY)
        if not acc_re.id: 
            await master_service.save_account(acc_re)
        
        # Reload accounts to get IDs
        accounts = await master_service.get_accounts()
        acc_cash = next(a for a in accounts if a.code == "1110")
        acc_sales = next(a for a in accounts if a.code == "4110")
        acc_expense = next(a for a in accounts if a.code == "6110")
        acc_capital = next(a for a in accounts if a.code == "3110")
        acc_re = next(a for a in accounts if a.code == "3120")
    
        # 1.2 Fiscal Year
        fy_start = date(2025, 4, 1)
        fy_end = date(2026, 3, 31)
        
        current_fy = FiscalYear(
            name="Test Phase FY",
            start_date=fy_start,
            end_date=fy_end,
            period_number=1,
            status="OPEN"
        )
        saved_fy = await master_service.save_fiscal_year(current_fy)
        
        # 1.3 Transactions
        # TR1: Invest Capital (Cash 5000 / Capital 5000)
        await journal_service.add_journal_entry(Transaction(
            date=fy_start,
            description="Initial Capital",
            lines=[
                TransactionLine(account_id=acc_cash.id, debit=5000, credit=0),
                TransactionLine(account_id=acc_capital.id, debit=0, credit=5000)
            ]
        ))
        
        # TR2: Sales (Cash 10000 / Sales 10000)
        await journal_service.add_journal_entry(Transaction(
            date=date(2025, 6, 1),
            description="Sales",
            lines=[
                TransactionLine(account_id=acc_cash.id, debit=10000, credit=0),
                TransactionLine(account_id=acc_sales.id, debit=0, credit=10000)
            ]
        ))
    
        # TR3: Expense (Expense 3000 / Cash 3000)
        await journal_service.add_journal_entry(Transaction(
            date=date(2025, 12, 1),
            description="Expense",
            lines=[
                TransactionLine(account_id=acc_expense.id, debit=3000, credit=0),
                TransactionLine(account_id=acc_cash.id, debit=0, credit=3000)
            ]
        ))
        
        # Expected State:
        # Cash: 5000 + 10000 - 3000 = 12000 (Debit)
        # Capital: 5000 (Credit)
        # Sales: 10000 (Credit)
        # Expense: 3000 (Debit)
        # Net Income: 10000 - 3000 = 7000
        # Expected RE Carryover: 0 (Start) + 7000 (NI) = 7000
    
        # 2. Execute Closing
        next_fy = await fy_service.close_fiscal_year(saved_fy.id)
        
        # 3. Validation
        # 3.1 Next FY
        assert next_fy is not None
        assert next_fy.period_number == 2
        assert next_fy.start_date == date(2026, 4, 1)
        
        # 3.2 Current FY Status
        closed_fy = await master_service.get_fiscal_year_by_id(saved_fy.id)
        assert closed_fy.status == "CLOSED"
        
        # 3.3 Opening Transaction
        txs = await journal_service.get_entries(start_date=next_fy.start_date, end_date=next_fy.start_date)
        opening_tx = next((t for t in txs if t.description == "前期繰越"), None)
        
        assert opening_tx is not None
        
        # Validate Lines
        lines = opening_tx.lines
        
        # Cash (12000 Dr)
        l_cash = next((tx_line for tx_line in lines if tx_line.account_id == acc_cash.id), None)
        assert l_cash is not None
        assert l_cash.debit == 12000
        assert l_cash.credit == 0
        
        # Capital (5000 Cr)
        l_cap = next((tx_line for tx_line in lines if tx_line.account_id == acc_capital.id), None)
        assert l_cap is not None
        assert l_cap.debit == 0
        assert l_cap.credit == 5000
        
        # Retained Earnings (7000 Cr)
        l_re = next((tx_line for tx_line in lines if tx_line.account_id == acc_re.id), None)
        assert l_re is not None
        assert l_re.debit == 0
        assert l_re.credit == 7000
        
        # No PL items
        assert not any(tx_line.account_id == acc_sales.id for tx_line in lines)
        assert not any(tx_line.account_id == acc_expense.id for tx_line in lines)
