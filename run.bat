@echo off

echo ===================================================
echo  STEN-F Reflex Application Boot Script
echo ===================================================

cd /d "%~dp0"

:: Check if uv is installed
where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv command not found.
    echo [ERROR] Please make sure Astral uv is installed and added to your PATH.
    echo [ERROR] Refer to official installation guide.
    pause
    exit /b 1
)

:: Initialize virtual environment if it doesn't exist
if not exist ".venv" (
    echo [INFO] Virtual environment (.venv) not found. Initializing...
    echo [INFO] Syncing dependencies using uv...
    uv sync
    if errorlevel 1 (
        echo [ERROR] Environment initialization failed. Please check pyproject.toml.
        pause
        exit /b 1
    )
    echo [INFO] Environment setup completed successfully.
)

:: Start browser in background after 8 seconds
echo [INFO] Starting browser automation...
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:3000"

:: Start application
echo [INFO] Starting Reflex application...
uv run reflex run

if errorlevel 1 (
    echo [WARNING] Application terminated unexpectedly or stopped.
    pause
)

