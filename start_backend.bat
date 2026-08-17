@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Project MT5 - Backend Server

echo ===================================================
echo   Project MT5 - Backend Server (FastAPI / Uvicorn)
echo ===================================================
echo.

REM Navigate to ValueCell_MT5 directory
echo [1/3] Navigating to ValueCell_MT5...
cd /d "%~dp0ValueCell_MT5"

REM Check and activate virtual environment
echo [2/3] Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment venv not found in ValueCell_MT5!
    pause
    exit /b 1
)

REM Navigate to backend folder and start uvicorn
echo [3/3] Starting Uvicorn backend server...
echo.
echo Server running at:
echo   - Local:    http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ===================================================
echo.

cd backend
"%~dp0ValueCell_MT5\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --reload-dir . --reload-dir ../python --host 0.0.0.0 --port 8000

pause
