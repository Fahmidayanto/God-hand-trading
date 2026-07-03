@echo off
set PYTHONUTF8=1
REM ========================================
REM  Start Backend Server
REM ========================================
echo.
echo ========================================
echo   Starting ValueCell Backend Server
echo ========================================
echo.

REM Change to ValueCell_MT5 folder
echo [1/3] Changing to ValueCell_MT5 folder...
cd /d "%~dp0ValueCell_MT5"

REM Activate virtual environment
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Change to backend folder and start uvicorn
echo [3/3] Starting uvicorn server...
echo.
echo Server running at:
echo   - Local:    http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ========================================
echo.

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
