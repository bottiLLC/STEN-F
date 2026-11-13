# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Local filesystem evidence storage service conforming to statutory naming standards."""

from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path

import aiofiles

from app.core_foundation import settings


def _sanitize_file_name(text: str) -> str:
    """Sanitize filename to alphanumeric and safe delimiter characters.

    Args:
        text: Raw filename or description string.

    Returns:
        Cleaned filename string.
    """
    return "".join(c for c in text if c.isalnum() or c in " _-").strip()


class LocalFileService:
    """Service persisting local evidence documents with statutory naming standards."""

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize and verify local storage directory.

        Args:
            base_dir: Optional base directory path anchoring storage directory.
                      Defaults to settings.STORAGE_DIR (data/storage).
        """
        if base_dir is not None:
            self.storage_dir = (
                base_dir if base_dir.name == "storage" else base_dir / "storage"
            )
        else:
            self.storage_dir = settings.STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def resolve_evidence_path(self, path_str: str) -> Path | None:
        """Resolve evidence file path safely handling environment migrations.

        Args:
            path_str: Stored filesystem path or filename.

        Returns:
            Existing Path object, or None if not found.
        """
        candidate = Path(path_str)
        if candidate.exists() and candidate.is_file():
            return candidate

        fallback = self.storage_dir / candidate.name
        if fallback.exists() and fallback.is_file():
            return fallback

        return None

    async def save_evidence_for_transaction(
        self,
        file_bytes: bytes,
        transaction_id: int | None = None,
        date_obj: date = date.today(),
        amount: int = 0,
        corp_name: str = "Unknown",
        extension: str = ".pdf",
    ) -> str:
        """Persist evidence file bound to transaction id or content hash under legal standard naming.

        Args:
            file_bytes: Raw binary file payload.
            transaction_id: Optional associated transaction ID. If None, content hash is used.
            date_obj: Transaction date.
            amount: Transaction absolute amount.
            corp_name: Vendor or counterparty name.
            extension: File extension suffix (defaults to .pdf).

        Returns:
            Saved filesystem path string.
        """
        clean_name = corp_name
        for prefix in ("株式会社", "合同会社", "有限会社"):
            clean_name = clean_name.replace(prefix, "")
        ext = extension if extension.startswith(".") else f".{extension}"
        suffix_id = (
            str(transaction_id)
            if transaction_id is not None
            else hashlib.sha256(file_bytes).hexdigest()[:8]
        )
        save_path = (
            self.storage_dir
            / f"{date_obj.strftime('%Y%m%d')}_{amount}_{_sanitize_file_name(clean_name)}_{suffix_id}{ext}"
        )
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
        return str(save_path)
