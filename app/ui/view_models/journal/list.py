# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import reflex as rx
from typing import List
from datetime import date
from app.domain.models.transaction import Transaction
from app.ui.di import DI
import structlog
from .base import JournalState

log = structlog.get_logger()

# Global module-level var to share state across sessions
GLOBAL_JOURNAL_UPDATE_TIME: float = 0.0


class JournalListState(JournalState):
    """State for viewing and managing the list of journal entries."""

    journal_entries: List[Transaction] = []
    show_deleted: bool = False

    filter_start_date: str = ""
    filter_end_date: str = ""

    _local_last_update: float = 0.0

    async def check_for_updates(self):
        """Polls global state to see if a reload is necessary."""
        global GLOBAL_JOURNAL_UPDATE_TIME

        # If the global timestamp is newer, meaning another tab successfully submitted a form
        if GLOBAL_JOURNAL_UPDATE_TIME > self._local_last_update:
            self._local_last_update = GLOBAL_JOURNAL_UPDATE_TIME
            await self.load_entries()

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
                start = (
                    date.fromisoformat(self.filter_start_date)
                    if self.filter_start_date
                    else None
                )
                end = (
                    date.fromisoformat(self.filter_end_date)
                    if self.filter_end_date
                    else None
                )

                entries = await service.get_entries(
                    start_date=start, end_date=end, include_deleted=self.show_deleted
                )
                self.journal_entries = entries
            except Exception as e:
                log.error("Error loading entries", error=str(e), exc_info=True)

    async def delete_entry(self, entry_id: int):
        async with DI.get_journal_service() as service:
            try:
                await service.delete_entry(entry_id)
                await self.load_entries()

                # Trigger global update signal
                global GLOBAL_JOURNAL_UPDATE_TIME
                import time

                GLOBAL_JOURNAL_UPDATE_TIME = time.time()
                self._local_last_update = GLOBAL_JOURNAL_UPDATE_TIME

                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"削除エラー: {e}")

    async def export_csv(self):
        """Export filtered journal entries to CSV."""
        async with DI.get_journal_service() as service:
            try:
                start = (
                    date.fromisoformat(self.filter_start_date)
                    if self.filter_start_date
                    else None
                )
                end = (
                    date.fromisoformat(self.filter_end_date)
                    if self.filter_end_date
                    else None
                )

                csv_data = await service.export_journal_entries_csv(
                    start_date=start, end_date=end
                )

                filename = f"journal_export_{self.filter_start_date or 'begin'}_{self.filter_end_date or 'end'}.csv"

                return rx.download(data=csv_data, filename=filename)
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
            log.error("Failed to download evidence.", error=str(e), exc_info=True)
            return rx.window_alert(f"ダウンロードエラー: {e}")
