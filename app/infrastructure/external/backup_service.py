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

import asyncio
from datetime import datetime
from pathlib import Path
import shutil
from app.config import settings


class BackupService:
    async def create_backup(self, target_dir_str: str) -> str:
        if not target_dir_str:
            raise ValueError("バックアップ先ディレクトリが指定されていません。")
        return await asyncio.to_thread(self._create_backup_sync, target_dir_str)

    def _create_backup_sync(self, target_dir_str: str) -> str:
        target_dir = Path(target_dir_str)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"指定されたディレクトリを作成できませんでした: {e}")

        backup_subdir = target_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir.mkdir(exist_ok=True)

        db_path_str = settings.DATABASE_URL
        db_path = (
            Path(db_path_str.split("///")[-1])
            if db_path_str and "sqlite" in db_path_str
            else settings.PROJECT_ROOT / "data" / settings.DB_NAME
        )

        if not db_path.exists() or str(db_path) == ":memory:":
            raise RuntimeError("データベースのバックアップに失敗しました。")

        try:
            shutil.copy2(db_path, backup_subdir / db_path.name)
            for ext in ("-wal", "-shm"):
                aux = Path(str(db_path) + ext)
                if aux.exists():
                    shutil.copy2(aux, backup_subdir / f"{db_path.name}{ext}")
        except Exception as e:
            raise RuntimeError(f"データベースのバックアップ作成に失敗しました: {e}")

        env_path = settings.PROJECT_ROOT / ".env"
        if env_path.exists() and env_path.is_file():
            try:
                shutil.copy2(env_path, backup_subdir / ".env")
            except Exception:
                pass

        return str(backup_subdir)
