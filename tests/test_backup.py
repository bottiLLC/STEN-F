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

import pytest
import shutil
import asyncio
from pathlib import Path
from unittest.mock import patch

from app.infrastructure.external.backup_service import BackupService
from app.config import settings

@pytest.fixture
def temp_backup_env(tmp_path):
    # Set up temporary environment
    original_project_root = settings.PROJECT_ROOT
    original_database_url = settings.DATABASE_URL
    
    # Create mock PROJECT_ROOT
    mock_root = tmp_path / "mock_project"
    mock_root.mkdir()
    
    # Create mock .env
    mock_env = mock_root / ".env"
    mock_env.write_text("DUMMY_ENV=123", encoding="utf-8")
    
    # Create mock DB path and file
    mock_db_dir = mock_root / "data"
    mock_db_dir.mkdir()
    mock_db_file = mock_db_dir / "sten_f.db"
    mock_db_file.write_text("DUMMY_DB_DATA", encoding="utf-8")
    
    # Create mock WAL file to test optional copy
    mock_wal_file = mock_db_dir / "sten_f.db-wal"
    mock_wal_file.write_text("DUMMY_WAL_DATA", encoding="utf-8")
    
    # Also create a dummy uploaded_files directory to ensure it is NOT copied
    mock_uploads = mock_root / "uploaded_files"
    mock_uploads.mkdir()
    (mock_uploads / "test.pdf").write_text("PDF", encoding="utf-8")

    # Set up target backup directory
    target_backup_dir = tmp_path / "backups"
    
    try:
        # Patch settings
        settings.PROJECT_ROOT = mock_root
        settings.DATABASE_URL = f"sqlite+aiosqlite:///{mock_db_file}"
        
        yield target_backup_dir, mock_db_dir, mock_uploads
    finally:
        # Restore original settings
        settings.PROJECT_ROOT = original_project_root
        settings.DATABASE_URL = original_database_url


@pytest.mark.asyncio
async def test_create_backup_success(temp_backup_env):
    target_backup_dir, mock_db_dir, mock_uploads = temp_backup_env
    
    service = BackupService()
    
    # Run backup
    backup_path_str = await service.create_backup(str(target_backup_dir))
    backup_path = Path(backup_path_str)
    
    # Verify backup directory creation
    assert backup_path.exists()
    assert backup_path.is_dir()
    
    # Verify DB file copy
    copied_db = backup_path / "sten_f.db"
    assert copied_db.exists()
    assert copied_db.read_text() == "DUMMY_DB_DATA"
    
    # Verify WAL file copy
    copied_wal = backup_path / "sten_f.db-wal"
    assert copied_wal.exists()
    assert copied_wal.read_text() == "DUMMY_WAL_DATA"
    
    # Verify .env file copy
    copied_env = backup_path / ".env"
    assert copied_env.exists()
    assert copied_env.read_text() == "DUMMY_ENV=123"
    
    # Verify uploaded_files is NOT copied
    assert not (backup_path / "uploaded_files").exists()
    
    # Check parent directory name is timestamp format roughly
    assert len(backup_path.name) == 15  # e.g. YYYYMMDD_HHMMSS
    assert "_" in backup_path.name

@pytest.mark.asyncio
async def test_create_backup_no_target_dir():
    service = BackupService()
    
    with pytest.raises(ValueError, match="バックアップ先ディレクトリが指定されていません"):
        await service.create_backup("")
