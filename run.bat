@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ===================================================
echo  Antigravity Reflex アプリケーション起動スクリプト
echo ===================================================

cd /d "%~dp0"

:: .venv の存在チェックと初期化
if not exist ".venv" (
    echo [INFO] 仮想環境（.venv）が見つかりません。初期設定を開始します...
    echo [INFO] uv を使用して依存関係を同期しています...
    uv sync
    if !errorlevel! neq 0 (
        echo [ERROR] 環境の初期化に失敗しました。pyproject.toml を確認してください。
        pause
        exit /b !errorlevel!
    )
    echo [INFO] 環境構築が完了しました。
)

:: ブラウザ自動起動（バックグラウンドで8秒後に起動）
echo [INFO] ブラウザ自動起動タスクを開始しています...
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:3000"

:: アプリケーションの起動
echo [INFO] Reflex アプリケーションを起動しています...
uv run reflex run

if !errorlevel! neq 0 (
    echo [WARNING] アプリケーションが異常終了したか、または停止されました。
    pause
)
