@echo off
REM ============================================
REM Start Paper Trading Session
REM ============================================

echo.
echo ====================================
echo  STARTING PAPER TRADING
echo ====================================
echo.
echo Mode: PAPER (Safe - No Real Money)
echo Symbol: XAUUSD
echo Timeframe: M15
echo.
echo Press Ctrl+C to stop
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Set Python path
set PYTHONPATH=%CD%\python

REM Start trading system
python python\valuecell\trading_system.py --mode paper
