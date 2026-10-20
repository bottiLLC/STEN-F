from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Final
import zipfile

_ROOT: Final[Path] = Path(__file__).resolve().parent
_CONFIG_FILE: Final[Path] = _ROOT / "data" / "backup_config.json"
_DEFAULT_BACKUP_DIR: Final[Path] = _ROOT / "data" / "backups"


def get_backup_dir() -> Path:
    """Retrieve resolved destination directory path for data backups.

    Returns:
        Resolved Path object pointing to the configured or default backup directory.
    """
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
                custom_path = data.get("backup_dir")
                if custom_path:
                    return Path(custom_path).resolve()
        except OSError, json.JSONDecodeError:
            pass

    env_dir = os.getenv("BACKUP_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    return _DEFAULT_BACKUP_DIR.resolve()


def set_backup_dir(target_dir: str) -> dict[str, str | bool]:
    """Configure and persist destination directory path for data backups.

    Args:
        target_dir: Filesystem path string for the target backup directory.

    Returns:
        Dictionary containing success flag and user-facing status message.
    """
    path = Path(target_dir).resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"backup_dir": str(path)}, f, indent=2)
        return {"success": True, "message": f"バックアップ先を設定しました: {path!s}"}
    except OSError as e:
        return {
            "success": False,
            "message": f"保存先パスが無効、または書き込み権限がありません: {e!s}",
        }


def run_backup(
    app_name: str = "app", source_dir: str | None = None
) -> dict[str, str | bool]:
    """Execute atomic data backup with testzip integrity verification.

    Args:
        app_name: Application prefix used for output archive naming.
        source_dir: Target directory to back up. Defaults to project-anchored data directory.

    Returns:
        Dictionary containing success status, archive metadata, and feedback message.
    """
    source_path = (
        Path(source_dir).resolve() if source_dir else (_ROOT / "data").resolve()
    )

    # 1. Interlock: Source presence
    if not source_path.exists() or not any(source_path.iterdir()):
        return {
            "success": False,
            "message": f"バックアップ対象が存在しないか空欄です: {source_path}",
            "timestamp": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # 2. Interlock: Destination resolution
    backup_dir = get_backup_dir()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {
            "success": False,
            "message": f"保存先フォルダの作成に失敗しました: {e!s}",
            "timestamp": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        }

    now = datetime.now(UTC).astimezone()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{app_name}_backup_{timestamp_str}.zip"
    final_destination = backup_dir / zip_filename

    # 3. Atomic processing in temp directory
    resolved_backup_dir = backup_dir.resolve()
    resolved_config_file = _CONFIG_FILE.resolve()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_zip = Path(tmp_dir) / zip_filename

        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_path.rglob("*"):
                # Exclude directories, backup config file, and backup destination folder
                if not file_path.is_file():
                    continue
                resolved_file = file_path.resolve()
                if resolved_file == resolved_config_file:
                    continue
                if resolved_file.is_relative_to(resolved_backup_dir):
                    continue

                zipf.write(file_path, file_path.relative_to(source_path))

        # 4. Integrity check (testzip)
        with zipfile.ZipFile(tmp_zip, "r") as zipf:
            corrupt = zipf.testzip()
            if corrupt is not None:
                return {
                    "success": False,
                    "message": f"整合性チェック失敗（破損検知）: {corrupt}",
                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                }

        # 5. Atomic move with OS-level error protection
        file_size = tmp_zip.stat().st_size
        try:
            shutil.move(str(tmp_zip), str(final_destination))
        except OSError as e:
            return {
                "success": False,
                "message": f"バックアップファイルの確定移動に失敗しました: {e!s}",
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            }

    size_str = (
        f"{file_size / (1024 * 1024):.2f} MB"
        if file_size >= 1024 * 1024
        else f"{file_size / 1024:.2f} KB"
    )

    return {
        "success": True,
        "filename": zip_filename,
        "size": size_str,
        "destination": str(final_destination),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "message": f"バックアップ完了: {zip_filename} ({size_str})",
    }
