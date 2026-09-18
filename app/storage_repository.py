# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from collections.abc import AsyncGenerator
import datetime
from pathlib import Path
from typing import Final, TypeVar
from sqlalchemy import ForeignKey, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
)

from app.core_foundation import log, settings
from app.domain_contracts import (
    DEFAULT_ACCOUNTS,
    Abstract,
    Account,
    Corporation,
    Counterparty,
    FiscalYear,
    ILedgerRepository,
    IMasterRepository,
    SystemSettings,
    Transaction,
    TransactionLine,
    TrialBalanceRawRow,
)


# --- 1. Datum Plane (ORM Schemas & Engine Binding) ---
DATABASE_URL: Final[str] = (
    settings.DATABASE_URL
    or f"sqlite+aiosqlite:///{settings.PROJECT_ROOT / 'data' / settings.DB_NAME}"
)
engine: Final[AsyncEngine] = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal: Final[async_sessionmaker[AsyncSession]] = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    """Declarative base class for SQLAlchemy entity models."""

    pass


ModelT = TypeVar("ModelT", bound=Base)


class AccountTable(Base):
    """Database table schema for accounts."""

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)


class CorporationTable(Base):
    """Database table schema for company corporation profile."""

    __tablename__ = "corporation"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str | None] = mapped_column(nullable=True)
    representative_title: Mapped[str | None] = mapped_column(nullable=True)
    representative_name: Mapped[str | None] = mapped_column(nullable=True)


class CounterpartyTable(Base):
    """Database table schema for vendor and customer master entries."""

    __tablename__ = "counterparties"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    name_kana: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    debit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    credit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    description_template: Mapped[str | None] = mapped_column(nullable=True)


class FiscalYearTable(Base):
    """Database table schema for accounting periods."""

    __tablename__ = "fiscal_years"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="OPEN")
    period_number: Mapped[int | None] = mapped_column(nullable=True)


class AbstractTable(Base):
    """Database table schema for recurring transaction abstracts."""

    __tablename__ = "abstracts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    account: Mapped[AccountTable] = relationship("AccountTable")


class TransactionTable(Base):
    """Database table schema for double-entry transactions."""

    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    counterparty: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(nullable=True)
    lines: Mapped[list[TransactionLineTable]] = relationship(
        "TransactionLineTable",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )


class TransactionLineTable(Base):
    """Database table schema for split transaction lines."""

    __tablename__ = "transaction_lines"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    debit: Mapped[int] = mapped_column(default=0)
    credit: Mapped[int] = mapped_column(default=0)
    transaction: Mapped[TransactionTable] = relationship(
        "TransactionTable", back_populates="lines"
    )
    account: Mapped[AccountTable] = relationship("AccountTable")


class SystemTable(Base):
    """Database table schema for application configuration settings."""

    __tablename__ = "system_config"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ai_api_key: Mapped[str | None] = mapped_column(nullable=True)
    backup_path: Mapped[str | None] = mapped_column(nullable=True)


# --- 2. Internal Pure Transformations ---
def _to_domain_transaction(row: TransactionTable) -> Transaction:
    """Transform ORM TransactionTable instance into Pydantic domain model.

    Args:
        row: TransactionTable ORM instance with loaded lines.

    Returns:
        Domain Transaction instance.
    """
    lines = [
        TransactionLine(
            id=line.id, account_id=line.account_id, debit=line.debit, credit=line.credit
        )
        for line in row.lines
    ]
    return Transaction(
        id=row.id,
        date=row.date,
        description=row.description or "",
        lines=lines,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        counterparty=row.counterparty,
        invoice_number=row.invoice_number,
        evidence_path=row.evidence_path,
    )


