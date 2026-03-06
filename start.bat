@echo off
cd /d %~dp0
echo STEN-F 起動準備中...

:: 別プロセスとして約7秒待機後にブラウザを起動させる（メインプロセスを止めない）
start "" cmd /c "timeout /t 7 /nobreak >nul && start http://localhost:3000"

uv run reflex run
pause
