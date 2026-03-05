from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.interfaces.i_master_repository import IMasterRepository
from domain.models.corporation import Corporation
from domain.models.fiscal_year import FiscalYear
from domain.models.account import Account
from domain.models.abstract import Abstract
from domain.models.counterparty import Counterparty

from infrastructure.db.models import CorporationTable, FiscalYearTable, AccountTable, AbstractTable, CounterpartyTable

class SQLAlchemyMasterRepository(IMasterRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Corporation ---
    async def get_corporation(self) -> Optional[Corporation]:
        stmt = select(CorporationTable).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return Corporation.model_validate(row) if row else None

    async def save_corporation(self, corp: Corporation) -> Corporation:
        # Check if exists
        stmt = select(CorporationTable).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.name = corp.name
            existing.address = corp.address
            existing.representative_name = corp.representative_name
            existing.representative_title = corp.representative_title
            await self.session.commit()
            await self.session.refresh(existing)
            return Corporation.model_validate(existing)
        else:
            new_corp = CorporationTable(
                name=corp.name,
                address=corp.address,
                representative_name=corp.representative_name,
                representative_title=corp.representative_title
            )
            self.session.add(new_corp)
            await self.session.commit()
            await self.session.refresh(new_corp)
            return Corporation.model_validate(new_corp)

    # --- Fiscal Year ---
    async def get_fiscal_years(self) -> List[FiscalYear]:
        stmt = select(FiscalYearTable).order_by(FiscalYearTable.start_date.desc())
        result = await self.session.execute(stmt)
        return [FiscalYear.model_validate(r) for r in result.scalars().all()]

    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]:
        stmt = select(FiscalYearTable).where(FiscalYearTable.id == fy_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return FiscalYear.model_validate(row) if row else None

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        # Simplistic save (update if ID exists, else insert)
        if fy.id:
            stmt = select(FiscalYearTable).where(FiscalYearTable.id == fy.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.name = fy.name
                existing.start_date = fy.start_date
                existing.end_date = fy.end_date
                existing.status = fy.status
                existing.period_number = fy.period_number
                await self.session.commit()
                return FiscalYear.model_validate(existing)
        
        new_fy = FiscalYearTable(
            name=fy.name,
            start_date=fy.start_date,
            end_date=fy.end_date,
            status=fy.status,
            period_number=fy.period_number
        )
        self.session.add(new_fy)
        await self.session.commit()
        await self.session.refresh(new_fy)
        return FiscalYear.model_validate(new_fy)

    async def delete_fiscal_year(self, fy_id: int) -> bool:
        stmt = select(FiscalYearTable).where(FiscalYearTable.id == fy_id)
        result = await self.session.execute(stmt)
        fy = result.scalar_one_or_none()
        if fy:
            await self.session.delete(fy)
            await self.session.commit()
            return True
        return False

    # --- Account ---
    async def get_accounts(self) -> List[Account]:
        stmt = select(AccountTable).order_by(AccountTable.code)
        result = await self.session.execute(stmt)
        return [Account.model_validate(r) for r in result.scalars().all()]

    async def save_account(self, account: Account) -> Account:
        if account.id:
            stmt = select(AccountTable).where(AccountTable.id == account.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.code = account.code
                existing.name = account.name
                existing.type = account.type.value # Store as string
                existing.description = account.description
                await self.session.commit()
                return Account.model_validate(existing)
                
        new_acc = AccountTable(
            code=account.code,
            name=account.name,
            type=account.type.value,
            description=account.description
        )
        self.session.add(new_acc)
        await self.session.commit()
        await self.session.refresh(new_acc)
        return Account.model_validate(new_acc)

    async def delete_account(self, account_id: int) -> bool:
        stmt = select(AccountTable).where(AccountTable.id == account_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await self.session.delete(existing)
            await self.session.commit()
            return True
        return False

    # --- Abstract ---
    async def get_abstracts(self) -> List[Abstract]:
        # Join with Account to get name potentially, but eager load is better
        stmt = select(AbstractTable).options(selectinload(AbstractTable.account))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        # Map manually or use model_validate with denormalization
        abstracts = []
        for r in rows:
            data = Abstract.model_validate(r)
            if r.account:
                data.account_name = r.account.name
            abstracts.append(data)
        return abstracts

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        if abstract.id:
            stmt = select(AbstractTable).where(AbstractTable.id == abstract.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.account_id = abstract.account_id
                existing.text = abstract.text
                await self.session.commit()
                await self.session.refresh(existing)
                return Abstract.model_validate(existing)
            
        new_abs = AbstractTable(
            account_id=abstract.account_id,
            text=abstract.text
        )
        self.session.add(new_abs)
        await self.session.commit()
        await self.session.refresh(new_abs)
        return Abstract.model_validate(new_abs)

    async def delete_abstract(self, abs_id: int) -> bool:
        stmt = select(AbstractTable).where(AbstractTable.id == abs_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await self.session.delete(existing)
            await self.session.commit()
            return True
        return False

    # --- Counterparty ---
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        existing = None
        
        # 1. Check by ID if provided (Update Mode)
        if counterparty.id:
            stmt = select(CounterpartyTable).where(CounterpartyTable.id == counterparty.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            
        # 2. If no ID (or not found), Check for Duplicates (Insert Mode)
        else:
            # Check by invoice_number if present
            if counterparty.invoice_number:
                stmt = select(CounterpartyTable).where(CounterpartyTable.invoice_number == counterparty.invoice_number)
                result = await self.session.execute(stmt)
                existing = result.scalar_one_or_none()
            
            # Check by name if still not found
            if not existing and counterparty.name:
                stmt = select(CounterpartyTable).where(CounterpartyTable.name == counterparty.name)
                result = await self.session.execute(stmt)
                existing = result.scalar_one_or_none()
            
        if existing:
            existing.name = counterparty.name
            existing.name_kana = counterparty.name_kana
            # Handle empty string as None for invoice
            existing.invoice_number = counterparty.invoice_number if counterparty.invoice_number else None
            existing.debit_account_id = counterparty.debit_account_id
            existing.credit_account_id = counterparty.credit_account_id
            existing.description_template = counterparty.description_template
            
            await self.session.commit()
            await self.session.refresh(existing)
            return Counterparty.model_validate(existing)
        else:
            new_cp = CounterpartyTable(
                name=counterparty.name,
                name_kana=counterparty.name_kana,
                invoice_number=counterparty.invoice_number if counterparty.invoice_number else None,
                debit_account_id=counterparty.debit_account_id,
                credit_account_id=counterparty.credit_account_id,
                description_template=counterparty.description_template
            )
            self.session.add(new_cp)
            await self.session.commit()
            await self.session.refresh(new_cp)
            return Counterparty.model_validate(new_cp)

    async def get_counterparties(self) -> List[Counterparty]:
        stmt = select(CounterpartyTable).order_by(CounterpartyTable.name)
        result = await self.session.execute(stmt)
        return [Counterparty.model_validate(r) for r in result.scalars().all()]

    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]:
        stmt = select(CounterpartyTable).where(
            CounterpartyTable.name.ilike(f"%{keyword}%")
        ).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return Counterparty.model_validate(row) if row else None

    async def delete_counterparty(self, cp_id: int) -> bool:
        stmt = select(CounterpartyTable).where(CounterpartyTable.id == cp_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await self.session.delete(existing)
            await self.session.commit()
            return True
        return False
