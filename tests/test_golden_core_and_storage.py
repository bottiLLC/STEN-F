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

"""
First Stage Golden Master Test: Core Utilities & External Storage Services
Testing ONLY public API, mocking ONLY external boundary (filesystem/settings).
"""

from datetime import date
from pathlib import Path
import pytest

from app.core.utils import normalize_amount
from app.infrastructure.external.file_service import LocalFileService
from app.infrastructure.external.backup_service import BackupService


def test_golden_normalize_amount():
    # Null / empty
    assert normalize_amount(None) == 0
    assert normalize_amount("") == 0
    assert normalize_amount("   ") == 0

    # Numeric types
    assert normalize_amount(1000) == 1000
    assert normalize_amount(1234.56) == 1235
    assert normalize_amount(1234.4) == 1234

    # String with fullwidth numbers, commas, spaces
    assert normalize_amount("１２，３４５円") == 0  # Invalid due to trailing '円'
    assert normalize_amount("１２，３４５") == 12345
    assert normalize_amount(" 1,000,000 ") == 1000000
    assert normalize_amount("　５００　") == 500
    assert normalize_amount("invalid_string") == 0


@pytest.mark.asyncio
async def test_golden_local_file_service(tmp_path: Path):
    service = LocalFileService(base_dir=tmp_path)
    assert (tmp_path / "storage").exists()

    # 1. save_evidence
    raw_data = b"%PDF-1.4 dummy file content"
    saved_path_str = await service.save_evidence(
        file_bytes=raw_data,
        original_filename="receipt.pdf",
        date_obj=date(2026, 4, 1),
        description="Office Supplies / PC",
        amount=15000,
    )
    saved_path = Path(saved_path_str)
    assert saved_path.exists()
    assert saved_path.read_bytes() == raw_data
    assert "2026-04-01" in saved_path.name
    assert "15000.pdf" in saved_path.name

    # 2. save_evidence_for_transaction
    saved_tx_path_str = await service.save_evidence_for_transaction(
        file_bytes=raw_data,
        transaction_id=42,
        date_obj=date(2026, 4, 1),
        amount=25000,
        corp_name="株式会社テスト商事",
    )
    saved_tx_path = Path(saved_tx_path_str)
    assert saved_tx_path.exists()
    assert saved_tx_path.read_bytes() == raw_data
    assert "20260401_25000_テスト商事_42.pdf" in saved_tx_path.name


@pytest.mark.asyncio
async def test_golden_backup_service(tmp_path: Path, monkeypatch):
    service = BackupService()

    # Empty target dir error
    with pytest.raises(ValueError, match="バックアップ先ディレクトリが指定されていません"):
        await service.create_backup("")

    # Prepare dummy SQLite database and .env in tmp_path
    db_file = tmp_path / "sten_f.db"
    db_file.write_bytes(b"SQLite format 3\x00dummy-db-content")
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY_KEY=12345", encoding="utf-8")

    monkeypatch.setattr("app.config.settings.DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr("app.config.settings.PROJECT_ROOT", tmp_path)

    target_backup_dir = tmp_path / "backups"
    backup_result_path_str = await service.create_backup(str(target_backup_dir))

    backup_result_dir = Path(backup_result_path_str)
    assert backup_result_dir.exists()
    assert backup_result_dir.is_dir()
    assert (backup_result_dir / "sten_f.db").exists()
    assert (backup_result_dir / "sten_f.db").read_bytes() == b"SQLite format 3\x00dummy-db-content"
    assert (backup_result_dir / ".env").exists()
    assert (backup_result_dir / ".env").read_text(encoding="utf-8") == "DUMMY_KEY=12345"
