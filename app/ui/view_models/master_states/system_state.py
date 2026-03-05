import reflex as rx
import os
from app.ui.di import DI

class SystemState(rx.State):
    backup_path: str = os.path.abspath("./backups")
    ai_api_key: str = ""
    is_saving_key: bool = False

    def set_backup_path(self, path: str):
        self.backup_path = path
        
    def set_ai_api_key(self, api_key: str):
        self.ai_api_key = api_key

    async def load_settings(self):
        """データベースからシステム設定を読み込む"""
        try:
            async with DI.get_master_service() as service:
                settings = await service.get_system_settings()
                self.ai_api_key = settings.ai_api_key or ""
        except Exception as e:
            # First-time loading might fail if the DB isn't strictly seeded
            print(f"Failed to load system settings: {e}")

    async def save_api_key(self):
        """OpenAI APIキーを保存する"""
        self.is_saving_key = True
        yield
        try:
            async with DI.get_master_service() as service:
                # Need to get current settings first, then update
                settings = await service.get_system_settings()
                settings.ai_api_key = self.ai_api_key
                await service.save_system_settings(settings)
                
            return rx.toast.success("AI設定が保存されました。")
        except Exception as e:
            return rx.window_alert(f"保存エラー: {str(e)}")
        finally:
            self.is_saving_key = False
            yield

    async def create_backup(self):
        """Create a database backup."""
        service = DI.get_backup_service()
        try:
             saved_path = await service.create_backup(self.backup_path)
             return rx.window_alert(f"バックアップが完了しました！\n保存場所: {saved_path}")
        except Exception as e:
             return rx.window_alert(f"エラーが発生しました: {str(e)}")
