@echo off
REM Start Trading System in PAPER TRADING MODE
REM Location: d:\Project\Project MT5\ValueCell_MT5\start_trading_paper.bat

echo ========================================
echo Multi-Agent Trading System
echo ========================================
echo.
echo Mode: PAPER TRADING (Safe - No Real Money)
echo Symbol: XAUUSD
echo Timeframe: M15
echo Check Interval: 5 seconds
echo.
echo Press Ctrl+C to stop
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start trading system
python -m valuecell.trading_system --mode paper --symbol XAUUSD --timeframe M15 --interval 5

pause
