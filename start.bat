@echo off
cd /d %~dp0
echo STEN-F 起動準備中...

:: バックグラウンドでPythonを使用して7秒後にブラウザを開く
start /B "" uv run python -c "import webbrowser, time; time.sleep(7); webbrowser.open('http://localhost:3000')"

uv run reflex run
pause
