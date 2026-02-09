from typing import List, Optional
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.interfaces.i_ledger_repository import ILedgerRepository
from domain.models.account import Account, AccountType
from domain.models.transaction import Transaction, TransactionLine
from infrastructure.db.models import AccountTable, TransactionTable, TransactionLineTable

class SQLAlchemyLedgerRepository(ILedgerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_accounts(self) -> List[Account]:
        stmt = select(AccountTable).order_by(AccountTable.code)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [Account.model_validate(row) for row in rows]

    async def get_transactions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        stmt = select(TransactionTable).options(selectinload(TransactionTable.lines))
        
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
                lines=lines
            ))
        return domain_txs

    async def get_transactions_by_account(self, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        # 1. Get Transaction IDs associated with this account
        stmt_ids = select(TransactionLineTable.transaction_id).where(TransactionLineTable.account_id == account_id).distinct()
        
        # Note: We can iterate/filter by date here if we join TransactionTable, 
        # but simpler to filter in step 2 if the volume is low-medium (which it is for this app).
        
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
                lines=lines
            ))
        return domain_txs


    async def add_transaction(self, transaction: Transaction) -> int:
        db_tx = TransactionTable(
            date=transaction.date,
            description=transaction.description
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
            
        await self.session.commit()
        await self.session.refresh(db_tx)
        return db_tx.id

    async def delete_transaction(self, transaction_id: int) -> bool:
        stmt = select(TransactionTable).where(TransactionTable.id == transaction_id)
        result = await self.session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        if db_tx:
            await self.session.delete(db_tx)
            await self.session.commit()
            return True
        return False

    async def get_trial_balance_data(self, fiscal_year_id: int) -> List[dict]:
        # This requires joining with Fiscal Year logically, but usually we filter by date range.
        # For this example, we assume we fetch dates from Service first or pass dates here.
        # But V1 logic uses explicit SQL.
        # Let's assume the service calculates dates passed to a cleaner method, OR we implement finding FY here.
        # To keep it simple and clean, let's say we pass the start/end date logic to repo or service.
        # The Interface asks for `fiscal_year_id`. Let's allow passing dates for "Trial Balance" logic or fetch FY.
        # Let's simple query `fiscal_years` table to get dates first inside this method? 
        # Or better, `get_trial_balance_data_by_date_range`.
        # Adhering to interface:
        
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
