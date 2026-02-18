import reflex as rx
import os
from app.ui.di import DI

class SystemState(rx.State):
    backup_path: str = os.path.abspath("./backups")

    def set_backup_path(self, path: str):
        self.backup_path = path

    async def create_backup(self):
        """Create a database backup."""
        service = DI.get_backup_service()
        try:
             saved_path = await service.create_backup(self.backup_path)
             return rx.window_alert(f"バックアップが完了しました！\n保存場所: {saved_path}")
        except Exception as e:
             return rx.window_alert(f"エラーが発生しました: {str(e)}")
