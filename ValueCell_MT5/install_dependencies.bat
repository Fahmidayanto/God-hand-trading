@echo off
REM Helper script to install dependencies using venv
REM Usage: install_dependencies.bat

echo ========================================
echo Installing Dependencies (using venv)
echo ========================================
echo.

REM Check if venv exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created!
    echo.
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r python\requirements.txt

echo.
echo ========================================
echo Installation completed!
echo ========================================
echo.
echo Next steps:
echo 1. Update .env file with your credentials
echo 2. Run: run_test_mt5.bat
echo.
pause
