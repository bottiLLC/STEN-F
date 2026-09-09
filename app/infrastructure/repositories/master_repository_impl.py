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

from typing import Any, List, Optional, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.interfaces.i_master_repository import IMasterRepository
from app.domain.models.abstract import Abstract
from app.domain.models.account import Account
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.system import SystemSettings
from app.infrastructure.db.models import (
    AbstractTable,
    AccountTable,
    CorporationTable,
    CounterpartyTable,
    FiscalYearTable,
    SystemTable,
)


class SQLAlchemyMasterRepository(IMasterRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _delete_by_id(self, model_cls: Type[Any], entity_id: int) -> bool:
        stmt = select(model_cls).where(model_cls.id == entity_id)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        if row:
            await self.session.delete(row)
            await self.session.commit()
            return True
        return False

    async def _save_and_refresh(self, entity: Any) -> Any:
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def get_system_settings(self) -> SystemSettings:
        res = await self.session.execute(select(SystemTable).limit(1))
        row = res.scalar_one_or_none() or await self._save_and_refresh(SystemTable())
        return SystemSettings.model_validate(row)

    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        res = await self.session.execute(select(SystemTable).limit(1))
        row = res.scalar_one_or_none() or SystemTable()
        row.ai_api_key, row.backup_path = settings.ai_api_key, settings.backup_path
        return SystemSettings.model_validate(await self._save_and_refresh(row))

    async def get_corporation(self) -> Optional[Corporation]:
        res = await self.session.execute(select(CorporationTable).limit(1))
        row = res.scalar_one_or_none()
        return Corporation.model_validate(row) if row else None

    async def save_corporation(self, corp: Corporation) -> Corporation:
        res = await self.session.execute(select(CorporationTable).limit(1))
        row = res.scalar_one_or_none() or CorporationTable()
        row.name, row.address = corp.name, corp.address
        row.representative_name, row.representative_title = corp.representative_name, corp.representative_title
        return Corporation.model_validate(await self._save_and_refresh(row))

    async def get_fiscal_years(self) -> List[FiscalYear]:
        res = await self.session.execute(select(FiscalYearTable).order_by(FiscalYearTable.start_date.desc()))
        return [FiscalYear.model_validate(r) for r in res.scalars().all()]

    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]:
        res = await self.session.execute(select(FiscalYearTable).where(FiscalYearTable.id == fy_id))
        row = res.scalar_one_or_none()
        return FiscalYear.model_validate(row) if row else None

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        row = None
        if fy.id:
            res = await self.session.execute(select(FiscalYearTable).where(FiscalYearTable.id == fy.id))
            row = res.scalar_one_or_none()
        row = row or FiscalYearTable()
        row.name, row.start_date, row.end_date = fy.name, fy.start_date, fy.end_date
        row.status, row.period_number = fy.status, fy.period_number
        return FiscalYear.model_validate(await self._save_and_refresh(row))

    async def delete_fiscal_year(self, fy_id: int) -> bool:
        return await self._delete_by_id(FiscalYearTable, fy_id)

    async def get_accounts(self) -> List[Account]:
        res = await self.session.execute(select(AccountTable).order_by(AccountTable.code))
        return [Account.model_validate(r) for r in res.scalars().all()]

    async def save_account(self, account: Account) -> Account:
        row = None
        if account.id:
            res = await self.session.execute(select(AccountTable).where(AccountTable.id == account.id))
            row = res.scalar_one_or_none()
        row = row or AccountTable()
        row.code, row.name, row.type, row.description = account.code, account.name, account.type.value, account.description
        return Account.model_validate(await self._save_and_refresh(row))

    async def delete_account(self, account_id: int) -> bool:
        return await self._delete_by_id(AccountTable, account_id)

    async def get_abstracts(self) -> List[Abstract]:
        res = await self.session.execute(select(AbstractTable).options(selectinload(AbstractTable.account)))
        out = []
        for r in res.scalars().all():
            d = Abstract.model_validate(r)
            if r.account:
                d.account_name = r.account.name
            out.append(d)
        return out

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        row = None
        if abstract.id:
            res = await self.session.execute(select(AbstractTable).where(AbstractTable.id == abstract.id))
            row = res.scalar_one_or_none()
        row = row or AbstractTable()
        row.account_id, row.text = abstract.account_id, abstract.text
        return Abstract.model_validate(await self._save_and_refresh(row))

    async def delete_abstract(self, abs_id: int) -> bool:
        return await self._delete_by_id(AbstractTable, abs_id)

    async def save_counterparty(self, cp: Counterparty) -> Counterparty:
        row = None
        if cp.id:
            res = await self.session.execute(select(CounterpartyTable).where(CounterpartyTable.id == cp.id))
            row = res.scalar_one_or_none()
        elif cp.invoice_number:
            res = await self.session.execute(select(CounterpartyTable).where(CounterpartyTable.invoice_number == cp.invoice_number))
            row = res.scalar_one_or_none()
        elif cp.name:
            res = await self.session.execute(select(CounterpartyTable).where(CounterpartyTable.name == cp.name))
            row = res.scalar_one_or_none()

        row = row or CounterpartyTable()
        row.name, row.name_kana = cp.name, cp.name_kana
        row.invoice_number = cp.invoice_number or None
        row.debit_account_id, row.credit_account_id = cp.debit_account_id, cp.credit_account_id
        row.description_template = cp.description_template
        return Counterparty.model_validate(await self._save_and_refresh(row))

    async def get_counterparties(self) -> List[Counterparty]:
        res = await self.session.execute(select(CounterpartyTable).order_by(CounterpartyTable.name))
        return [Counterparty.model_validate(r) for r in res.scalars().all()]

    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]:
        res = await self.session.execute(
            select(CounterpartyTable).where(CounterpartyTable.name.ilike(f"%{keyword}%")).limit(1)
        )
        row = res.scalar_one_or_none()
        return Counterparty.model_validate(row) if row else None

    async def delete_counterparty(self, cp_id: int) -> bool:
        return await self._delete_by_id(CounterpartyTable, cp_id)
