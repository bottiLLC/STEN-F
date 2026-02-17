
import asyncio
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.db.models import AbstractTable, AccountTable
from sqlalchemy import select

async def check_abstracts():
    async with async_session_factory() as session:
        # Check Account ID for 'Cash' (Code 111 or similar)
        # Using name '現金'
        stmt = select(AccountTable).where(AccountTable.name == '現金')
        result = await session.execute(stmt)
        cash_acc = result.scalars().first()
        
        if not cash_acc:
            print("No 'Cash' (現金) account found.")
            return

        print(f"Cash Account: ID={cash_acc.id}, Code={cash_acc.code}")

        # Check Abstracts
        stmt = select(AbstractTable).where(AbstractTable.account_id == cash_acc.id)
        result = await session.execute(stmt)
        abstracts = result.scalars().all()
        
        print(f"Abstracts for Cash (count={len(abstracts)}):")
        for a in abstracts:
            print(f"- {a.text}")

        # Check all abstracts
        stmt = select(AbstractTable)
        result = await session.execute(stmt)
        all_abs = result.scalars().all()
        print(f"Total Abstracts in DB: {len(all_abs)}")

if __name__ == "__main__":
    asyncio.run(check_abstracts())
