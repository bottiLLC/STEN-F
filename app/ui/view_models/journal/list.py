import reflex as rx
from typing import List
from datetime import date
from domain.models.transaction import Transaction
from app.ui.di import DI
from core.logging import logger
from .base import JournalState

class JournalListState(JournalState):
    """State for viewing and managing the list of journal entries."""
    
    journal_entries: List[Transaction] = []
    show_deleted: bool = False
    
    filter_start_date: str = ""
    filter_end_date: str = ""

    async def toggle_show_deleted(self):
        self.show_deleted = not self.show_deleted
        await self.load_entries()
        
    def set_filter_start_date(self, value: str):
        self.filter_start_date = value

    def set_filter_end_date(self, value: str):
        self.filter_end_date = value

    async def load_entries(self):
        """Load recent journal entries."""
        async with DI.get_journal_service() as service:
             try:
                 start = date.fromisoformat(self.filter_start_date) if self.filter_start_date else None
                 end = date.fromisoformat(self.filter_end_date) if self.filter_end_date else None
                 
                 entries = await service.get_entries(
                     start_date=start, 
                     end_date=end, 
                     include_deleted=self.show_deleted
                 )
                 self.journal_entries = entries
             except Exception as e:
                 logger.error("Error loading entries", error=str(e), exc_info=True)

    async def delete_entry(self, entry_id: int):
        async with DI.get_journal_service() as service:
            try:
                await service.delete_entry(entry_id)
                await self.load_entries()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"削除エラー: {e}")

    async def export_csv(self):
        """Export filtered journal entries to CSV."""
        async with DI.get_journal_service() as service:
            try:
                start = date.fromisoformat(self.filter_start_date) if self.filter_start_date else None
                end = date.fromisoformat(self.filter_end_date) if self.filter_end_date else None
                
                csv_data = await service.export_journal_entries_csv(start_date=start, end_date=end)
                
                filename = f"journal_export_{self.filter_start_date or 'begin'}_{self.filter_end_date or 'end'}.csv"
                
                return rx.download(
                    data=csv_data,
                    filename=filename
                )
            except Exception as e:
                return rx.window_alert(f"Export Error: {e}")

    async def download_evidence(self, entry_id: int):
        """Download evidence file for a transaction asynchronously."""
        entry = next((e for e in self.journal_entries if e.id == entry_id), None)
        if not entry or not entry.evidence_path:
             return rx.window_alert("証憑ファイルが見つかりません。")
        
        import os
        import aiofiles
        if not os.path.exists(entry.evidence_path):
             return rx.window_alert("指定されたファイルがサーバー上に存在しません。")
             
        try:
            async with aiofiles.open(entry.evidence_path, "rb") as f:
                data = await f.read()
                
            filename = os.path.basename(entry.evidence_path)
            return rx.download(data=data, filename=filename)
        except Exception as e:
            logger.error("Failed to download evidence.", error=str(e), exc_info=True)
            return rx.window_alert(f"ダウンロードエラー: {e}")
