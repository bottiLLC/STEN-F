import asyncio
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.ui.di import DI
from app.domain.models.counterparty import Counterparty
from app.domain.models.account import AccountType

async def verify():
    print("Starting Counterparty Validation...")
    
    # Use context manager for service
    async with DI.get_master_service() as service:
        # Pre-check
        initial_list = await service.get_counterparties()
        print(f"Initial count: {len(initial_list)}")

        # 1. Create
        cp = Counterparty(
            name="Test Corp Validation",
            name_kana="test",
            invoice_number="T1234567890123",
            default_account_type=AccountType.COST_OF_SALES.value
        )
        print(f"Saving: {cp.name}")
        saved = await service.save_counterparty(cp)
        print(f"Saved ID: {saved.id}")
        
        # 2. Get
        all_cps = await service.get_counterparties()
        print(f"Total Counterparties: {len(all_cps)}")
        my_cp = next((c for c in all_cps if c.id == saved.id), None)
        
        if my_cp is None:
            print("ERROR: Could not find saved counterparty")
            return

        print(f"Found: {my_cp.name}")
        if my_cp.invoice_number != "T1234567890123":
             print(f"ERROR: Invoice number mismatch: {my_cp.invoice_number}")
        
        # 3. Update (implicitly via save with ID?) 
        # State uses save_counterparty with ID if set.
        # Let's try updating name
        my_cp.name = "Test Corp Updated"
        updated = await service.save_counterparty(my_cp)
        print(f"Updated Name: {updated.name}")
        
        # Verify update
        all_cps_update = await service.get_counterparties()
        my_cp_update = next((c for c in all_cps_update if c.id == saved.id), None)
        if my_cp_update.name != "Test Corp Updated":
             print(f"ERROR: Update failed, got {my_cp_update.name}")

        # 4. Delete
        print(f"Deleting ID: {saved.id}")
        await service.delete_counterparty(saved.id)
        
        # 5. Verify Delete
        all_cps_after = await service.get_counterparties()
        print(f"Total Counterparties after delete: {len(all_cps_after)}")
        my_cp_after = next((c for c in all_cps_after if c.id == saved.id), None)
        
        if my_cp_after is not None:
             print("ERROR: Counterparty was not deleted")
        else:
             print("Delete successful")

if __name__ == "__main__":
    try:
        # Fix for Windows SelectorEventLoopPolicy if needed, but standard run should be fine for simple script
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        asyncio.run(verify())
        print("VERIFICATION COMPLETED")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"VERIFICATION FAILED: {e}")
