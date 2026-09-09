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

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.models.account import Account
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.transaction import Transaction, TransactionLine
from app.infrastructure.db.models import (
    AccountTable,
    FiscalYearTable,
    TransactionLineTable,
    TransactionTable,
)


class SQLAlchemyLedgerRepository(ILedgerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_accounts(self) -> List[Account]:
        res = await self.session.execute(select(AccountTable).order_by(AccountTable.code))
        return [Account.model_validate(r) for r in res.scalars().all()]

    @staticmethod
    def _to_domain(row: TransactionTable) -> Transaction:
        lines = [
            TransactionLine(id=line.id, account_id=line.account_id, debit=line.debit, credit=line.credit)
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

    async def get_transactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
        include_relationships: bool = False,
    ) -> List[Transaction]:
        stmt = select(TransactionTable)
        if include_relationships:
            stmt = stmt.options(selectinload(TransactionTable.lines).selectinload(TransactionLineTable.account))
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
        return [self._to_domain(r) for r in res.scalars().all()]

    async def get_transactions_by_account(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
    ) -> List[Transaction]:
        stmt_ids = select(TransactionLineTable.transaction_id).join(TransactionTable).where(TransactionLineTable.account_id == account_id)
        if not include_deleted:
            stmt_ids = stmt_ids.where(TransactionTable.is_deleted.is_(False))

        tx_ids = (await self.session.execute(stmt_ids.distinct())).scalars().all()
        if not tx_ids:
            return []

        stmt = select(TransactionTable).where(TransactionTable.id.in_(tx_ids)).options(selectinload(TransactionTable.lines)).order_by(TransactionTable.date, TransactionTable.id)
        if start_date:
            stmt = stmt.where(TransactionTable.date >= start_date)
        if end_date:
            stmt = stmt.where(TransactionTable.date <= end_date)

        res = await self.session.execute(stmt)
        return [self._to_domain(r) for r in res.scalars().all()]

    async def add_transaction(self, tx: Transaction) -> int:
        db_tx = TransactionTable(
            date=tx.date,
            description=tx.description,
            is_deleted=False,
            counterparty=tx.counterparty,
            invoice_number=tx.invoice_number,
            evidence_path=tx.evidence_path,
        )
        self.session.add(db_tx)
        await self.session.flush()

        for line in tx.lines:
            self.session.add(
                TransactionLineTable(transaction_id=db_tx.id, account_id=line.account_id, debit=line.debit, credit=line.credit)
            )
        return db_tx.id

    async def update_transaction(self, tx: Transaction) -> bool:
        res = await self.session.execute(
            select(TransactionTable).where(TransactionTable.id == tx.id).options(selectinload(TransactionTable.lines))
        )
        db_tx = res.scalar_one_or_none()
        if not db_tx:
            return False

        db_tx.date, db_tx.description = tx.date, tx.description
        db_tx.counterparty, db_tx.invoice_number = tx.counterparty, tx.invoice_number
        if tx.evidence_path:
            db_tx.evidence_path = tx.evidence_path

        db_tx.lines = [
            TransactionLineTable(transaction_id=db_tx.id, account_id=line.account_id, debit=line.debit, credit=line.credit)
            for line in tx.lines
        ]
        return True

    async def has_transactions_for_account(self, account_id: int) -> bool:
        res = await self.session.execute(select(TransactionLineTable).where(TransactionLineTable.account_id == account_id).limit(1))
        return res.scalar_one_or_none() is not None

    async def delete_transaction(self, transaction_id: int) -> bool:
        res = await self.session.execute(select(TransactionTable).where(TransactionTable.id == transaction_id))
        db_tx = res.scalar_one_or_none()
        if db_tx:
            db_tx.is_deleted = True
            db_tx.deleted_at = datetime.now()
            await self.session.commit()
            return True
        return False

    async def get_trial_balance_data(self, fiscal_year_id: int) -> List[Dict[str, Any]]:
        res = await self.session.execute(select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id))
        fy = res.scalar_one_or_none()
        if not fy:
            return []

        agg_stmt = (
            select(
                TransactionLineTable.account_id,
                func.sum(TransactionLineTable.debit).label("total_debit"),
                func.sum(TransactionLineTable.credit).label("total_credit"),
            )
            .join(TransactionTable, TransactionTable.id == TransactionLineTable.transaction_id)
            .where(
                TransactionTable.date >= fy.start_date,
                TransactionTable.date <= fy.end_date,
                TransactionTable.is_deleted.is_(False),
            )
            .group_by(TransactionLineTable.account_id)
        )
        res = await self.session.execute(agg_stmt)
        return [
            {"account_id": r.account_id, "total_debit": r.total_debit or 0, "total_credit": r.total_credit or 0}
            for r in res.all()
        ]

    async def get_fiscal_year(self, fiscal_year_id: int) -> Optional[FiscalYear]:
        res = await self.session.execute(select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id))
        row = res.scalar_one_or_none()
        return FiscalYear.model_validate(row) if row else None

    async def commit(self) -> None:
        await self.session.commit()

    async def update_evidence_path(self, transaction_id: int, path: str) -> bool:
        res = await self.session.execute(select(TransactionTable).where(TransactionTable.id == transaction_id))
        db_tx = res.scalar_one_or_none()
        if db_tx:
            db_tx.evidence_path = path
            return True
        return False

    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]:
        stmt = (
            select(TransactionLineTable.account_id)
            .join(TransactionTable, TransactionTable.id == TransactionLineTable.transaction_id)
            .where(TransactionTable.is_deleted.is_(False))
            .group_by(TransactionLineTable.account_id)
            .order_by(func.count(TransactionLineTable.account_id).desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
