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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pathlib import Path
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
assert DATABASE_URL is not None

engine = create_async_engine(DATABASE_URL, echo=False)


async def init_db():
    from app.infrastructure.db.models import Base

    # Ensure the directory exists before creating the database
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Auto-migration: Check if backup_path exists in system_config table
        try:
            # Try to select the column. If it doesn't exist, this will raise an OperationalError.
            await conn.execute(text("SELECT backup_path FROM system_config LIMIT 1"))
        except Exception:
            # Column likely does not exist, so try to add it
            try:
                await conn.execute(
                    text("ALTER TABLE system_config ADD COLUMN backup_path TEXT")
                )
            except Exception as e:
                import structlog

                structlog.get_logger().warning(
                    "Auto-migration of backup_path column failed", error=str(e)
                )


AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
