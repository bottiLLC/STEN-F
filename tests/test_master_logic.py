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
from domain.models.counterparty import Counterparty
from domain.models.account import Account, AccountType
from domain.models.transaction import Transaction, TransactionLine
from datetime import date

@pytest.mark.asyncio
class TestMasterLogic:
    
    async def test_counterparty_lifecycle(self, container):
        """Test Create, Read, Update, Delete for Counterparty"""
        from contextlib import AsyncExitStack
        async with AsyncExitStack() as stack:
            master_service = await stack.enter_async_context(container.master_service_scope())
        
            # 1. Create
            cp = Counterparty(name="Logic Test Corp", invoice_number="T1111222233334")
            saved = await master_service.save_counterparty(cp)
            assert saved.id is not None
            assert saved.name == "Logic Test Corp"
            
            # 2. Read (via list)
            cps = await master_service.get_counterparties()
            assert any(c.id == saved.id for c in cps)
            
            # 3. Update
            saved.name = "Logic Test Corp Updated"
            updated = await master_service.save_counterparty(saved)
            assert updated.id == saved.id
            assert updated.name == "Logic Test Corp Updated"
            
            # Verify Update in DB
            cps_after = await master_service.get_counterparties()
            target = next((c for c in cps_after if c.id == saved.id), None)
            assert target is not None
            assert target.name == "Logic Test Corp Updated"
            
            # 4. Delete
            await master_service.delete_counterparty(saved.id)
            
            # Verify Deletion
            cps_final = await master_service.get_counterparties()
            assert not any(c.id == saved.id for c in cps_final)

    async def test_account_deletion_constraint(self, container):
        """Test that Account cannot be deleted if used in a Transaction"""
        from contextlib import AsyncExitStack
        async with AsyncExitStack() as stack:
            master_service = await stack.enter_async_context(container.master_service_scope())
            journal_service = await stack.enter_async_context(container.journal_service_scope())
        
            # 1. Create a specific account for this test
            acc = Account(code="999", name="Test Constraint", type=AccountType.SGA, description="For testing")
            await master_service.save_account(acc)
            
            accounts = await master_service.get_accounts()
            target_acc = next(a for a in accounts if a.code == "999")
            
            # 2. Use it in a transaction
            tx = Transaction(
                date=date.today(),
                description="Constraint Test TX",
                lines=[
                    TransactionLine(account_id=target_acc.id, debit=100, credit=0),
                    # Need a balancing line, use default cash/sales or just another dummy? 
                    # System doesn't strictly enforce balance at repo level yet, but good practice.
                    # Let's just use same account reversed for simplicity or fetching another.
                    TransactionLine(account_id=target_acc.id, debit=0, credit=100)
                ]
            )
            await journal_service.add_journal_entry(tx)
            
            # 3. Attempt to delete account -> Should Fail
            with pytest.raises(ValueError) as excinfo:
                await master_service.delete_account(target_acc.id)
            
            assert "仕訳で使用されているため" in str(excinfo.value)

