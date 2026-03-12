import reflex as rx
from app.ui.di import DI

from .base import JournalState
from .master import JournalMasterState
from .form import JournalFormState
from .ocr import JournalOCRState
from .list import JournalListState

class JournalCoordinatorState(JournalState):
    """
    Orchestrates the Journal page module. 
    Handles top-level mount events to distribute loaded data to independent substates.
    """
    
    async def on_mount_journal(self):
        """Called when Journal Entry or History pages are mounted."""
        # Load master data
        master_state = await self.get_state(JournalMasterState)
        await master_state.load_accounts()
        
        # Pass necessary reference data to FormState
        form_state = await self.get_state(JournalFormState)
        form_state.abstracts = master_state.abstracts
        
        # Configure and load ListState
        list_state = await self.get_state(JournalListState)
        if not list_state.filter_start_date or not list_state.filter_end_date:
            async with DI.get_master_service() as service:
                fys = await service.get_fiscal_years()
                if fys:
                    # Sort descending safely across None issues
                    open_fys = [fy for fy in fys if fy.status == "OPEN"]
                    if open_fys:
                        open_fys.sort(key=lambda x: x.period_number, reverse=True)
                        latest = open_fys[0]
                        list_state.filter_start_date = latest.start_date.isoformat()
                        list_state.filter_end_date = latest.end_date.isoformat()
                        
        await list_state.load_entries()
        
    async def handle_tab_change(self, val: str):
        """Handle UI tab change if maintaining local tab states."""
        if val == "list":
            list_state = await self.get_state(JournalListState)
            await list_state.load_entries()
