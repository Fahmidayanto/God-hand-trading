@echo off
set PYTHONUTF8=1
echo.
echo ============================================================
echo   Headroom Real-time Token Savings Monitor
echo ============================================================
echo.

cd /d "%~dp0ValueCell_MT5"
call venv\Scripts\activate.bat

python scripts/monitor_headroom.py

pause
