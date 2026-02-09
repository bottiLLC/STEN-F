import asyncio
import sys
import os

# Add v2/app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infrastructure.db.models import engine
from infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from sqlalchemy.ext.asyncio import AsyncSession

async def debug():
    print("Starting Debug...")
    async with AsyncSession(engine) as session:
        repo = SQLAlchemyLedgerRepository(session)
        
        # 1. Accounts
        accounts = await repo.get_accounts()
        print(f"Total Accounts: {len(accounts)}")
        
        # 2. Check each account
        for a in accounts:
            # Simple check for a few known accounts or all
            txs = await repo.get_transactions_by_account(a.id)
            if len(txs) > 0:
                print(f"Account [{a.code}] {a.name} (ID: {a.id}): Found {len(txs)} transactions.")
                first_tx = txs[0]
                print(f"  First TX ID: {first_tx.id}, Date: {first_tx.date}")
                print(f"  Lines: {len(first_tx.lines)}")
                for l in first_tx.lines:
                    print(f"    - Line ID: {l.id}, AccID: {l.account_id}, Dr: {l.debit}, Cr: {l.credit}")
            else:
                pass
                # print(f"Account [{a.code}] {a.name} (ID: {a.id}): No transactions.")

    print("Debug Finished.")

if __name__ == "__main__":
    asyncio.run(debug())
