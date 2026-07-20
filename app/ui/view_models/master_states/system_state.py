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
import structlog
from app.config import settings
from app.ui.di import DI

log = structlog.get_logger()


class SystemState(rx.State):
    backup_path: str = str((settings.PROJECT_ROOT / "backups").resolve())
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
                if settings.backup_path:
                    self.backup_path = settings.backup_path
        except Exception as e:
            # First-time loading might fail if the DB isn't strictly seeded
            log.warning("Failed to load system settings", error=str(e))

    async def save_backup_path(self):
        """バックアップ保存先パスをデータベースに保存する"""
        try:
            async with DI.get_master_service() as service:
                settings = await service.get_system_settings()
                settings.backup_path = self.backup_path
                await service.save_system_settings(settings)
            yield rx.toast.success("バックアップ保存先を設定しました。")
        except Exception as e:
            yield rx.window_alert(f"保存エラー: {str(e)}")

    async def select_backup_directory(self):
        """Tkinterを使用してフォルダ選択ダイアログを開き、パスを取得して保存する"""
        import asyncio

        def _open_dialog():
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                title="バックアップ保存先フォルダの選択",
                initialdir=self.backup_path or "",
            )
            root.destroy()
            return selected

        try:
            selected_dir = await asyncio.to_thread(_open_dialog)
            if selected_dir:
                from pathlib import Path

                normalized = str(Path(selected_dir).resolve())
                self.backup_path = normalized
                async with DI.get_master_service() as service:
                    settings = await service.get_system_settings()
                    settings.backup_path = normalized
                    await service.save_system_settings(settings)
                yield rx.toast.success(f"保存先を設定しました: {normalized}")
        except Exception as e:
            log.error("Failed to select directory via tkinter", error=str(e))
            yield rx.window_alert(f"フォルダ選択エラー: {str(e)}")

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

            yield rx.toast.success("AI設定が保存されました。")
        except Exception as e:
            yield rx.window_alert(f"保存エラー: {str(e)}")
        finally:
            self.is_saving_key = False
            yield

    async def create_backup(self):
        """Create a database backup."""
        service = DI.get_backup_service()
        try:
            saved_path = await service.create_backup(self.backup_path)
            yield rx.window_alert(
                f"データベースと設定ファイル(.env)のバックアップが完了しました！\n保存場所: {saved_path}"
            )
        except Exception as e:
            yield rx.window_alert(f"エラーが発生しました: {str(e)}")
