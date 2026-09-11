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

from datetime import date
import pytest

from app.container import Container
from app.domain_contracts import Account, AccountType, Corporation, FiscalYear
from app.storage_repository import Base, engine, init_db


@pytest.fixture(scope="function")
async def container():
    """Provides an isolated Container instance with clean schema and seed data for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await init_db()

    c = Container()

    async with c.master_service_scope() as ms:
        today = date.today()
        await ms.save_fiscal_year(
            FiscalYear(
                name=f"FY{today.year}",
                start_date=date(today.year, 1, 1),
                end_date=date(today.year, 12, 31),
                status="OPEN",
                period_number=1,
            )
        )
        await ms.save_corporation(Corporation(name="Test Corp", address="Test Address"))
        await ms.save_account(
            Account(
                code="1110",
                name="現金",
                type=AccountType.CURRENT_ASSET,
                description="Cash",
            )
        )
        await ms.save_account(
            Account(
                code="4110",
                name="売上高",
                type=AccountType.REVENUE,
                description="Sales",
            )
        )

    yield c
