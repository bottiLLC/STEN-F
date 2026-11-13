# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from dataclasses import dataclass
import datetime
from decimal import Decimal
from pathlib import Path
import shutil
from typing import Final, TypeVar

from sqlalchemy import ForeignKey, Numeric, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core_foundation import log, settings


# --- 1. Datum Plane (ORM Schemas & Engine Binding) ---
DATABASE_URL: Final[str] = (
    settings.DATABASE_URL
    or f"sqlite+aiosqlite:///{settings.DATA_DIR / settings.DB_NAME}"
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
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)


class CounterpartyTable(Base):
    """Database table schema for vendor and customer master entries."""

    __tablename__ = "counterparties"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    name_kana: Mapped[str | None] = mapped_column(nullable=True)
    trade_name: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    debit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    credit_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    description_template: Mapped[str | None] = mapped_column(nullable=True)
    tel: Mapped[str | None] = mapped_column(nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)


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
    occurred_at: Mapped[datetime.date | None] = mapped_column(index=True, nullable=True)
    recorded_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    counterparty: Mapped[str | None] = mapped_column(nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(nullable=True)
    reversed_transaction_id: Mapped[int | None] = mapped_column(
        index=True, nullable=True
    )
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


@dataclass(frozen=True)
class _ColumnMigration:
    """Declarative specification for idempotent legacy SQLite column additions."""

    table: str
    column: str
    ddl: str
    backfill_sql: str | None = None


_COLUMN_MIGRATIONS: Final[tuple[_ColumnMigration, ...]] = (
    _ColumnMigration(
        table="system_config",
        column="backup_path",
        ddl="ALTER TABLE system_config ADD COLUMN backup_path TEXT",
    ),
    _ColumnMigration(
        table="corporation",
        column="invoice_number",
        ddl="ALTER TABLE corporation ADD COLUMN invoice_number TEXT",
    ),
    _ColumnMigration(
        table="counterparties",
        column="trade_name",
        ddl="ALTER TABLE counterparties ADD COLUMN trade_name TEXT",
    ),
    _ColumnMigration(
        table="counterparties",
        column="tel",
        ddl="ALTER TABLE counterparties ADD COLUMN tel TEXT",
    ),
    _ColumnMigration(
        table="counterparties",
        column="tax_rate",
        ddl="ALTER TABLE counterparties ADD COLUMN tax_rate NUMERIC(5, 4)",
    ),
    _ColumnMigration(
        table="transactions",
        column="occurred_at",
        ddl="ALTER TABLE transactions ADD COLUMN occurred_at DATE",
        backfill_sql="UPDATE transactions SET occurred_at = date WHERE occurred_at IS NULL",
    ),
    _ColumnMigration(
        table="transactions",
        column="recorded_at",
        ddl="ALTER TABLE transactions ADD COLUMN recorded_at TIMESTAMP",
        backfill_sql="UPDATE transactions SET recorded_at = CURRENT_TIMESTAMP WHERE recorded_at IS NULL",
    ),
    _ColumnMigration(
        table="transactions",
        column="reversed_transaction_id",
        ddl="ALTER TABLE transactions ADD COLUMN reversed_transaction_id INTEGER",
    ),
)


# --- 2. Legacy Migration & Initialization ---
def migrate_legacy_data_to_data_dir() -> None:
    """Migrate legacy root-level databases, storage files, backups, and configs into data/ directory."""
    data_dir = settings.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    target_db = data_dir / settings.DB_NAME
    if not target_db.exists():
        legacy_candidates = [
            settings.PROJECT_ROOT / "bookkeeping.db",
            settings.PROJECT_ROOT / "sten_f.db",
        ]
        for leg_db in legacy_candidates:
            if leg_db.exists():
                shutil.copy2(leg_db, target_db)
                log.info(
                    "legacy_db_migrated",
                    source=str(leg_db),
                    destination=str(target_db),
                )
                for ext in ("-wal", "-shm"):
                    leg_extra = leg_db.parent / f"{leg_db.name}{ext}"
                    if leg_extra.exists():
                        shutil.copy2(leg_extra, data_dir / f"{settings.DB_NAME}{ext}")
                break

    legacy_storage = settings.PROJECT_ROOT / "storage"
    if (
        legacy_storage.exists()
        and legacy_storage.is_dir()
        and legacy_storage.resolve() != settings.STORAGE_DIR.resolve()
    ):
        migrated_storage_files = 0
        for item in legacy_storage.iterdir():
            if item.is_file():
                dest = settings.STORAGE_DIR / item.name
                if not dest.exists():
                    shutil.copy2(item, dest)
                    migrated_storage_files += 1
        if migrated_storage_files > 0:
            log.info("legacy_storage_migrated", count=migrated_storage_files)

    legacy_backups = settings.PROJECT_ROOT / "backups"
    if (
        legacy_backups.exists()
        and legacy_backups.is_dir()
        and legacy_backups.resolve() != settings.BACKUP_DIR.resolve()
    ):
        migrated_backup_dirs = 0
        for item in legacy_backups.iterdir():
            dest = settings.BACKUP_DIR / item.name
            if not dest.exists():
                if item.is_dir():
                    shutil.copytree(item, dest)
                    migrated_backup_dirs += 1
                elif item.is_file():
                    shutil.copy2(item, dest)
                    migrated_backup_dirs += 1
        if migrated_backup_dirs > 0:
            log.info("legacy_backups_migrated", count=migrated_backup_dirs)

    root_env = settings.PROJECT_ROOT / ".env"
    data_env = settings.DATA_DIR / ".env"
    if root_env.exists() and not data_env.exists():
        shutil.copy2(root_env, data_env)
        log.info("env_config_mirrored_to_data", destination=str(data_env))


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Initialize SQLite schema and execute auto-migration for missing columns.

    Args:
        target_engine: Optional explicit AsyncEngine instance.
    """
    migrate_legacy_data_to_data_dir()
    eng = target_engine or engine
    db_url = str(eng.url) if hasattr(eng, "url") else (settings.DATABASE_URL or "")
    if db_url and "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for mig in _COLUMN_MIGRATIONS:
            try:
                await conn.execute(
                    text(f"SELECT {mig.column} FROM {mig.table} LIMIT 1")
                )
            except Exception:
                try:
                    await conn.execute(text(mig.ddl))
                    if mig.backfill_sql:
                        await conn.execute(text(mig.backfill_sql))
                except Exception as e:
                    log.warning("db_migration_skip", column=mig.column, error=str(e))
