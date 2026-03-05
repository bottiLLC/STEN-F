import os
import sys
import pytest

# Ensure 'v2/app' is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from container import Container

@pytest.fixture(scope="function")
async def container():
    """Provides a Container instance for each test function."""
    # Initialize DB schema for in-memory DB or fresh test DB
    from infrastructure.db.session import init_db
    await init_db()
    
    c = Container()
    
    # SEED DATA
    from domain.models.corporation import Corporation
    from domain.models.account import Account, AccountType
    from domain.models.fiscal_year import FiscalYear
    from datetime import date
    
    # 0. Seed Data using Scoped Service
    async with c.master_service_scope() as ms:
        # 0. Seed Fiscal Year
        fys = await ms.get_fiscal_years()
        if not fys:
            today = date.today()
            await ms.save_fiscal_year(FiscalYear(
                name=f"FY{today.year}",
                start_date=date(today.year, 1, 1),
                end_date=date(today.year, 12, 31),
                status="OPEN",
                period_number=1
            ))
        
        # 1. Seed Corporation
        if not await ms.get_corporation():
            await ms.save_corporation(Corporation(name="Test Corp", address="Test Address"))
            
        # 2. Seed Accounts if empty
        accounts = await ms.get_accounts()
        if not accounts:
            # Cash
            await ms.save_account(Account(
                code="1110", 
                name="現金", 
                type=AccountType.CURRENT_ASSET, 
                description="Cash"
            ))
            # Sales
            await ms.save_account(Account(
                code="4110", 
                name="売上高", 
                type=AccountType.REVENUE, 
                description="Sales"
            ))
    
    yield c
    # Container is now stateless (sessions are scoped), so no global shutdown needed.

