# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core_foundation import log
from app.domain_contracts import (
    DEFAULT_ACCOUNTS,
    Abstract,
    Account,
    Corporation,
    Counterparty,
    FiscalYear,
    IMasterRepository,
    SystemSettings,
)
from app.storage_repository.database import (
    AbstractTable,
    AccountTable,
    AsyncSessionLocal,
    Base,
    CorporationTable,
    CounterpartyTable,
    FiscalYearTable,
    ModelT,
    SystemTable,
    init_db,
)


class SQLAlchemyMasterRepository(IMasterRepository):
    """Concrete persistence implementation for master entities."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind session to repository instance.

        Args:
            session: Active AsyncSession instance.
        """
        self.session = session

    async def _get_by_id(
        self, model_cls: type[ModelT], entity_id: int | None
    ) -> ModelT | None:
        """Fetch single entity by primary key.

        Args:
            model_cls: Target DeclarativeBase table class.
            entity_id: Primary key identifier.

        Returns:
            ORM row instance or None.
        """
        if not entity_id:
            return None
        res = await self.session.execute(
            select(model_cls).where(getattr(model_cls, "id") == entity_id)
        )
        return res.scalar_one_or_none()

    async def _delete_by_id(self, model_cls: type[Base], entity_id: int) -> bool:
        """Delete single entity by primary key.

        Args:
            model_cls: Target DeclarativeBase table class.
            entity_id: Primary key identifier.

        Returns:
            True if entity was deleted, False if not found.
        """
        row = await self._get_by_id(model_cls, entity_id)
        if row:
            await self.session.delete(row)
            await self.session.commit()
            return True
        return False

    async def _save_and_refresh(self, entity: ModelT) -> ModelT:
        """Persist, commit, and refresh entity state.

        Args:
            entity: ORM table instance to save.

        Returns:
            Refreshed entity instance.
        """
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def get_system_settings(self) -> SystemSettings:
        """Fetch singleton system configuration row.

        Returns:
            SystemSettings domain instance.
        """
        res = await self.session.execute(select(SystemTable).limit(1))
        row = res.scalar_one_or_none() or await self._save_and_refresh(SystemTable())
        return SystemSettings.model_validate(row)

    async def save_system_settings(self, stg: SystemSettings) -> SystemSettings:
        """Update and commit system configuration attributes.

        Args:
            stg: SystemSettings domain instance with updated values.

        Returns:
            Persisted SystemSettings instance.
        """
        res = await self.session.execute(select(SystemTable).limit(1))
        row = res.scalar_one_or_none() or SystemTable()
        row.ai_api_key, row.backup_path = stg.ai_api_key, stg.backup_path
        return SystemSettings.model_validate(await self._save_and_refresh(row))

    async def get_corporation(self) -> Corporation | None:
        """Fetch corporate profile record.

        Returns:
            Corporation profile or None.
        """
        res = await self.session.execute(select(CorporationTable).limit(1))
        row = res.scalar_one_or_none()
        return Corporation.model_validate(row) if row else None

    async def save_corporation(self, corp: Corporation) -> Corporation:
        """Save corporate profile information.

        Args:
            corp: Corporation domain instance.

        Returns:
            Persisted Corporation instance.
        """
        res = await self.session.execute(select(CorporationTable).limit(1))
        row = res.scalar_one_or_none() or CorporationTable()
        row.name, row.address = corp.name, corp.address
        row.representative_name = corp.representative_name
        row.representative_title = corp.representative_title
        row.invoice_number = corp.invoice_number
        return Corporation.model_validate(await self._save_and_refresh(row))

    async def get_fiscal_years(self) -> list[FiscalYear]:
        """Fetch all fiscal years ordered chronologically descending.

        Returns:
            List of FiscalYear domain models.
        """
        res = await self.session.execute(
            select(FiscalYearTable).order_by(FiscalYearTable.start_date.desc())
        )
        return [FiscalYear.model_validate(r) for r in res.scalars().all()]

    async def get_fiscal_year(self, fy_id: int) -> FiscalYear | None:
        """Fetch fiscal year by identifier.

        Args:
            fy_id: Fiscal year ID.

        Returns:
            FiscalYear domain model or None.
        """
        row = await self._get_by_id(FiscalYearTable, fy_id)
        return FiscalYear.model_validate(row) if row else None

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        """Save or update fiscal year boundary.

        Args:
            fy: FiscalYear domain model.

        Returns:
            Persisted FiscalYear instance.
        """
        row = (await self._get_by_id(FiscalYearTable, fy.id)) or FiscalYearTable()
        row.name, row.start_date, row.end_date = fy.name, fy.start_date, fy.end_date
        row.status, row.period_number = fy.status, fy.period_number
        return FiscalYear.model_validate(await self._save_and_refresh(row))

    async def delete_fiscal_year(self, fy_id: int) -> bool:
        """Delete fiscal year by identifier.

        Args:
            fy_id: Target fiscal year ID.

        Returns:
            True if deleted, False otherwise.
        """
        return await self._delete_by_id(FiscalYearTable, fy_id)

    async def get_accounts(self) -> list[Account]:
        """Fetch all accounts ordered by account code.

        Returns:
            List of Account domain models.
        """
        res = await self.session.execute(
            select(AccountTable).order_by(AccountTable.code)
        )
        return [Account.model_validate(r) for r in res.scalars().all()]

    async def save_account(self, account: Account) -> Account:
        """Save or update account definition.

        Args:
            account: Account domain model.

        Returns:
            Persisted Account instance.
        """
        row = (await self._get_by_id(AccountTable, account.id)) or AccountTable()
        row.code, row.name, row.type = account.code, account.name, account.type.value
        row.description = account.description
        return Account.model_validate(await self._save_and_refresh(row))

    async def delete_account(self, account_id: int) -> bool:
        """Delete account definition by identifier.

        Args:
            account_id: Target account ID.

        Returns:
            True if deleted, False otherwise.
        """
        return await self._delete_by_id(AccountTable, account_id)

    async def get_abstracts(self) -> list[Abstract]:
        """Fetch all predefined abstracts with linked account names.

        Returns:
            List of Abstract domain models.
        """
        res = await self.session.execute(
            select(AbstractTable).options(selectinload(AbstractTable.account))
        )
        out: list[Abstract] = []
        for r in res.scalars().all():
            d = Abstract.model_validate(r)
            if r.account:
                setattr(d, "account_name", r.account.name)
            out.append(d)
        return out

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        """Save or update transaction abstract template.

        Args:
            abstract: Abstract domain model.

        Returns:
            Persisted Abstract instance.
        """
        row = (await self._get_by_id(AbstractTable, abstract.id)) or AbstractTable()
        row.account_id, row.text = abstract.account_id, abstract.text
        return Abstract.model_validate(await self._save_and_refresh(row))

    async def delete_abstract(self, abs_id: int) -> bool:
        """Delete transaction abstract template.

        Args:
            abs_id: Target abstract ID.

        Returns:
            True if deleted, False otherwise.
        """
        return await self._delete_by_id(AbstractTable, abs_id)

    async def save_counterparty(self, cp: Counterparty) -> Counterparty:
        """Save counterparty record with invoice and name collision resolution.

        Args:
            cp: Counterparty domain model.

        Returns:
            Persisted Counterparty instance.
        """
        row = await self._get_by_id(CounterpartyTable, cp.id)
        if not row and cp.invoice_number:
            res = await self.session.execute(
                select(CounterpartyTable).where(
                    CounterpartyTable.invoice_number == cp.invoice_number
                )
            )
            row = res.scalar_one_or_none()
        if not row and cp.name:
            res = await self.session.execute(
                select(CounterpartyTable).where(CounterpartyTable.name == cp.name)
            )
            row = res.scalar_one_or_none()

        row = row or CounterpartyTable()
        row.name, row.name_kana = cp.name, cp.name_kana
        row.trade_name = cp.trade_name
        row.invoice_number = cp.invoice_number or None
        row.debit_account_id = getattr(cp, "debit_account_id", None)
        row.credit_account_id = getattr(cp, "credit_account_id", None)
        row.description_template = getattr(cp, "description_template", None)
        row.tel = getattr(cp, "tel", None)
        row.tax_rate = getattr(cp, "tax_rate", None)
        return Counterparty.model_validate(await self._save_and_refresh(row))

    async def get_counterparties(self) -> list[Counterparty]:
        """Fetch all counterparty profiles.

        Returns:
            List of Counterparty domain models.
        """
        res = await self.session.execute(
            select(CounterpartyTable).order_by(CounterpartyTable.name)
        )
        return [Counterparty.model_validate(r) for r in res.scalars().all()]

    async def get_counterparty_by_keyword(self, keyword: str) -> Counterparty | None:
        """Find counterparty by fuzzy match across name, kana, trade name, or invoice number.

        Args:
            keyword: Substring or registration number to search.

        Returns:
            Matched Counterparty model or None.
        """
        kw = keyword.strip()
        if not kw:
            return None
        inv_match = f"T{kw}" if kw.isdigit() and len(kw) == 13 else kw
        res = await self.session.execute(
            select(CounterpartyTable)
            .where(
                or_(
                    CounterpartyTable.name.ilike(f"%{kw}%"),
                    CounterpartyTable.name_kana.ilike(f"%{kw}%"),
                    CounterpartyTable.trade_name.ilike(f"%{kw}%"),
                    CounterpartyTable.invoice_number == inv_match,
                )
            )
            .limit(1)
        )
        row = res.scalar_one_or_none()
        return Counterparty.model_validate(row) if row else None

    async def delete_counterparty(self, cp_id: int) -> bool:
        """Delete counterparty by identifier.

        Args:
            cp_id: Target counterparty ID.

        Returns:
            True if deleted, False otherwise.
        """
        return await self._delete_by_id(CounterpartyTable, cp_id)


async def seed_accounts_with_service(service: IMasterRepository) -> None:
    """Sync missing default standard accounts using provided repository.

    Args:
        service: IMasterRepository implementation.
    """
    existing = await service.get_accounts()
    existing_codes = {acc.code for acc in existing}
    added_count = 0
    for acc_data in DEFAULT_ACCOUNTS:
        if acc_data["code"] not in existing_codes:
            await service.save_account(Account(**acc_data))
            added_count += 1
    if added_count > 0:
        log.info("default_accounts_synced", count=added_count)


async def seed_accounts() -> None:
    """Initialize database schema and seed default standard accounts."""
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = SQLAlchemyMasterRepository(session)
        await seed_accounts_with_service(repo)
