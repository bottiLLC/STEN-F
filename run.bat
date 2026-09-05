@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   STEN-F Launcher (Windows)
echo ===================================================
echo.

:: 1. Auto-detect Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python and ensure it is added to your environment variables.
    echo.
    pause
    exit /b 1
)

:: 2. Bootstrap 'uv' via Python pip if missing
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] 'uv' package manager not found. Bootstrapping via pip...
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install uv
    if errorlevel 1 (
        echo [ERROR] Failed to install 'uv'.
        echo.
        pause
        exit /b 1
    )
    echo [INFO] 'uv' installed successfully.
)

:: 3. Detect Entry Point
set ENTRY_POINT=app.py
if not exist "app.py" (
    if exist "main.py" (
        set ENTRY_POINT=main.py
    ) else (
        echo [ERROR] Entry point app.py not found.
        echo.
        pause
        exit /b 1
    )
)

:: 4. Sync Dependencies
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    call uv venv
)

if exist "pyproject.toml" (
    echo [INFO] Syncing dependencies...
    call uv sync
)

:: 5. Launch Application
echo.
echo [INFO] Launching %ENTRY_POINT% with Streamlit ...
echo.

call uv run streamlit run "%ENTRY_POINT%" --server.headless false

if errorlevel 1 (
    echo.
    echo [WARNING] Application stopped or encountered an error.
)

echo.
pause
