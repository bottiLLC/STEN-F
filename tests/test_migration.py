import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.infrastructure.db.session import init_db


@pytest.mark.asyncio
async def test_auto_migration_backup_path(tmp_path, mocker):
    """Ensure that the database migration automatically adds the backup_path column if it is missing."""
    import app.infrastructure.db.session as session_mod

    original_database_url = settings.DATABASE_URL
    original_engine = session_mod.engine

    temp_db_file = tmp_path / "test_migration.db"
    temp_db_url = f"sqlite+aiosqlite:///{temp_db_file}"

    # Setup original database URL
    settings.DATABASE_URL = temp_db_url
    # Create a new engine for the temp DB and patch the session module's engine
    temp_engine = create_async_engine(temp_db_url)
    session_mod.engine = temp_engine

    try:
        # 1. Create a raw legacy database structure without backup_path
        async with temp_engine.begin() as conn:
            # Create a simple system_config table with only id and ai_api_key
            await conn.execute(
                text(
                    "CREATE TABLE system_config ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "ai_api_key TEXT"
                    ")"
                )
            )
            # Insert a dummy row to simulate existing user settings
            await conn.execute(
                text("INSERT INTO system_config (ai_api_key) VALUES ('test-key')")
            )

        # 2. Run init_db() which contains our auto-migration script
        await init_db()

        # 3. Verify that the backup_path column was successfully added
        # If the column was not added, selecting it will raise an error.
        async with temp_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT backup_path FROM system_config LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            # The column should be present and hold NULL (None) for the existing row
            assert row[0] is None

    finally:
        # Restore settings and engine
        settings.DATABASE_URL = original_database_url
        session_mod.engine = original_engine
        await temp_engine.dispose()
