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

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Default DB Path (Parent of app)
# Calculate path relative to THIS file: app/infrastructure/db/session.py -> app/infrastructure/db/ -> app/infrastructure/ -> app/ -> STEN-F/
DEFAULT_DB_PATH = Path(__file__).parents[3] / "data" / "sten_f.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}")

engine = create_async_engine(DATABASE_URL, echo=False)

async def init_db():
    from infrastructure.db.models import Base
    # Ensure the directory exists before creating the database
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
