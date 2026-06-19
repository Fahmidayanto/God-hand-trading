@echo off
echo ====================================
echo   ValueCell Trading Backend
echo ====================================
echo.

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo Starting FastAPI server...
echo API will be available at: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
