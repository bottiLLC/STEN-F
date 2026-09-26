# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Callable
from unittest.mock import patch
import zipfile

import pytest

import backup_manager
from backup_manager import (
    get_backup_dir,
    run_backup,
    set_backup_dir,
)

_app_path = Path(__file__).resolve().parent.parent / "app.py"
_spec = importlib.util.spec_from_file_location("main_app", _app_path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Failed to load app.py specification")
_app_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_app_module)
_render_sidebar_backup: Callable[[], None] = _app_module._render_sidebar_backup


# ---------------------------------------------------------------------------
# 1. get_backup_dir Tests
# ---------------------------------------------------------------------------


def test_get_backup_dir_from_valid_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系] backup_config.json にカスタムパスが設定されている場合、その解決パスが返されることを検証"""
    # Arrange
    config_file = tmp_path / "backup_config.json"
    target_dir = tmp_path / "custom_backups"
    config_file.write_text(
        json.dumps({"backup_dir": str(target_dir)}), encoding="utf-8"
    )
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)

    # Act
    resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == target_dir.resolve()


def test_get_backup_dir_fallback_on_corrupt_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[異常系/境界値] backup_config.json が不正なJSONの場合、環境変数またはデフォルトパスへフォールバックすることを検証"""
    # Arrange
    config_file = tmp_path / "backup_config.json"
    config_file.write_text("NOT_VALID_JSON{{{", encoding="utf-8")
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    default_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "_DEFAULT_BACKUP_DIR", default_dir)

    # Act
    resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == default_dir.resolve()


def test_get_backup_dir_fallback_on_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[異常系/境界値] backup_config.json のオープン時に OSError が発生した場合、フォールバックすることを検証"""
    # Arrange
    config_file = tmp_path / "backup_config.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    default_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "_DEFAULT_BACKUP_DIR", default_dir)

    with patch("builtins.open", side_effect=OSError("Permission denied")):
        # Act
        resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == default_dir.resolve()


def test_get_backup_dir_fallback_on_empty_config_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[異常系/境界値] backup_config.json に backup_dir キーが空文字または存在しない場合、フォールバックすることを検証"""
    # Arrange
    config_file = tmp_path / "backup_config.json"
    config_file.write_text(
        json.dumps({"other_key": "val", "backup_dir": ""}), encoding="utf-8"
    )
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    default_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "_DEFAULT_BACKUP_DIR", default_dir)

    # Act
    resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == default_dir.resolve()


def test_get_backup_dir_from_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系] 設定ファイルが存在せず環境変数 BACKUP_DIR が指定されている場合、環境変数の解決パスが返されることを検証"""
    # Arrange
    nonexistent_config = tmp_path / "nonexistent" / "backup_config.json"
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", nonexistent_config)
    env_dir = tmp_path / "env_backups"
    monkeypatch.setenv("BACKUP_DIR", str(env_dir))

    # Act
    resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == env_dir.resolve()


def test_get_backup_dir_default_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系/デフォルト] 設定ファイルも環境変数も存在しない場合、デフォルトパス (./backups) が返されることを検証"""
    # Arrange
    nonexistent_config = tmp_path / "nonexistent" / "backup_config.json"
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", nonexistent_config)
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    default_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "_DEFAULT_BACKUP_DIR", default_dir)

    # Act
    resolved_dir = get_backup_dir()

    # Assert
    assert resolved_dir == default_dir.resolve()


# ---------------------------------------------------------------------------
# 2. set_backup_dir Tests
# ---------------------------------------------------------------------------


def test_set_backup_dir_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系] 保存先ディレクトリを正しく設定し、backup_config.json に永続化できることを検証"""
    # Arrange
    config_file = tmp_path / "data" / "backup_config.json"
    target_dir = tmp_path / "my_backups"
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)

    # Act
    result = set_backup_dir(str(target_dir))

    # Assert
    assert result["success"] is True
    assert "バックアップ先を設定しました" in str(result["message"])
    assert target_dir.resolve().exists()
    assert config_file.exists()
    saved_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_data["backup_dir"] == str(target_dir.resolve())


def test_set_backup_dir_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[異常系] 書き込み権限がない場合など OSError 発生時に適切なエラー辞書が返されることを検証"""
    # Arrange
    config_file = tmp_path / "data" / "backup_config.json"
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)

    # Act
    with patch.object(Path, "mkdir", side_effect=OSError("Read-only filesystem")):
        result = set_backup_dir(str(tmp_path / "invalid_path"))

    # Assert
    assert result["success"] is False
    assert "保存先パスが無効、または書き込み権限がありません" in str(result["message"])
    assert "Read-only filesystem" in str(result["message"])


# ---------------------------------------------------------------------------
# 3. run_backup Tests
# ---------------------------------------------------------------------------


