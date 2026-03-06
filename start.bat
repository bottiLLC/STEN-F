@echo off
cd /d %~dp0
echo STEN-F 起動準備中...

:: バックグラウンドで約6秒待機してからブラウザを開く
start "" cmd /c "ping localhost -n 7 >nul & start http://localhost:3000"

uv run reflex run
pause
