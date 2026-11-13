# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""SQLAlchemy persistence package facade maintaining backward-compatible imports."""

from __future__ import annotations

from app.storage_repository.database import (
    DATABASE_URL,
    AbstractTable,
    AccountTable,
    AsyncSessionLocal,
    Base,
    CorporationTable,
    CounterpartyTable,
    FiscalYearTable,
    ModelT,
    SystemTable,
    TransactionLineTable,
    TransactionTable,
    engine,
    init_db,
    migrate_legacy_data_to_data_dir,
)
from app.storage_repository.ledger_repository import (
    SQLAlchemyLedgerRepository,
    _to_domain_transaction,
)
from app.storage_repository.master_repository import (
    SQLAlchemyMasterRepository,
    seed_accounts,
    seed_accounts_with_service,
)

__all__ = [
    "DATABASE_URL",
    "AbstractTable",
    "AccountTable",
    "AsyncSessionLocal",
    "Base",
    "CorporationTable",
    "CounterpartyTable",
    "FiscalYearTable",
    "ModelT",
    "SQLAlchemyLedgerRepository",
    "SQLAlchemyMasterRepository",
    "SystemTable",
    "TransactionLineTable",
    "TransactionTable",
    "_to_domain_transaction",
    "engine",
    "init_db",
    "migrate_legacy_data_to_data_dir",
    "seed_accounts",
    "seed_accounts_with_service",
]
