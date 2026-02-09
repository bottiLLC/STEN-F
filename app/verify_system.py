import asyncio
import sys
import os
from datetime import date

# Add v2/app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from container import Container
from domain.models.transaction import Transaction, TransactionLine
from domain.models.account import AccountType
from domain.models.fiscal_year import FiscalYear

async def verify_system():
    print("🚀 Starting Comprehensive System Verification...")
    
    container = Container()
    
    # 1. Services Initialization
    print("\n[1] Initializing Services...")
    try:
        master_service = await container.get_master_service()
        ledger_service = await container.get_ledger_service()
        journal_service = await container.get_journal_service()
        pdf_service = container.get_pdf_service()
        print("✅ Services initialized successfully.")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return

    # 2. Master Data Check
    print("\n[2] Checking Master Data...")
    fys = await master_service.get_fiscal_years()
    accounts = await master_service.get_accounts()
    corp = await master_service.get_corporation()
    
    if not fys:
        print("❌ No Fiscal Years found.")
        return
    print(f"✅ Found {len(fys)} Fiscal Years.")
    
    if not accounts:
        print("❌ No Accounts found.")
        return
    print(f"✅ Found {len(accounts)} Accounts.")
    
    if not corp:
        print("⚠️ No Corporation data found (Warning only).")
    else:
        print(f"✅ Corporation: {corp.name}")

    # 2b. Create temporary FY covering today
    today = date.today()
    start_of_year = date(today.year, 1, 1)
    end_of_year = date(today.year, 12, 31)
    
    test_fy = FiscalYear(
        name="VERIFICATION_FY",
        start_date=start_of_year,
        end_date=end_of_year,
        status="OPEN",
        period_number=999
    )
    
    print(f"\n[2b] Creating Test Fiscal Year ({start_of_year} - {end_of_year})...")
    created_fy_id = None
    try:
        await master_service.save_fiscal_year(test_fy) 
        # Refetch to get ID
        fys = await master_service.get_fiscal_years()
        target_fy = next((f for f in fys if f.name == "VERIFICATION_FY"), None)
        if target_fy:
             print(f"✅ Created/Found Test FY. ID: {target_fy.id}")
             created_fy_id = target_fy.id
        else:
             print(f"❌ Failed to find Test FY after creation!")
             target_fy = fys[-1] # Fallback
    except Exception as e:
        print(f"❌ Failed to create Test FY: {e}")
        target_fy = fys[-1]
        
    print(f"ℹ️ Testing with Fiscal Year: {target_fy.name} (ID: {target_fy.id})")

    # 3. Journal Entry Test (Create)
    print("\n[3] Testing Journal Entry Creation...")
    cash_acc = next((a for a in accounts if "現金" in a.name), None)
    sales_acc = next((a for a in accounts if "売上" in a.name or a.type == AccountType.REVENUE), None)
    
    if not cash_acc or not sales_acc:
        print("❌ Could not find Cash or Sales accounts for valid test.")
        cash_acc = accounts[0]
        sales_acc = accounts[1]
        print(f"⚠️ Using fallback accounts: {cash_acc.name}, {sales_acc.name}")

    test_amount = 12345
    test_tx = Transaction(
        date=today,
        description="SYSTEM_VERIFICATION_TEST_TRANSACTION",
        lines=[
            TransactionLine(account_id=cash_acc.id, debit=test_amount, credit=0),
            TransactionLine(account_id=sales_acc.id, debit=0, credit=test_amount)
        ]
    )
    
    tx_id = None
    try:
        tx_id = await journal_service.add_journal_entry(test_tx)
        print(f"✅ Transaction created with ID: {tx_id}")
    except Exception as e:
        print(f"❌ Failed to create transaction: {e}")
        return

    # 4. Ledger Integrity Check
    print("\n[4] Checking Ledger Integrity...")
    
    # 4a. Check General Ledger
    try:
        gl_df = await ledger_service.get_general_ledger(target_fy.id, cash_acc.id)
        if tx_id is not None:
            target_row = gl_df[gl_df['TransactionID'] == tx_id]
            if not target_row.empty:
                print(f"✅ Transaction found in General Ledger for {cash_acc.name}.")
                print(f"   Debits: {target_row.iloc[0]['借方']}")
            else:
                print(f"❌ Transaction {tx_id} NOT found in General Ledger for {cash_acc.name}!")
    except Exception as e:
        print(f"❌ Failed to fetch General Ledger: {e}")

    # 4b. Check Trial Balance
    try:
        tb_rows = await ledger_service.get_trial_balance(target_fy.id)
        cash_row = next((r for r in tb_rows if r.account_id == cash_acc.id), None)
        if cash_row:
             print(f"✅ Trial Balance Row for {cash_acc.name} exists.")
             print(f"   Debit Total: {cash_row.debit_total}, Credit Total: {cash_row.credit_total}")
             if cash_row.debit_total >= test_amount:
                 print(f"✅ Debit Total reflects new transaction.")
             else:
                 print(f"❌ Debit Total ({cash_row.debit_total}) does NOT reflect transaction ({test_amount})!")
        else:
             print(f"❌ Trial Balance Row for {cash_acc.name} missing!")
    except Exception as e:
        print(f"❌ Failed to fetch Trial Balance: {e}")

    # 5. Financial Report Generation
    print("\n[5] Generating Financial Report...")
    try:
        report = await ledger_service.generate_financial_report(target_fy.id)
        print("✅ Financial Report object generated.")
        print(f"   Total Assets: {report.total_assets}")
        print(f"   Net Income: {report.net_income}")
    except Exception as e:
        print(f"❌ Failed to generate Financial Report: {e}")

    # 6. PDF Generation (Dry Run)
    print("\n[6] Testing PDF Generation...")
    try:
        if corp:
            pdf_bytes = pdf_service.generate_annual_report(corp, report, target_fy, today, today)
            print(f"✅ PDF generated successfully ({len(pdf_bytes)} bytes).")
        else:
             print("⚠️ Skipping PDF test (No Corporation data).")
    except Exception as e:
        print(f"❌ PDF Generation failed: {e}")

    # 7. Cleanup
    print("\n[7] Cleaning up Test Data...")
    if tx_id:
        try:
            await journal_service.delete_entry(tx_id)
            print(f"✅ Test Transaction {tx_id} deleted.")
        except Exception as e:
            print(f"❌ Failed to delete transaction: {e}")

    if created_fy_id:
        try:
            await master_service.delete_fiscal_year(created_fy_id)
            print(f"✅ Test FY {created_fy_id} deleted.")
        except Exception as e:
            print(f"❌ Failed to delete Test FY: {e}")

    print("\n🎉 Comprehensive Verification Completed.")

if __name__ == "__main__":
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_system())
