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

@pytest.mark.asyncio
async def test_journal_entry_update_flow(container):
    """Test full cycle of adding and then updating a journal entry."""
    
    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(container.master_service_scope())
        journal_service = await stack.enter_async_context(container.journal_service_scope())
        # ledger_service = await stack.enter_async_context(container.ledger_service_scope()) # Not used in test body?
        # Actually ledger_service is used implicitly? No, verified not used in verification step 5.
        # But let's check step 5. It uses journal_service.get_entries.
        # So ledger_service removal is safe if unused. 
        # Wait, reading code: `saved_txs = await journal_service.get_entries` line 55.
        # So ledger_service is unused. Removing to be clean.
    
        # 1. Setup Data: Get Accounts and Setup Fiscal Year
        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]
        
        # Setup OPEN fiscal year spanning today
        from app.domain.models.fiscal_year import FiscalYear
        import datetime
        today = date.today()
        fy = FiscalYear(
            name="Test FY",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN"
        )
        await master_service.save_fiscal_year(fy)

        
        # 2. Add New Transaction
        tx = Transaction(
            date=date.today(),
            description="Original Description",
            counterparty="Original CP",
            lines=[
                TransactionLine(account_id=acc1.id, debit=1000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=1000)
            ]
        )
        
        tx_id = await journal_service.add_journal_entry(tx)
        assert tx_id is not None
        
        # 3. Create Update Object
        # Fetch existing to get full object or construct new one with ID
        # Repository update usually requires full object, effectively replacing it.
        
        # We constructed it manually in UI, so let's do same here.
        updated_tx = Transaction(
            id=tx_id, # CRITICAL: ID Must match
            date=date.today(),
            description="Updated Description",
            counterparty="Updated CP",
            invoice_number="T1234567890123", # Adding new field
            lines=[
                # Changing amounts
                TransactionLine(account_id=acc1.id, debit=1200, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=1200)
            ]
        )
        
        # 4. Perform Update
        success = await journal_service.update_journal_entry(updated_tx)
        assert success is True
        
        # 5. Verify in DB via LedgerService/Repository
        saved_txs = await journal_service.get_entries(include_deleted=False)
        target = next((t for t in saved_txs if t.id == tx_id), None)
        
        assert target is not None
        assert target.description == "Updated Description"
        assert target.counterparty == "Updated CP"
        assert target.invoice_number == "T1234567890123"
        
        # Check Lines
        assert len(target.lines) == 2
        l1 = next(tx_line for tx_line in target.lines if tx_line.account_id == acc1.id)
        assert l1.debit == 1200
        
        # 6. Verify non-existent update fails
        fake_tx = Transaction(
            id=999999,
            date=date.today(),
            description="Ghost",
            lines=[]
        )
        success_fail = await journal_service.update_journal_entry(fake_tx)
        assert success_fail is False

