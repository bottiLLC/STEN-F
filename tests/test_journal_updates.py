import pytest
from datetime import date
from domain.models.transaction import Transaction, TransactionLine

@pytest.mark.asyncio
async def test_journal_entry_update_flow(container):
    """Test full cycle of adding and then updating a journal entry."""
    
    master_service = await container.get_master_service()
    journal_service = await container.get_journal_service()
    ledger_service = await container.get_ledger_service()
    
    # 1. Setup Data: Get Accounts
    accounts = await master_service.get_accounts()
    acc1 = accounts[0]
    acc2 = accounts[1]
    
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
        invoice_number="T99999", # Adding new field
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
    assert target.invoice_number == "T99999"
    
    # Check Lines
    assert len(target.lines) == 2
    l1 = next(l for l in target.lines if l.account_id == acc1.id)
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

