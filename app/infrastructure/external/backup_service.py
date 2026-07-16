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

import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from app.config import settings

class BackupService:
    async def create_backup(self, target_dir_str: str) -> str:
        """
        Creates a backup of the current database to the specified target directory.
        Creates a timestamped subdirectory inside target_dir.
        Returns the full path of the backup file.
        Executed asynchronously to prevent blocking.
        """
        if not target_dir_str:
            raise ValueError("バックアップ先ディレクトリが指定されていません。")
            
        return await asyncio.to_thread(self._create_backup_sync, target_dir_str)

    def _create_backup_sync(self, target_dir_str: str) -> str:
        """
        Internal synchronous method for backup creation.
        """
        target_dir = Path(target_dir_str)
        
        # Ensure target directory exists
        if not target_dir.exists():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"指定されたディレクトリを作成できませんでした: {e}")
        
        # Create timestamped subdirectory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = target_dir / timestamp
        backup_subdir.mkdir(exist_ok=True)
        
        # Database Copy Logic
        db_copied = False
        db_path_str = settings.DATABASE_URL
        if db_path_str and "sqlite" in db_path_str:
            # Extract actual path from connection string (e.g. sqlite+aiosqlite:///path/to/db)
            db_path = Path(db_path_str.split("///")[-1])
            if db_path.exists() and str(db_path) != ":memory:":
                try:
                    dest_db_path = backup_subdir / db_path.name
                    shutil.copy2(db_path, dest_db_path)
                    
                    # Try to copy WAL and SHM files if they exist (SQLite)
                    wal_path = Path(str(db_path) + "-wal")
                    shm_path = Path(str(db_path) + "-shm")
                    
                    if wal_path.exists(): 
                        shutil.copy2(wal_path, backup_subdir / f"{db_path.name}-wal")
                    if shm_path.exists(): 
                        shutil.copy2(shm_path, backup_subdir / f"{db_path.name}-shm")
                    
                    db_copied = True
                except Exception as e:
                    raise RuntimeError(f"データベースのバックアップ作成に失敗しました: {e}")
        else:
            # Fallback based on old logic just in case
            fallback_db_path = settings.PROJECT_ROOT / "data" / settings.DB_NAME
            if fallback_db_path.exists():
                try:
                    dest_db_path = backup_subdir / fallback_db_path.name
                    shutil.copy2(fallback_db_path, dest_db_path)
                    
                    wal_path = Path(str(fallback_db_path) + "-wal")
                    if wal_path.exists():
                        shutil.copy2(wal_path, backup_subdir / f"{fallback_db_path.name}-wal")
                    
                    db_copied = True
                except Exception as e:
                    raise RuntimeError(f"データベースのバックアップ作成に失敗しました(Fallback): {e}")
            else:
                 raise RuntimeError("バックアップ元のデータベースファイルが見つかりません。")
        
        # .env Copy Logic
        env_path = settings.PROJECT_ROOT / ".env"
        if env_path.exists() and env_path.is_file():
            try:
                shutil.copy2(env_path, backup_subdir / ".env")
            except Exception:
                # 必須ではないがエラーは報告するか、無視するか。ここでは継続するがログには残したい
                # print関数は使えないため、無視して進める。
                pass

        if not db_copied:
             raise RuntimeError("データベースのバックアップに失敗しました。")

        return str(backup_subdir)