# --- 3. Public Orchestration Layer ---
async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Initialize SQLite schema and execute auto-migration for missing columns.

    Args:
        target_engine: Optional explicit AsyncEngine instance.
    """
    eng = target_engine or engine
    db_url = str(eng.url) if hasattr(eng, "url") else (settings.DATABASE_URL or "")
    if db_url and "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("SELECT backup_path FROM system_config LIMIT 1"))
        except Exception:
            try:
                await conn.execute(
                    text("ALTER TABLE system_config ADD COLUMN backup_path TEXT")
                )
            except Exception as e:
                log.warning("db_migration_skip", column="backup_path", error=str(e))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield managed async session instance.

    Yields:
        Active AsyncSession for database operations.
    """
    async with AsyncSessionLocal() as session:
        yield session


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
        row.name, row.name_kana = (
            cp.name,
            getattr(cp, "reading", None) or getattr(cp, "name_kana", None),
        )
        row.invoice_number = cp.invoice_number or None
        row.debit_account_id = getattr(cp, "debit_account_id", None)
        row.credit_account_id = getattr(cp, "credit_account_id", None)
        row.description_template = getattr(cp, "description_template", None)
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
        """Find counterparty by fuzzy name substring.

        Args:
            keyword: Substring to match against counterparty name.

        Returns:
            Matched Counterparty model or None.
        """
        res = await self.session.execute(
            select(CounterpartyTable)
            .where(CounterpartyTable.name.ilike(f"%{keyword}%"))
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


class SQLAlchemyLedgerRepository(ILedgerRepository):
    """Concrete persistence implementation for journal and ledger transactions."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind session to ledger repository instance.

        Args:
            session: Active AsyncSession instance.
        """
        self.session = session

    async def get_accounts(self) -> list[Account]:
        """Fetch account catalog for ledger presentation.

        Returns:
            List of Account domain models.
        """
        res = await self.session.execute(
            select(AccountTable).order_by(AccountTable.code)
        )
        return [Account.model_validate(r) for r in res.scalars().all()]

    async def get_transactions(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        include_deleted: bool = False,
        include_relationships: bool = False,
    ) -> list[Transaction]:
        """Fetch transactions filtered by date range and deletion flag.

        Args:
            start_date: Optional inclusive start date filter.
            end_date: Optional inclusive end date filter.
            include_deleted: Whether to include logically deleted transactions.
            include_relationships: Whether to eagerly load account relationships.

        Returns:
            List of Transaction domain models.
        """
        stmt = select(TransactionTable)
        if include_relationships:
            stmt = stmt.options(
                selectinload(TransactionTable.lines).selectinload(
                    TransactionLineTable.account
                )
            )
        else:
            stmt = stmt.options(selectinload(TransactionTable.lines))

        if not include_deleted:
            stmt = stmt.where(TransactionTable.is_deleted.is_(False))
        if start_date:
            stmt = stmt.where(TransactionTable.date >= start_date)
        if end_date:
            stmt = stmt.where(TransactionTable.date <= end_date)

        stmt = stmt.order_by(TransactionTable.date.desc(), TransactionTable.id.desc())
        res = await self.session.execute(stmt)
        return [_to_domain_transaction(r) for r in res.scalars().all()]

    async def get_transactions_by_account(
        self,
        account_id: int,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        include_deleted: bool = False,
    ) -> list[Transaction]:
        """Fetch transactions matching specified account id within date range.

        Args:
            account_id: Target account ID.
            start_date: Optional inclusive start date filter.
            end_date: Optional inclusive end date filter.
            include_deleted: Whether to include logically deleted transactions.

        Returns:
            List of Transaction domain models.
        """
        stmt_ids = (
            select(TransactionLineTable.transaction_id)
            .join(TransactionTable)
            .where(TransactionLineTable.account_id == account_id)
        )
        if not include_deleted:
            stmt_ids = stmt_ids.where(TransactionTable.is_deleted.is_(False))

        tx_ids = (await self.session.execute(stmt_ids.distinct())).scalars().all()
        if not tx_ids:
            return []

        stmt = (
            select(TransactionTable)
            .where(TransactionTable.id.in_(tx_ids))
            .options(selectinload(TransactionTable.lines))
            .order_by(TransactionTable.date, TransactionTable.id)
        )
        if start_date:
            stmt = stmt.where(TransactionTable.date >= start_date)
        if end_date:
            stmt = stmt.where(TransactionTable.date <= end_date)

        res = await self.session.execute(stmt)
        return [_to_domain_transaction(r) for r in res.scalars().all()]

    async def add_transaction(self, transaction: Transaction) -> int:
        """Persist newly composed balanced journal transaction.

        Args:
            transaction: Validated Transaction domain model.

        Returns:
            Database primary key ID of created transaction.
        """
        db_tx = TransactionTable(
            date=transaction.date,
            description=transaction.description,
            is_deleted=False,
            counterparty=transaction.counterparty,
            invoice_number=transaction.invoice_number,
            evidence_path=transaction.evidence_path,
        )
        self.session.add(db_tx)
        await self.session.flush()

        for line in transaction.lines:
            self.session.add(
                TransactionLineTable(
                    transaction_id=db_tx.id,
                    account_id=line.account_id,
                    debit=line.debit,
                    credit=line.credit,
                )
            )
        return db_tx.id

    async def update_transaction(self, transaction: Transaction) -> bool:
        """Update existing journal entry header and replace transaction lines.

        Args:
            transaction: Transaction domain model with updated fields.

        Returns:
            True if transaction was updated, False if not found.
        """
        res = await self.session.execute(
            select(TransactionTable)
            .where(TransactionTable.id == transaction.id)
            .options(selectinload(TransactionTable.lines))
        )
        db_tx = res.scalar_one_or_none()
        if not db_tx:
            return False

        db_tx.date, db_tx.description = transaction.date, transaction.description
        db_tx.counterparty, db_tx.invoice_number = (
            transaction.counterparty,
            transaction.invoice_number,
        )
        if transaction.evidence_path:
            db_tx.evidence_path = transaction.evidence_path

        db_tx.lines = [
            TransactionLineTable(
                transaction_id=db_tx.id,
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit,
            )
            for line in transaction.lines
        ]
        return True

    async def has_transactions_for_account(self, account_id: int) -> bool:
        """Check if any transaction line references account id.

        Args:
            account_id: Target account ID.

        Returns:
            True if account has linked transactions, False otherwise.
        """
        res = await self.session.execute(
            select(TransactionLineTable)
            .where(TransactionLineTable.account_id == account_id)
            .limit(1)
        )
        return res.scalar_one_or_none() is not None

    async def delete_transaction(self, transaction_id: int) -> bool:
        """Soft delete journal transaction record.

        Args:
            transaction_id: Primary key of transaction to mark deleted.

        Returns:
            True if transaction was marked deleted, False if not found.
        """
        res = await self.session.execute(
            select(TransactionTable)
            .where(TransactionTable.id == transaction_id)
            .options(selectinload(TransactionTable.lines))
        )
        db_tx = res.scalar_one_or_none()
        if db_tx:
            db_tx.is_deleted = True
            db_tx.deleted_at = datetime.datetime.now()
            await self.session.commit()
            return True
        return False

    async def get_trial_balance_data(
        self, fiscal_year_id: int
    ) -> list[TrialBalanceRawRow]:
        """Aggregate total debit and credit amounts per account within fiscal period.

        Args:
            fiscal_year_id: Fiscal period identifier.

        Returns:
            List of aggregate dictionaries containing account_id, total_debit, total_credit.
        """
        res = await self.session.execute(
            select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id)
        )
        fy = res.scalar_one_or_none()
        if not fy:
            return []

        agg_stmt = (
            select(
                TransactionLineTable.account_id,
                func.sum(TransactionLineTable.debit).label("total_debit"),
                func.sum(TransactionLineTable.credit).label("total_credit"),
            )
            .join(
                TransactionTable,
                TransactionTable.id == TransactionLineTable.transaction_id,
            )
            .where(
                TransactionTable.date >= fy.start_date,
                TransactionTable.date <= fy.end_date,
                TransactionTable.is_deleted.is_(False),
            )
            .group_by(TransactionLineTable.account_id)
        )
        res = await self.session.execute(agg_stmt)
        return [
            {
                "account_id": r.account_id,
                "total_debit": r.total_debit or 0,
                "total_credit": r.total_credit or 0,
            }
            for r in res.all()
        ]

    async def get_fiscal_year(self, fiscal_year_id: int) -> FiscalYear | None:
        """Fetch fiscal year definition by id.

        Args:
            fiscal_year_id: Fiscal year ID.

        Returns:
            FiscalYear domain model or None.
        """
        res = await self.session.execute(
            select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id)
        )
        row = res.scalar_one_or_none()
        return FiscalYear.model_validate(row) if row else None

    async def commit(self) -> None:
        """Explicitly commit pending session transaction."""
        await self.session.commit()

    async def update_evidence_path(self, transaction_id: int, path: str) -> bool:
        """Update linked evidence document path on transaction record.

        Args:
            transaction_id: Primary key of target transaction.
            path: Storage file system path.

        Returns:
            True if updated, False if transaction not found.
        """
        res = await self.session.execute(
            select(TransactionTable).where(TransactionTable.id == transaction_id)
        )
        db_tx = res.scalar_one_or_none()
        if db_tx:
            db_tx.evidence_path = path
            return True
        return False

    async def get_frequent_account_ids(self, limit: int = 5) -> list[int]:
        """Retrieve most frequently utilized account ids.

        Args:
            limit: Maximum count of account ids to return.

        Returns:
            List of account IDs ranked by usage frequency.
        """
        stmt = (
            select(TransactionLineTable.account_id)
            .join(
                TransactionTable,
                TransactionTable.id == TransactionLineTable.transaction_id,
            )
            .where(TransactionTable.is_deleted.is_(False))
            .group_by(TransactionLineTable.account_id)
            .order_by(func.count(TransactionLineTable.account_id).desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


async def seed_accounts_with_service(
    service: IMasterRepository,
) -> None:
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
