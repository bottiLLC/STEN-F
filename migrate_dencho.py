import asyncio
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Configuration
DB_FILE = Path("bookkeeping.db")
BACKUP_DIR = Path("backups_migration")

def backup_database():
    """Creates a timestamped backup of the database."""
    if not DB_FILE.exists():
        print(f"Database file {DB_FILE} not found. Skipping backup.")
        return

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"bookkeeping_{timestamp}.db"
    
    print(f"Backing up database to {backup_path}...")
    shutil.copy2(DB_FILE, backup_path)
    print("Backup complete.")

async def migrate_schema():
    """Applies schema changes for Dencho Act compliance."""
    # Use direct sqlite3 for DDL to avoid async overhead complexity for simple migrations,
    # or use SQLAlchemy text execution. Let's use sqlite3 for simplicity in DDL execution.
    # Actually, let's use the async engine pattern to be consistent with the app, 
    # but strictly speaking sqlite3 standard lib is fine for this one-off.
    
    # We'll use sqlite3 for synchronous simplicity and reliability in this script.
    print(f"Connecting to database: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # 1. Create counterparties table
        print("Creating table 'counterparties'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_kana TEXT,
                invoice_number TEXT UNIQUE,
                default_account_type TEXT
            )
        """)

        # 2. Alter transactions table
        print("Altering table 'transactions'...")
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        # Add is_deleted
        if 'is_deleted' not in columns:
            print("  Adding column 'is_deleted'...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
        
        # Add counterparty
        if 'counterparty' not in columns:
            print("  Adding column 'counterparty'...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN counterparty TEXT")

        # Add evidence_path
        if 'evidence_path' not in columns:
            print("  Adding column 'evidence_path'...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN evidence_path TEXT")

        # Check deleted_at (Should exist from previous work, but ensure)
        if 'deleted_at' not in columns:
            print("  Adding column 'deleted_at'...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN deleted_at TIMESTAMP")

        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting migration for Electronic Books Preservation Act...")
    backup_database()
    # Run sync migration func
    if DB_FILE.exists():
        asyncio.run(asyncio.to_thread(migrate_schema)) # Just wrapping in asyncio run for consistency if we expanded
    else:
        # If DB doesn't exist, models.py will create it properly on next app run with new definitions.
        # But we should probably create the empty db? No, let app handle init if missing.
        print("Database file does not exist. Please run the application to initialize the database first, or ensure path is correct.")
        # Actually simplest to just let the app init. 
        # But if the user expects this script to Upgrade an existing DB, we proceed.
        pass
