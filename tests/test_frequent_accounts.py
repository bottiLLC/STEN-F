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
# Import App Modules
from app.infrastructure.db.models import Base, AccountTable  # noqa: E402
from app.infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository  # noqa: E402
from app.application.services.journal_service import JournalService  # noqa: E402
from app.domain.models.transaction import Transaction, TransactionLine  # noqa: E402

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
    
    from unittest.mock import AsyncMock, patch
    from app.ui.di import DI
    
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
    
    id_cash = acc_cash.id
    
    # Mocking MasterService for validation
    mock_master_service = AsyncMock()
    
    from app.domain.models.fiscal_year import FiscalYear
    import datetime
    today = date.today()
    mock_master_service.get_fiscal_years.return_value = [
        FiscalYear(name="Test", start_date=today - datetime.timedelta(days=365), end_date=today + datetime.timedelta(days=365), status="OPEN")
    ]
    
    class MockDIContextManager:
        async def __aenter__(self):
            return mock_master_service
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # 3. Execute Logic via Service
    
    @patch.object(DI, 'get_master_service', return_value=MockDIContextManager())
    async def run_test(mock_di):
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
    
    await run_test()
