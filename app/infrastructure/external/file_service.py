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

from datetime import date
import os
from pathlib import Path
import aiofiles
from app.config import settings


class LocalFileService:
    def __init__(self, base_dir: Path = settings.PROJECT_ROOT):
        self.storage_dir = base_dir / "storage"
        self.storage_dir.mkdir(exist_ok=True)

    async def save_evidence(
        self,
        file_bytes: bytes,
        original_filename: str,
        date_obj: date,
        description: str,
        amount: int,
    ) -> str:
        safe_desc = "".join(
            c for c in description if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        ext = os.path.splitext(original_filename)[1] or ".pdf"
        save_path = self.storage_dir / f"{date_obj}_{safe_desc}_{amount}{ext}"
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
        return str(save_path)

    async def save_evidence_for_transaction(
        self,
        file_bytes: bytes,
        transaction_id: int,
        date_obj: date,
        amount: int,
        corp_name: str,
    ) -> str:
        norm_corp = (
            corp_name.replace("株式会社", "")
            .replace("合同会社", "")
            .replace("有限会社", "")
            .strip()
        )
        safe_corp = "".join(
            c for c in norm_corp if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        save_path = (
            self.storage_dir
            / f"{date_obj.strftime('%Y%m%d')}_{amount}_{safe_corp}_{transaction_id}.pdf"
        )
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
        return str(save_path)
