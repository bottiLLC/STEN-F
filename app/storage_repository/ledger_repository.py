# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain_contracts import (
    Account,
    FiscalYear,
    ILedgerRepository,
    Transaction,
    TransactionLine,
    TrialBalanceRawRow,
)
from app.storage_repository.database import (
    AccountTable,
    FiscalYearTable,
    TransactionLineTable,
    TransactionTable,
)


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
    occ_date = row.occurred_at or row.date
    rec_dt = row.recorded_at or datetime.datetime.now(datetime.timezone.utc)
    return Transaction(
        id=row.id,
        occurred_at=occ_date,
        recorded_at=rec_dt,
        description=row.description or "",
        lines=lines,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        counterparty=row.counterparty,
        invoice_number=row.invoice_number,
        evidence_path=row.evidence_path,
        reversed_transaction_id=getattr(row, "reversed_transaction_id", None),
    )


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

        tx_date_col = func.coalesce(TransactionTable.occurred_at, TransactionTable.date)
        if not include_deleted:
            stmt = stmt.where(TransactionTable.is_deleted.is_(False))
        if start_date:
            stmt = stmt.where(tx_date_col >= start_date)
        if end_date:
            stmt = stmt.where(tx_date_col <= end_date)

        stmt = stmt.order_by(tx_date_col.desc(), TransactionTable.id.desc())
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

        tx_date_col = func.coalesce(TransactionTable.occurred_at, TransactionTable.date)
        stmt = (
            select(TransactionTable)
            .where(TransactionTable.id.in_(tx_ids))
            .options(selectinload(TransactionTable.lines))
            .order_by(tx_date_col, TransactionTable.id)
        )
        if start_date:
            stmt = stmt.where(tx_date_col >= start_date)
        if end_date:
            stmt = stmt.where(tx_date_col <= end_date)

        res = await self.session.execute(stmt)
        return [_to_domain_transaction(r) for r in res.scalars().all()]

    async def add_transaction(self, transaction: Transaction) -> int:
        """Persist newly composed balanced journal transaction under Dual-Timestamp invariant.

        Args:
            transaction: Validated Transaction domain model.

        Returns:
            Database primary key ID of created transaction.
        """
        total_debit = sum(line.debit for line in transaction.lines)
        total_credit = sum(line.credit for line in transaction.lines)
        if total_debit != total_credit or not transaction.lines:
            raise ValueError(
                f"Zero-Tolerance Balance Violation (Rule 2): Debit({total_debit}) != Credit({total_credit})"
            )

        occ_date = transaction.occurred_at or transaction.date
        if occ_date is None:
            raise ValueError("Transaction requires occurred_at or date")
        rec_dt = transaction.recorded_at or datetime.datetime.now(datetime.timezone.utc)
        db_tx = TransactionTable(
            occurred_at=occ_date,
            recorded_at=rec_dt,
            date=occ_date,
            description=transaction.description,
            is_deleted=False,
            counterparty=transaction.counterparty,
            invoice_number=transaction.invoice_number,
            evidence_path=transaction.evidence_path,
            reversed_transaction_id=transaction.reversed_transaction_id,
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

    async def reverse_transaction(
        self,
        original_tx_id: int,
        reason: str = "誤謬取消",
        occurred_at: datetime.date | None = None,
    ) -> int:
        """Rectify error solely by creating a new reversing entry (red slip) under Rule 1.

        Args:
            original_tx_id: Primary key of transaction to reverse.
            reason: Cancellation reason string.
            occurred_at: Optional reversing occurrence date (defaults to original occurrence date).

        Returns:
            Created reversing transaction ID.

        Raises:
            ValueError: If original transaction not found.
        """
        res = await self.session.execute(
            select(TransactionTable)
            .where(TransactionTable.id == original_tx_id)
            .options(selectinload(TransactionTable.lines))
        )
        orig = res.scalar_one_or_none()
        if not orig:
            raise ValueError(f"仕訳ID {original_tx_id} が見つかりません。")

        reversing_date = occurred_at or orig.occurred_at or orig.date
        rev_desc = f"[取消: {reason}] {orig.description or ''}".strip()

        rev_lines = [
            TransactionLine(
                account_id=line.account_id,
                debit=line.credit,
                credit=line.debit,
            )
            for line in orig.lines
        ]
        rev_tx = Transaction(
            occurred_at=reversing_date,
            description=rev_desc,
            lines=rev_lines,
            counterparty=orig.counterparty,
            invoice_number=orig.invoice_number,
            reversed_transaction_id=original_tx_id,
        )
        return await self.add_transaction(rev_tx)

    async def update_transaction(self, transaction: Transaction) -> bool:
        """Prohibited by Rule 1 (Absolute Immutability)."""
        raise NotImplementedError(
            "UPDATE operations on Journal Entries are strictly prohibited by Rule 1 (Absolute Immutability). "
            "Rectify transactions solely by inserting reversing entries via reverse_transaction."
        )

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
        """Prohibited by Rule 1 (Absolute Immutability)."""
        raise NotImplementedError(
            "DELETE operations on Journal Entries are strictly prohibited by Rule 1 (Absolute Immutability). "
            "Rectify transactions solely by inserting reversing entries via reverse_transaction."
        )

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

        tx_date_col = func.coalesce(TransactionTable.occurred_at, TransactionTable.date)
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
                tx_date_col >= fy.start_date,
                tx_date_col <= fy.end_date,
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
        """Prohibited by Rule 1 (Absolute Immutability). Use add_journal_entry_with_evidence."""
        raise NotImplementedError(
            "UPDATE operations on Journal Entries are strictly prohibited by Rule 1 (Absolute Immutability). "
            "Evidence paths must be bound at initial append via add_journal_entry_with_evidence."
        )
