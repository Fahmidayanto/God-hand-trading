@echo off
REM ========================================
REM  Start Frontend Dev Server
REM ========================================
echo.
echo ========================================
echo   Starting ValueCell Frontend Server
echo ========================================
echo.

REM Change to ValueCell_MT5 folder
echo [1/2] Changing to ValueCell_MT5/frontend folder...
cd /d "%~dp0ValueCell_MT5\frontend"

REM Start dev server
echo [2/2] Running npm run dev...
echo.
echo Press Ctrl+C to stop the server.
echo ========================================
echo.

npm run dev

pause
