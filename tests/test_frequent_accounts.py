import sys
import os

# Ensure project root AND app dir are in path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
app_dir = os.path.join(root_dir, 'app')
sys.path.append(root_dir)
sys.path.append(app_dir)

import pytest  # noqa: E402
from datetime import date  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker  # noqa: E402

# Ensure app is in path
from pathlib import Path  # noqa: E402
import sys  # noqa: E402
app_dir = str(Path(__file__).parent.parent / "app")
sys.path.append(app_dir)

# Import App Modules
# Assuming 'app' is in path, we can import directly
from infrastructure.db.models import Base, AccountTable  # noqa: E402
from infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository  # noqa: E402
from application.services.journal_service import JournalService  # noqa: E402
from domain.models.transaction import Transaction, TransactionLine  # noqa: E402

# Test Config
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_session():
    """Context manager for test database session."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    
    # Init Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        yield session
        
    await engine.dispose()

@pytest.mark.asyncio
async def test_frequent_accounts_manual_wiring(test_session):
    """
    Test frequent account logic by manually wiring up the Service and Repository 
    against an in-memory database.
    """
    session = test_session
    
    # 1. Manual Dependency Injection
    repo = SQLAlchemyLedgerRepository(session)
    journal_service = JournalService(repo)
    
    # 2. Setup Data (Directly via ORM for speed/reliability in setup phase)
    # Accounts
    acc_a = AccountTable(code="9001", name="Freq A", type="Expense")
    acc_b = AccountTable(code="9002", name="Freq B", type="Expense")
    acc_c = AccountTable(code="9003", name="Rare C", type="Expense")
    acc_d = AccountTable(code="9004", name="Deleted D", type="Expense")
    acc_cash = AccountTable(code="1001", name="Cash", type="Asset") # For balancing
    
    session.add_all([acc_a, acc_b, acc_c, acc_d, acc_cash])
    await session.flush()
    
    id_a, id_b, id_c, id_d = acc_a.id, acc_b.id, acc_c.id, acc_d.id
    id_cash = acc_cash.id
    
    # 3. Execute Logic via Service
    
    async def add_via_service(account_ids, is_deleted=False):
        # Create debit lines for target accounts
        lines = [TransactionLine(account_id=aid, debit=100, credit=0) for aid in account_ids]
        
        # Calculate total debit
        total_debit = sum(100 for _ in account_ids)
        
        # Add balancing credit line (Cash)
        lines.append(TransactionLine(account_id=id_cash, debit=0, credit=total_debit))
        
        tx = Transaction(
            date=date.today(),
            description="Test",
            lines=lines
        )
        tx_id = await journal_service.add_journal_entry(tx)
        
        if is_deleted:
            await journal_service.delete_entry(tx_id)
            
    # Frequent Pattern
    # A: 3, B: 2, C: 1, D: 5 (deleted)
    # Cash will be used many times, but we will ignore it in verification or accept it as top 1 if limit logic allows.
    # Actually, Cash will be the MOST frequent.
    # A: 3 txs -> 3 lines
    # B: 2 txs -> 2 lines
    # C: 1 tx -> 1 line
    # Cash: 3+2+1+5 = 11 lines (Wait, deleted D doesn't count for frequent)
    # Cash non-deleted = 1+1+1+1 = 4 txs usage?
    # Tx1(A,B): Cash 1
    # Tx2(A,B): Cash 1
    # Tx3(A): Cash 1
    # Tx4(C): Cash 1
    # Total Cash valid = 4.
    # Total A valid = 3.
    # Total B valid = 2.
    
    # So order will be: Cash(4), A(3), B(2)
    # If we limit=3, we get [Cash, A, B]. 
    # If we limit=2, we get [Cash, A].
    # We want to verify A and B are detected. 
    # Let's request limit=3 and check order.
    
    await add_via_service([id_a, id_b])      # A:1, B:1, Cash:1
    await add_via_service([id_a, id_b])      # A:2, B:2, Cash:2
    await add_via_service([id_a])            # A:3, Cash:3
    await add_via_service([id_c])            # C:1, Cash:4
    
    for _ in range(5):
        await add_via_service([id_d], is_deleted=True)
        
    # 4. Verify
    # Expect: Cash(4), A(3), B(2)
    frequent_ids = await journal_service.get_frequent_account_ids(limit=3)
    
    # Map back to codes for clarity in failure message
    print(f"Frequent IDs: {frequent_ids}")
    
    assert len(frequent_ids) == 3
    assert frequent_ids[0] == id_cash
    assert frequent_ids[1] == id_a
    assert frequent_ids[2] == id_b
    assert id_d not in frequent_ids
