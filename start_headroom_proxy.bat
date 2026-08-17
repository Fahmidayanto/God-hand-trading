@echo off
set PYTHONUTF8=1
REM ========================================
REM  Start Headroom Local Proxy Server (Port 8787)
REM ========================================
echo.
echo ========================================
echo   Starting Headroom Local Proxy Server
echo ========================================
echo.

REM Change to ValueCell_MT5 folder
echo [1/2] Changing to ValueCell_MT5 folder...
cd /d "%~dp0ValueCell_MT5"

REM Activate virtual environment
echo [2/2] Activating virtual environment and launching Headroom Proxy...
call venv\Scripts\activate.bat

echo.
echo Headroom Proxy running at:
echo   - Local Proxy: http://127.0.0.1:8787
echo.
echo Press Ctrl+C to stop the proxy server.
echo ========================================
echo.

set LITELLM_LOG=ERROR

headroom proxy --port 8787

pause
