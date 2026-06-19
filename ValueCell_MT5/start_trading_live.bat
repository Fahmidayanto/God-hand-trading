@echo off
REM Start Trading System in LIVE TRADING MODE
REM Location: d:\Project\Project MT5\ValueCell_MT5\start_trading_live.bat

echo ========================================
echo Multi-Agent Trading System
echo ========================================
echo.
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo !!! WARNING: LIVE TRADING MODE     !!!
echo !!! REAL MONEY WILL BE AT RISK     !!!
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
echo Mode: LIVE TRADING
echo Symbol: XAUUSD
echo Timeframe: M15
echo Check Interval: 5 seconds
echo.
echo You will be asked to confirm before starting
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start trading system (will ask for confirmation)
python -m valuecell.trading_system --mode live --symbol XAUUSD --timeframe M15 --interval 5

pause
