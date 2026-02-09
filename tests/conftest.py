import os
import sys
import pytest
import asyncio

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
    
    ms = await c.get_master_service()
    
    # 1. Seed Corporation
    if not await ms.get_corporation():
        await ms.save_corporation(Corporation(name="Test Corp", address="Test Address"))
        
    # 2. Seed Accounts if empty
    accounts = await ms.get_accounts()
    if not accounts:
        # Cash
        await ms.save_account(Account(
            code="111", 
            name="現金", 
            type=AccountType.CURRENT_ASSET, 
            description="Cash"
        ))
        # Sales
        await ms.save_account(Account(
            code="411", 
            name="売上高", 
            type=AccountType.REVENUE, 
            description="Sales"
        ))
    
    return c
