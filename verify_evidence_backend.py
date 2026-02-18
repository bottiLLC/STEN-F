import asyncio
import sys
import os
from datetime import date
from pathlib import Path

# Ensure app is in path
sys.path.append(os.getcwd())

from app.ui.di import DI
from app.domain.models.transaction import Transaction, TransactionLine

async def verify():
    print("Starting Evidence Linkage Validation...")
    
    # Mock Data
    dummy_file_content = b"Content of a dummy PDF receipt"
    dummy_transaction = Transaction(
        date=date.today(),
        description="Test Evidence Entry",
        counterparty="Test Corp Evidence",
        invoice_number="T9876543210987",
        lines=[
            # Assuming account_id 1 exists (usually Cash or Sales)
            # We should probably get a valid account ID first
             TransactionLine(account_id=1, debit=1000, credit=0),
             TransactionLine(account_id=2, debit=0, credit=1000) 
        ]
    )

    async with DI.get_journal_service() as service:
        # We need valid account IDs. 
        # But let's assume 1 and 2 exist or we fail. 
        # Better: get accounts first.
        async with DI.get_master_service() as ms:
            accounts = await ms.get_accounts()
            if len(accounts) < 2:
                print("Not enough accounts to test transaction.")
                return
            
            dummy_transaction.lines[0].account_id = accounts[0].id
            dummy_transaction.lines[1].account_id = accounts[1].id
            
        print(f"Adding transaction with evidence...")
        file_service = DI.get_file_service()
        
        try:
            tx_id = await service.add_journal_entry_with_evidence(
                dummy_transaction, 
                dummy_file_content, 
                file_service
            )
            print(f"Transaction ID: {tx_id}")
            
            # Verify Persistence
            entries = await service.get_entries()
            entry = next((e for e in entries if e.id == tx_id), None)
            
            if not entry:
                print("ERROR: Transaction not found in DB")
                return

            print(f"Found Entry: {entry.description}")
            print(f"Evidence Path: {entry.evidence_path}")
            
            if not entry.evidence_path:
                print("ERROR: Evidence path is missing in DB")
            elif not os.path.exists(entry.evidence_path):
                print(f"ERROR: File does not exist at {entry.evidence_path}")
            else:
                print("SUCCESS: File exists on disk.")
                
                # Cleanup File
                try:
                    os.remove(entry.evidence_path)
                    print("Cleanup: Deleted test file.")
                except Exception as e:
                    print(f"Cleanup Warning: Could not delete file: {e}")

            # Cleanup DB
            print(f"Deleting transaction {tx_id}")
            await service.delete_entry(tx_id)
            print("Cleanup: Deleted transaction.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR during add_journal_entry_with_evidence: {e}")

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(verify())
        print("VERIFICATION COMPLETED")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
