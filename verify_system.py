import asyncio
import os
import sys
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from app.ui.di import DI
from app.domain.models.corporation import Corporation
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import Account, AccountType
from app.domain.models.abstract import Abstract
from app.domain.models.transaction import Transaction, TransactionLine

async def verify_system():
    print("=== Starting System Verification (Service Layer) ===")
    
    # 1. Master: Corporation
    print("\n[1] Verifying Corporation Registration...")
    async with DI.get_master_service() as service:
        # Check existing first
        existing_corp = await service.get_corporation()
        corp_id = existing_corp.id if existing_corp else None
        
        corp = Corporation(
            id=corp_id,
            name="Test Corp Ltd. (Verified)",
            address="1-2-3 Test St, Tokyo",
            representative_title="CEO",
            representative_name="Taro Test"
        )
        await service.save_corporation(corp)
        print("    -> Corporation saved.")
        
        # Verify
        saved = await service.get_corporation()
        print(f"    -> Verified DB: {saved.name}")
        assert saved.name == "Test Corp Ltd. (Verified)"

    # 2. Master: Fiscal Year
    print("\n[2] Verifying Fiscal Year...")
    async with DI.get_master_service() as service:
        fys = await service.get_fiscal_years()
        fy_99 = next((f for f in fys if f.period_number == 99), None)
        
        if not fy_99:
            new_fy = FiscalYear(
                name="第99期",
                period_number=99,
                start_date=date(2030, 4, 1),
                end_date=date(2031, 3, 31),
                status="OPEN"
            )
            await service.create_fiscal_year(new_fy)
            print("    -> Fiscal Year 99 created.")
            # Reload to get ID
            fys = await service.get_fiscal_years()
            fy_99 = next(f for f in fys if f.period_number == 99)
        else:
            print("    -> FY 99 already exists.")
            
        fy_id = fy_99.id

    # 3. Master: Account
    print("\n[3] Verifying Account Creation...")
    acc_expense_id = None
    acc_cash_id = None
    acc_capital_id = None
    
    async with DI.get_master_service() as service:
        accounts = await service.get_accounts()
        
        # Helper to create if not exists
        async def ensure_account(code, name, type_enum):
            existing = next((a for a in accounts if a.code == code), None)
            if existing: 
                return existing.id
            
            new_acc = Account(
                code=code, 
                name=name, 
                type=type_enum, 
                description="Verified Account"
            )
            await service.save_account(new_acc)
            # Refetch to get ID (simple approach) or assume functionality
            # Let's verify by refetching
            updated_accounts = await service.get_accounts()
            return next(a for a in updated_accounts if a.code == code).id

        acc_expense_id = await ensure_account("9999", "Test Expense", AccountType.SGA)
        acc_cash_id = await ensure_account("1111", "Cash", AccountType.CURRENT_ASSET)
        acc_capital_id = await ensure_account("3000", "Capital", AccountType.EQUITY)
        
        print(f"    -> Accounts Addressed: {acc_expense_id}, {acc_cash_id}, {acc_capital_id}")

    # 4. Master: Abstract
    print("\n[4] Verifying Abstract Creation...")
    async with DI.get_master_service() as service:
        abstracts = await service.get_abstracts()
        if not any(a.text == "Verified Transaction" for a in abstracts):
            new_abs = Abstract(account_id=acc_expense_id, text="Verified Transaction")
            await service.save_abstract(new_abs)
            print("    -> Abstract created.")

    # 5. Journal Entry
    print("\n[5] Verifying Journal Entry...")
    tx_id = None
    async with DI.get_journal_service() as service:
        lines = [
            TransactionLine(account_id=acc_expense_id, debit=50000, credit=0),
            TransactionLine(account_id=acc_cash_id, debit=0, credit=50000)
        ]
        
        tx = Transaction(
            date=date(2030, 4, 1), # Inside FY 99
            description="Verified Service Entry",
            counterparty="Service Bot",
            lines=lines
        )
        
        tx_id = await service.add_journal_entry(tx)
        print(f"    -> Journal Entry submitted. ID: {tx_id}")
        
        # Verify
        entries = await service.get_entries()
        saved_entry = next((e for e in entries if e.id == tx_id), None)
        assert saved_entry is not None
        print("    -> Verified Entry existence.")

    # 6. Reports & PDF
    print("\n[6] Verifying PDF Export...")
    try:
        pdf_service = DI.get_pdf_service()
        
        # Generate Report Data
        async with DI.get_ledger_service() as ledger:
            print(f"    -> Generating Financial Report for FY ID: {fy_id}")
            report_data = await ledger.generate_financial_report(fy_id)
            print(f"       Assets: {report_data.total_assets}")
            print(f"       Expenses: {report_data.sga.total + report_data.cost_of_sales.total + report_data.non_op_expense.total + report_data.extra_loss.total}")
        
        async with DI.get_master_service() as master:
            corp = await master.get_corporation()
            
        current_fy = fy_99
        
        pdf_bytes = pdf_service.generate_annual_report(
            corp, report_data, current_fy, date.today(), date.today()
        )
        
        output_file = "verified_annual_report.pdf"
        with open(output_file, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"    -> PDF Generated successfully: {output_file} ({len(pdf_bytes)} bytes)")
    except Exception as e:
        print(f"    -> PDF Generation FAILED: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_system())
