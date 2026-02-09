import pytest
from datetime import date
from domain.models.transaction import Transaction, TransactionLine
from domain.models.account import AccountType
from domain.models.fiscal_year import FiscalYear

@pytest.mark.asyncio
class TestSystemIntegration:
    
    async def test_01_services_initialization(self, container):
        """Test that all key services can be initialized."""
        master_service = await container.get_master_service()
        ledger_service = await container.get_ledger_service()
        journal_service = await container.get_journal_service()
        pdf_service = container.get_pdf_service()
        
        assert master_service is not None
        assert ledger_service is not None
        assert journal_service is not None
        assert pdf_service is not None

    async def test_02_master_data_integrity(self, container):
        """Test that minimal master data exists."""
        master_service = await container.get_master_service()
        fys = await master_service.get_fiscal_years()
        accounts = await master_service.get_accounts()
        corp = await master_service.get_corporation()
        
        assert len(fys) > 0, "No Fiscal Years found"
        assert len(accounts) > 0, "No Accounts found"
        # Corporation is optional but expected in this setup
        if corp:
            assert corp.name is not None

    async def test_03_full_journal_entry_cycle(self, container):
        """
        Comprehensive Test:
        1. Create a Test Fiscal Year
        2. Create a Transaction (Journal Entry)
        3. Verify Transaction appears in General Ledger
        4. Verify Transaction affects Trial Balance
        5. Verify Financial Report generation
        6. Clean up (Delete Transaction and FY)
        """
        master_service = await container.get_master_service()
        journal_service = await container.get_journal_service()
        ledger_service = await container.get_ledger_service()
        
        # --- A. Setup Test FY ---
        today = date.today()
        test_fy = FiscalYear(
            name="PYTEST_FY",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            status="OPEN",
            period_number=888
        )
        
        # Clean up if exists from failed run
        fys = await master_service.get_fiscal_years()
        existing = next((f for f in fys if f.name == "PYTEST_FY"), None)
        if existing:
            await master_service.delete_fiscal_year(existing.id)

        await master_service.save_fiscal_year(test_fy)
        
        # Fetch updated user
        fys = await master_service.get_fiscal_years()
        target_fy = next((f for f in fys if f.name == "PYTEST_FY"), None)
        assert target_fy is not None
        
        # --- B. Setup Test Transaction ---
        accounts = await master_service.get_accounts()
        cash_acc = next((a for a in accounts if a.type == AccountType.CURRENT_ASSET), accounts[0])
        sales_acc = next((a for a in accounts if a.type == AccountType.REVENUE), accounts[1])
        
        test_amount = 1000
        tx = Transaction(
            date=today,
            description="PYTEST_TX",
            lines=[
                TransactionLine(account_id=cash_acc.id, debit=test_amount, credit=0),
                TransactionLine(account_id=sales_acc.id, debit=0, credit=test_amount)
            ]
        )
        
        tx_id = await journal_service.add_journal_entry(tx)
        assert tx_id is not None
        
        # --- C. Verify General Ledger ---
        gl_df = await ledger_service.get_general_ledger(target_fy.id, cash_acc.id)
        assert not gl_df.empty
        target_row = gl_df[gl_df['TransactionID'] == tx_id]
        assert not target_row.empty, "Transaction not found in General Ledger"
        
        # --- D. Verify Trial Balance ---
        tb_rows = await ledger_service.get_trial_balance(target_fy.id)
        cash_row = next((r for r in tb_rows if r.account_id == cash_acc.id), None)
        assert cash_row is not None
        assert cash_row.debit_total >= test_amount
        
        # --- E. Verify Financial Report (Regression Check) ---
        report = await ledger_service.generate_financial_report(target_fy.id)
        assert report is not None
        
        # --- F. Cleanup ---
        await journal_service.delete_entry(tx_id)
        
        # Verify Deletion
        gl_df_after = await ledger_service.get_general_ledger(target_fy.id, cash_acc.id)
        if not gl_df_after.empty:
            assert tx_id not in gl_df_after['TransactionID'].values

        await master_service.delete_fiscal_year(target_fy.id)
