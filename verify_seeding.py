import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.ui.di import DI
# We will use the implementation in reflex_main implicitly or manually call seed_accounts
from app.infrastructure.db.seed_data import seed_accounts
from sqlalchemy.future import select
from app.infrastructure.db.session import AsyncSessionLocal
from app.domain.models.account import Account

async def verify_seeding():
    print("=== Verifying Account Seeding ===")
    
    # 1. Run Seeding Logic
    await seed_accounts()
    
    # 2. Verify Accounts Exist
    async with DI.get_master_service() as service:
        accounts = await service.get_accounts()
        count = len(accounts)
        print(f"Total Accounts: {count}")
        
        cash = next((a for a in accounts if a.code == "1111"), None)
        sales = next((a for a in accounts if a.code == "4111"), None)
        expense = next((a for a in accounts if a.code == "6111"), None)
        
        if cash and sales and expense:
            print("SUCCESS: Default accounts found.")
            print(f"  - {cash.code}: {cash.name}")
            print(f"  - {sales.code}: {sales.name}")
            print(f"  - {expense.code}: {expense.name}")
        else:
            print("FAILURE: Default accounts missing.")
            
if __name__ == "__main__":
    asyncio.run(verify_seeding())
