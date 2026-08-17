@echo off
chcp 65001 >nul
title Project MT5 - Frontend Dashboard

echo ===================================================
echo   Project MT5 - Frontend Dashboard (React Router)
echo ===================================================
echo.

REM Navigate to frontend directory
echo [1/2] Navigating to ValueCell_MT5/frontend...
cd /d "%~dp0ValueCell_MT5\frontend"

if not exist "package.json" (
    echo [ERROR] package.json not found in ValueCell_MT5\frontend!
    pause
    exit /b 1
)

REM Start dev server
echo [2/2] Running npm run dev...
echo.
echo Dashboard running at: http://localhost:5173
echo.
echo Press Ctrl+C to stop the server.
echo ===================================================
echo.

npm run dev

pause
