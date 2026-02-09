import asyncio
import sys
import os
from sqlalchemy import select, delete

# Add v2/app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from container import Container
from infrastructure.db.models import TransactionTable, FiscalYearTable

async def cleanup_test_data():
    print("🧹 Cleaning up leftover test data...")
    container = Container()
    session = await container.db.get_session()
    
    async with session:
        # Delete Transactions
        stmt = delete(TransactionTable).where(TransactionTable.description == "SYSTEM_VERIFICATION_TEST_TRANSACTION")
        result = await session.execute(stmt)
        print(f"✅ Deleted {result.rowcount} test transactions.")
        
        # Delete FY
        stmt_fy = delete(FiscalYearTable).where(FiscalYearTable.name == "VERIFICATION_FY")
        result_fy = await session.execute(stmt_fy)
        print(f"✅ Deleted {result_fy.rowcount} test fiscal years.")
        
        await session.commit()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(cleanup_test_data())