def test_run_backup_interlock_source_not_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[インターロック検証] バックアップ元ディレクトリが存在しない場合、直ちに失敗を返すことを検証"""
    # Arrange
    nonexistent = tmp_path / "nonexistent_data"

    # Act
    result = run_backup(app_name="sten_f", source_dir=str(nonexistent))

    # Assert
    assert result["success"] is False
    assert "バックアップ対象が存在しないか空欄です" in str(result["message"])
    assert "timestamp" in result


def test_run_backup_interlock_source_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[インターロック検証] バックアップ元ディレクトリが空の場合、直ちに失敗を返すことを検証"""
    # Arrange
    empty_dir = tmp_path / "empty_data"
    empty_dir.mkdir(parents=True, exist_ok=True)

    # Act
    result = run_backup(app_name="sten_f", source_dir=str(empty_dir))

    # Assert
    assert result["success"] is False
    assert "バックアップ対象が存在しないか空欄です" in str(result["message"])
    assert "timestamp" in result


def test_run_backup_interlock_destination_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[インターロック検証] 保存先ディレクトリの作成に失敗した場合、適切なエラーを返すことを検証"""
    # Arrange
    source_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.db").write_text("dummy db", encoding="utf-8")

    dest_dir = tmp_path / "protected_backups"
    monkeypatch.setattr(backup_manager, "get_backup_dir", lambda: dest_dir)

    # Act
    with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
        result = run_backup(app_name="sten_f", source_dir=str(source_dir))

    # Assert
    assert result["success"] is False
    assert "保存先フォルダの作成に失敗しました" in str(result["message"])
    assert "Permission denied" in str(result["message"])


def test_run_backup_integrity_check_detects_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[整合性検証] testzip() で破損が検出された場合、確定配置を中止して失敗を返すことを検証"""
    # Arrange
    source_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.db").write_text("dummy db", encoding="utf-8")

    dest_dir = tmp_path / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(backup_manager, "get_backup_dir", lambda: dest_dir)

    # Act: testzip が破損ファイル名を返すようモック
    with patch.object(zipfile.ZipFile, "testzip", return_value="sample.db"):
        result = run_backup(app_name="sten_f", source_dir=str(source_dir))

    # Assert
    assert result["success"] is False
    assert "整合性チェック失敗（破損検知）: sample.db" in str(result["message"])
    # 破損時は最終保存先にZIPファイルが配置されていないこと
    assert len(list(dest_dir.glob("*.zip"))) == 0


def test_run_backup_atomic_move_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[異常系] shutil.move 失敗時にエラーを返し、例外を握りつぶさず適切にハンドリングすることを検証"""
    # Arrange
    source_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.db").write_text("dummy db", encoding="utf-8")

    dest_dir = tmp_path / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(backup_manager, "get_backup_dir", lambda: dest_dir)

    # Act
    with patch("shutil.move", side_effect=OSError("Disk full")):
        result = run_backup(app_name="sten_f", source_dir=str(source_dir))

    # Assert
    assert result["success"] is False
    assert "バックアップファイルの確定移動に失敗しました" in str(result["message"])
    assert "Disk full" in str(result["message"])


def test_run_backup_success_small_file_kb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系/KB表記] 1MB未満のデータバックアップが正常に作成・検証・移動され、configが除外されることを検証"""
    # Arrange
    source_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sten_f.db").write_bytes(b"SQLite dummy header and records")
    (source_dir / ".env").write_text("GEMINI_API_KEY=test", encoding="utf-8")

    # Exclude target: config file itself
    config_file = source_dir / "backup_config.json"
    config_file.write_text(json.dumps({"backup_dir": "ignored"}), encoding="utf-8")
    monkeypatch.setattr(backup_manager, "_CONFIG_FILE", config_file)

    # Subdirectory with receipt file
    receipt_dir = source_dir / "storage"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "receipt_001.pdf").write_bytes(b"%PDF dummy receipt content")

    dest_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "get_backup_dir", lambda: dest_dir)

    # Act
    result = run_backup(app_name="sten_f", source_dir=str(source_dir))

    # Assert
    assert result["success"] is True
    assert "バックアップ完了: sten_f_backup_" in str(result["message"])
    assert "KB" in str(result["size"])
    destination = Path(str(result["destination"]))
    assert destination.exists()
    assert destination.parent == dest_dir.resolve()

    # Verify ZIP contents
    with zipfile.ZipFile(destination, "r") as zf:
        namelist = zf.namelist()
        assert "sten_f.db" in namelist
        assert ".env" in namelist
        assert "storage/receipt_001.pdf" in namelist
        # Configuration file must be strictly excluded
        assert "backup_config.json" not in namelist
        assert zf.testzip() is None


