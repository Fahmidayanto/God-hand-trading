@echo off
REM ValueCell Backend Server Startup Script
REM Starts FastAPI/Uvicorn server with trading dashboard API

echo ========================================
echo ValueCell Trading Dashboard - Backend
echo ========================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Set environment variables
echo [2/3] Setting environment variables...
set API_HOST=0.0.0.0
set API_PORT=8000
set API_DEBUG=true
set CORS_ORIGINS=["http://localhost:3000","http://localhost:8000","http://127.0.0.1:3000","http://127.0.0.1:8000","file://"]

REM Start server
echo [3/3] Starting FastAPI server...
echo.
echo Server will be available at:
echo   - Local:   http://localhost:8000
echo   - Network: http://0.0.0.0:8000
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd python
python -m uvicorn valuecell.server.main:app --host 0.0.0.0 --port 8000 --reload

pause
