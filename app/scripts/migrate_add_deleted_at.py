import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add app to path
sys.path.append(str(Path(__file__).parents[2]))

from app.infrastructure.db.session import DATABASE_URL

async def migrate():
    print(f"Migrating database at: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        try:
            # Check if column exists (simple check strictly for SQLite)
            # This is a bit hacky but works for this specific task without proper migration tool
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN deleted_at DATETIME"))
            print("Added deleted_at column successfully.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print("Column deleted_at already exists.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
