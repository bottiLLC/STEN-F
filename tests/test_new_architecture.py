import pytest
from datetime import date
from domain.models.transaction import Transaction, TransactionLine

@pytest.mark.asyncio
async def test_journal_service_flow(container):
    """
    Verify the full flow: Service -> Repository -> Limit (Async)
    Uses the 'container' fixture from conftest.py which initializes DB.
    """
    # 1. Use the new scoped container
    async with container.journal_service_scope() as service:
        
        # 2. Need valid Account IDs. Use Master Service to fetch seeded accounts.
        async with container.master_service_scope() as master_service:
            # Fixture seeds accounts, so they should exist.
            accounts = await master_service.get_accounts()
            assert len(accounts) >= 2, "Seeding failed? Need at least 2 accounts."
            acc1 = accounts[0]
            acc2 = accounts[1]
            
        # 3. Create a Transaction
        tx = Transaction(
            date=date.today(),
            description="Test Transaction",
            lines=[
                TransactionLine(account_id=acc1.id, debit=1000, credit=0), 
                TransactionLine(account_id=acc2.id, debit=0, credit=1000)
            ],
            counterparty="Test Client",
            invoice_number="T1234567890123"
        )

        # 4. Add
        tx_id = await service.add_journal_entry(tx)
        assert tx_id is not None
        
        # 5. Fetch
        entries = await service.get_entries()
        assert len(entries) >= 1
        saved_tx = next((e for e in entries if e.id == tx_id), None)
        assert saved_tx is not None
        assert saved_tx.description == "Test Transaction"
        assert saved_tx.invoice_number == "T1234567890123"
        assert saved_tx.lines[0].debit == 1000

@pytest.mark.asyncio
async def test_master_service_flow(container):
    async with container.master_service_scope() as service:
        # Test Corporation Save/Get
        from domain.models.corporation import Corporation
        corp = Corporation(name="Test Corp Updated")
        await service.save_corporation(corp)
        
        saved = await service.get_corporation()
        assert saved.name == "Test Corp Updated"
