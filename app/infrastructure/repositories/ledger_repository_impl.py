from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.interfaces.i_ledger_repository import ILedgerRepository
from domain.models.account import Account
from domain.models.transaction import Transaction, TransactionLine
from infrastructure.db.models import AccountTable, TransactionTable, TransactionLineTable

class SQLAlchemyLedgerRepository(ILedgerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_accounts(self) -> List[Account]:
        """
        Retrieves all accounts ordered by code.
        """
        stmt = select(AccountTable).order_by(AccountTable.code)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [Account.model_validate(row) for row in rows]

    async def get_transactions(self, start_date: Optional[date] = None, end_date: Optional[date] = None, include_deleted: bool = False, include_relationships: bool = False) -> List[Transaction]:
        """
        Retrieves transactions with optional date filtering and deletion status.
        """
        stmt = select(TransactionTable)
        
        if include_relationships:
            from infrastructure.db.models import TransactionLineTable
            stmt = stmt.options(selectinload(TransactionTable.lines).selectinload(TransactionLineTable.account))
        else:
            stmt = stmt.options(selectinload(TransactionTable.lines))
        
        if not include_deleted:
            stmt = stmt.where(TransactionTable.is_deleted.is_(False))
        
        if start_date:
            stmt = stmt.where(TransactionTable.date >= start_date)
        if end_date:
            stmt = stmt.where(TransactionTable.date <= end_date)
            
        stmt = stmt.order_by(TransactionTable.date, TransactionTable.id)
        
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        
        # Mapping to Domain Models
        domain_txs = []
        for row in rows:
            lines = []
            for l in row.lines:
                line_domain = TransactionLine(
                    id=l.id,
                    account_id=l.account_id,
                    debit=l.debit,
                    credit=l.credit
                )
                if include_relationships and l.account:
                    line_domain.account = Account.model_validate(l.account)
                lines.append(line_domain)

            domain_txs.append(Transaction(
                id=row.id,
                date=row.date,
                description=row.description or "",
                lines=lines,
                is_deleted=row.is_deleted,
                deleted_at=row.deleted_at,
                counterparty=row.counterparty,
                invoice_number=row.invoice_number,
                evidence_path=row.evidence_path
            ))
        return domain_txs

    async def get_transactions_by_account(self, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, include_deleted: bool = False) -> List[Transaction]:
        """
        Retrieves transactions involving a specific account.
        """
        # 1. Get Transaction IDs associated with this account
        stmt_ids = select(TransactionLineTable.transaction_id).join(TransactionTable).where(TransactionLineTable.account_id == account_id)
        
        if not include_deleted:
            stmt_ids = stmt_ids.where(TransactionTable.is_deleted.is_(False))

        stmt_ids = stmt_ids.distinct()
        
        result_ids = await self.session.execute(stmt_ids)
        tx_ids = result_ids.scalars().all()
        
        if not tx_ids:
            return []

        # 2. Fetch Transactions with Lines
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
            
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        
        # Mapping to Domain Models
        domain_txs = []
        for row in rows:
            lines = [
                TransactionLine(
                    id=l.id,
                    account_id=l.account_id,
                    debit=l.debit,
                    credit=l.credit
                ) for l in row.lines
            ]
            domain_txs.append(Transaction(
                id=row.id,
                date=row.date,
                description=row.description or "",
                lines=lines,
                is_deleted=row.is_deleted,
                deleted_at=row.deleted_at,
                counterparty=row.counterparty,
                invoice_number=row.invoice_number,
                evidence_path=row.evidence_path
            ))
        return domain_txs


    async def add_transaction(self, transaction: Transaction) -> int:
        db_tx = TransactionTable(
            date=transaction.date,
            description=transaction.description,
            is_deleted=False,
            counterparty=transaction.counterparty,
            invoice_number=transaction.invoice_number,
            evidence_path=transaction.evidence_path
        )
        self.session.add(db_tx)
        await self.session.flush() # to get ID
        
        for line in transaction.lines:
            db_line = TransactionLineTable(
                transaction_id=db_tx.id,
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit
            )
            self.session.add(db_line)
            
        # No Commit here! Unit of Work pattern requires Service to commit.
        return db_tx.id

    async def update_transaction(self, transaction: Transaction) -> bool:
        stmt = select(TransactionTable).where(TransactionTable.id == transaction.id).options(selectinload(TransactionTable.lines))
        result = await self.session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        
        if not db_tx:
            return False
            
        # Update Header
        db_tx.date = transaction.date
        db_tx.description = transaction.description
        db_tx.counterparty = transaction.counterparty
        db_tx.invoice_number = transaction.invoice_number
        if transaction.evidence_path: # Only update if provided? Or always? Assuming overwrite.
             db_tx.evidence_path = transaction.evidence_path
             
        # Update Lines (Replace strategy)
        # Clear existing lines
        db_tx.lines = []
        
        # Add new lines
        for line in transaction.lines:
            db_line = TransactionLineTable(
                transaction_id=db_tx.id,
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit
            )
            # No session.add needed if appended to relationship? 
            # SQLAlchemy handles it if appended to db_tx.lines
            # But let's be explicit with list assignment above or append.
            db_tx.lines.append(db_line)
            
        return True

    async def has_transactions_for_account(self, account_id: int) -> bool:
        stmt = select(TransactionLineTable).where(TransactionLineTable.account_id == account_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete_transaction(self, transaction_id: int) -> bool:
        stmt = select(TransactionTable).where(TransactionTable.id == transaction_id)
        result = await self.session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        if db_tx:
            db_tx.is_deleted = True
            db_tx.deleted_at = datetime.now()
            await self.session.commit()
            return True
        return False

    async def get_trial_balance_data(self, fiscal_year_id: int) -> List[dict]:
        """
        Calculates total debit and credit for each account within a fiscal year.
        Returns a list of dictionaries with account_id, total_debit, and total_credit.
        """
        # 1. Get FY Dates
        from infrastructure.db.models import FiscalYearTable
        stmt = select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id)
        result = await self.session.execute(stmt)
        fy = result.scalar_one_or_none()
        if not fy:
            return []
            
        # 2. Aggregation
        stmt = (
            select(
                TransactionLineTable.account_id,
                func.sum(TransactionLineTable.debit).label("total_debit"),
                func.sum(TransactionLineTable.credit).label("total_credit")
            )
            .join(TransactionTable, TransactionTable.id == TransactionLineTable.transaction_id)
            .where(TransactionTable.date >= fy.start_date)
            .where(TransactionTable.date <= fy.end_date)
            .where(TransactionTable.is_deleted.is_(False))
            .group_by(TransactionLineTable.account_id)
        )
        
        result = await self.session.execute(stmt)
        return [
            {
                "account_id": row.account_id,
                "total_debit": row.total_debit or 0,
                "total_credit": row.total_credit or 0
            } 
            for row in result.all()
        ]

    async def get_fiscal_year(self, fiscal_year_id: int):
        from infrastructure.db.models import FiscalYearTable
        from domain.models.fiscal_year import FiscalYear
        
        stmt = select(FiscalYearTable).where(FiscalYearTable.id == fiscal_year_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return FiscalYear.model_validate(row)
        return None

    async def commit(self):
        await self.session.commit()

    async def update_evidence_path(self, transaction_id: int, path: str) -> bool:
        stmt = select(TransactionTable).where(TransactionTable.id == transaction_id)
        result = await self.session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        if db_tx:
            db_tx.evidence_path = path
            # We don't commit here, ensuring atomic transaction with previous add
            return True
        return False

    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]:
        """
        Get IDs of frequently used accounts.
        Based on occurance in TransactionLineTable, associated with non-deleted transactions.
        """
        stmt = (
            select(TransactionLineTable.account_id)
            .join(TransactionTable, TransactionTable.id == TransactionLineTable.transaction_id)
            .where(TransactionTable.is_deleted.is_(False))
            .group_by(TransactionLineTable.account_id)
            .order_by(func.count(TransactionLineTable.account_id).desc())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
