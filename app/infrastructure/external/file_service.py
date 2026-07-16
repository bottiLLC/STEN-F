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

import os
from datetime import date
from pathlib import Path

# Helper to find storage dir relative to V2 app
# Or we can share the same storage as V1?
# Let's share for now or put in v2/storage
# User wants "seamless", so maybe sharing is better? 
# But V2 is "Zero-Based". Let's use a v2 storage for cleanliness unless specified.
# Actually, V1 used config.BASE_DIR.
# Let's define V2 BASE_DIR.

V2_BASE_DIR = Path(__file__).parent.parent.parent.parent

class LocalFileService:
    def __init__(self, base_dir: Path = V2_BASE_DIR):
        self.storage_dir = base_dir / "storage"
        self.storage_dir.mkdir(exist_ok=True)

    async def save_evidence(self, file_bytes: bytes, original_filename: str, date_obj: date, description: str, amount: int) -> str:
        """
        Saves the evidence file with a standardized name.
        Format: YYYY-MM-DD_Store_Amount.pdf
        Returns the absolute path of the saved file.
        """
        
        # Sanitize description for filename
        safe_desc = "".join(c for c in description if c.isalnum() or c in (' ', '_', '-')).strip()
        
        # Get extension
        ext = os.path.splitext(original_filename)[1]
        if not ext:
            ext = ".pdf" # default fallback
            
        new_filename = f"{date_obj}_{safe_desc}_{amount}{ext}"
        save_path = self.storage_dir / new_filename
        
        import aiofiles  # type: ignore
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
            
        return str(save_path)

    async def save_evidence_for_transaction(self, file_bytes: bytes, transaction_id: int, date_obj: date, amount: int, corp_name: str) -> str:
        """
        Saves evidence with Dencho Act compliant filename:
        YYYYMMDD_{Amount}_{NormalizedCorp}_{ID}.pdf
        """
        # Normalize corp name (remove typical legal entities for brevity)
        normalized_corp = corp_name.replace("株式会社", "").replace("合同会社", "").replace("有限会社", "").strip()
        safe_corp = "".join(c for c in normalized_corp if c.isalnum() or c in (' ', '_', '-')).strip()
        
        filename = f"{date_obj.strftime('%Y%m%d')}_{amount}_{safe_corp}_{transaction_id}.pdf"
        save_path = self.storage_dir / filename
        
        import aiofiles
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
            
        return str(save_path)
