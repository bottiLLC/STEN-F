import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from config import settings

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
        
        # Define destination path
        dest_path = backup_subdir / "bookkeeping.db"
        
        # Define source path
        db_path = settings.PROJECT_ROOT / "data" / settings.DB_NAME
        
        # Copy logic
        try:
            shutil.copy2(db_path, dest_path)
            
            # Try to copy WAL files if they exist (SQLite)
            wal_path = Path(str(db_path) + "-wal")
            shm_path = Path(str(db_path) + "-shm")
            
            if wal_path.exists(): 
                shutil.copy2(wal_path, backup_subdir / "bookkeeping.db-wal")
            if shm_path.exists(): 
                shutil.copy2(shm_path, backup_subdir / "bookkeeping.db-shm")
            
            return str(dest_path)
        except Exception as e:
            raise RuntimeError(f"バックアップの作成に失敗しました: {e}")
