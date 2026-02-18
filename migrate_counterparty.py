
import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Match models.py path logic
DEFAULT_DB_PATH = Path(".").absolute() / "bookkeeping.db" # Check current dir first for script execution
if not DEFAULT_DB_PATH.exists():
     # Try parent
     DEFAULT_DB_PATH = Path("../../../bookkeeping.db")

DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"

async def migrate():
    print(f"Migrating database at: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Add default_account_id column
        try:
            await conn.execute(text("ALTER TABLE counterparties ADD COLUMN default_account_id INTEGER"))
            print("Added default_account_id column.")
        except Exception as e:
            print(f"Column default_account_id might already exist: {e}")
            
        # Drop default_account_type column? 
        # SQLite logic often requires table recreation for DROP COLUMN in older versions, 
        # but newer SQLite supports it. Let's try or ignore.
        try:
            await conn.execute(text("ALTER TABLE counterparties DROP COLUMN default_account_type"))
            print("Dropped default_account_type column.")
        except Exception as e:
            print(f"Could not drop default_account_type (might define default value or not supported): {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
