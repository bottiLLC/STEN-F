import pytest
import datetime
from domain.models.transaction import Transaction, TransactionLine
from domain.models.counterparty import Counterparty
# from app.container import Container (Removed, using fixture)

@pytest.mark.asyncio
async def test_dencho_compliance_features(container):
    # Container is provided by fixture
    
    
    # dependencies
    master_service = await container.get_master_service()
    journal_service = await container.get_journal_service()
    repo = await container.get_ledger_repository()
    
    # 1. Test Counterparty Upsert
    cp = Counterparty(name="Test Corp", invoice_number="T1234567890123", default_account_type="Travel")
    saved_cp = await master_service.save_counterparty(cp)
    assert saved_cp.id is not None
    assert saved_cp.name == "Test Corp"
    
    # Update same CP
    cp_update = Counterparty(name="Test Corp Updated", invoice_number="T1234567890123")
    updated_cp = await master_service.save_counterparty(cp_update)
    assert updated_cp.id == saved_cp.id
    assert updated_cp.name == "Test Corp Updated"

    # 2. Test Journal Entry with Evidence (Mocking FileService)
    class MockFileService:
        def save_evidence_for_transaction(self, file_bytes, transaction_id, date_obj, amount, corp_name):
            return f"/mock/storage/{date_obj}_{amount}_{corp_name}.pdf"

    tx = Transaction(
        date=datetime.date.today(),
        description="Test Invoice Transaction",
        counterparty="Test Corp Updated",
        lines=[
            TransactionLine(account_id=1, debit=1000, credit=0),
            TransactionLine(account_id=2, debit=0, credit=1000)
        ]
    )
    
    mock_file_service = MockFileService()
    file_bytes = b"fake pdf content"
    
    tx_id = await journal_service.add_journal_entry_with_evidence(tx, file_bytes, mock_file_service)
    assert tx_id is not None
    
    # Verify in DB
    saved_txs = await repo.get_transactions(include_deleted=True)
    target_tx = next((t for t in saved_txs if t.id == tx_id), None)
    assert target_tx is not None
    assert target_tx.counterparty == "Test Corp Updated"
    assert "Test Corp Updated" in target_tx.evidence_path
    assert target_tx.is_deleted is False

    # 3. Test Logical Deletion
    await journal_service.delete_entry(tx_id)
    
    # Verify deleted
    saved_txs_all = await repo.get_transactions(include_deleted=True)
    deleted_tx = next((t for t in saved_txs_all if t.id == tx_id), None)
    assert deleted_tx.is_deleted is True
    assert deleted_tx.deleted_at is not None
    
    # Verify defaults to hidden
    saved_txs_active = await repo.get_transactions(include_deleted=False)
    hidden_tx = next((t for t in saved_txs_active if t.id == tx_id), None)
    assert hidden_tx is None

    await container.shutdown()