def test_run_backup_success_large_file_mb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[正常系/MB表記] 1MB以上のデータバックアップでサイズ表示が MB 単位になることを検証"""
    # Arrange
    source_dir = tmp_path / "data"
    source_dir.mkdir(parents=True, exist_ok=True)
    # 1.2MB uncompressible random bytes so compressed ZIP > 1MB
    import os

    (source_dir / "large.bin").write_bytes(os.urandom(1_200_000))

    dest_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_manager, "get_backup_dir", lambda: dest_dir)

    # Act
    result = run_backup(app_name="app", source_dir=str(source_dir))

    # Assert
    assert result["success"] is True
    assert "MB" in str(result["size"])
    destination = Path(str(result["destination"]))
    assert destination.exists()


# ---------------------------------------------------------------------------
# 4. Streamlit UI Integration (_render_sidebar_backup) Tests
# ---------------------------------------------------------------------------


def test_render_sidebar_backup_update_destination_success() -> None:
    """[UI検証] 保存先フォルダ変更時に「保存先パスを更新」ボタン押下で set_backup_dir と st.rerun が実行されることを検証"""
    with (
        patch("streamlit.sidebar"),
        patch("streamlit.divider"),
        patch("streamlit.subheader"),
        patch.object(_app_module, "get_backup_dir", return_value=Path("/old/path")),
        patch("streamlit.text_input", return_value="/new/custom/path"),
        patch("streamlit.button", side_effect=[True, False]),
        patch.object(
            _app_module,
            "set_backup_dir",
            return_value={
                "success": True,
                "message": "バックアップ先を設定しました: /new/custom/path",
            },
        ) as mock_set,
        patch("streamlit.success") as mock_success,
        patch("streamlit.rerun") as mock_rerun,
    ):
        _render_sidebar_backup()

        mock_set.assert_called_once_with("/new/custom/path")
        mock_success.assert_called_once_with(
            "バックアップ先を設定しました: /new/custom/path"
        )
        mock_rerun.assert_called_once()


def test_render_sidebar_backup_update_destination_failure() -> None:
    """[UI検証] 保存先フォルダ更新失敗時に st.error が正しく表示されることを検証"""
    with (
        patch("streamlit.sidebar"),
        patch("streamlit.divider"),
        patch("streamlit.subheader"),
        patch.object(_app_module, "get_backup_dir", return_value=Path("/old/path")),
        patch("streamlit.text_input", return_value="/invalid/path"),
        patch("streamlit.button", side_effect=[True, False]),
        patch.object(
            _app_module,
            "set_backup_dir",
            return_value={
                "success": False,
                "message": "保存先パスが無効、または書き込み権限がありません",
            },
        ) as mock_set,
        patch("streamlit.error") as mock_error,
    ):
        _render_sidebar_backup()

        mock_set.assert_called_once_with("/invalid/path")
        mock_error.assert_called_once_with(
            "保存先パスが無効、または書き込み権限がありません"
        )


def test_render_sidebar_backup_run_backup_success() -> None:
    """[UI検証] 「今すぐバックアップを実行」押下時にスピナー表示および完了情報（日時・保存先）が表示されることを検証"""
    target_path = Path("/app/backups").resolve()
    with (
        patch("streamlit.sidebar"),
        patch("streamlit.divider"),
        patch("streamlit.subheader"),
        patch.object(_app_module, "get_backup_dir", return_value=target_path),
        patch("streamlit.text_input", return_value=str(target_path)),
        patch("streamlit.button", return_value=True),
        patch("streamlit.spinner"),
        patch.object(
            _app_module,
            "run_backup",
            return_value={
                "success": True,
                "message": "バックアップ完了: app_backup_20260926_120000.zip (10.00 KB)",
                "timestamp": "2026-09-26 12:00:00",
                "destination": "/app/backups/app_backup_20260926_120000.zip",
            },
        ) as mock_run,
        patch("streamlit.success") as mock_success,
        patch("streamlit.caption") as mock_caption,
    ):
        _render_sidebar_backup()

        mock_run.assert_called_once_with(app_name="app")
        mock_success.assert_called_once_with(
            "バックアップ完了: app_backup_20260926_120000.zip (10.00 KB)"
        )
        mock_caption.assert_any_call("完了日時: 2026-09-26 12:00:00")
        mock_caption.assert_any_call(
            "保存先: /app/backups/app_backup_20260926_120000.zip"
        )


def test_render_sidebar_backup_run_backup_failure() -> None:
    """[UI検証] バックアップ実行失敗時に st.error が正しく表示されることを検証"""
    target_path = Path("/app/backups").resolve()
    with (
        patch("streamlit.sidebar"),
        patch("streamlit.divider"),
        patch("streamlit.subheader"),
        patch.object(_app_module, "get_backup_dir", return_value=target_path),
        patch("streamlit.text_input", return_value=str(target_path)),
        patch("streamlit.button", return_value=True),
        patch("streamlit.spinner"),
        patch.object(
            _app_module,
            "run_backup",
            return_value={
                "success": False,
                "message": "バックアップ対象が存在しないか空欄です: ./data",
            },
        ),
        patch("streamlit.error") as mock_error,
    ):
        _render_sidebar_backup()

        mock_error.assert_called_once_with(
            "バックアップ対象が存在しないか空欄です: ./data"
        )
