@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting STEN-F Application...

REM Launch browser in the background after 8 seconds
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:3000"

uv run reflex run
pause
