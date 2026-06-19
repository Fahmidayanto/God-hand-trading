@echo off
echo ====================================
echo   ValueCell Full Stack Development
echo ====================================
echo.

REM Check if backend exists
if not exist "backend\app\main.py" (
    echo [ERROR] Backend not found!
    echo Please ensure backend directory exists.
    pause
    exit /b 1
)

REM Check if frontend exists
if not exist "frontend\package.json" (
    echo [WARNING] Frontend not found!
    echo Please run CREATE_FRONTEND.bat first.
    choice /C YN /M "Do you want to create frontend now?"
    if errorlevel 2 goto :start_backend_only
    call CREATE_FRONTEND.bat
)

echo.
echo Starting Backend and Frontend...
echo.

REM Start backend in new window
echo Starting Backend on port 8000...
start "ValueCell Backend" cmd /k "cd /d backend && start.bat"

timeout /t 3 /nobreak >nul

REM Start frontend in new window
echo Starting Frontend on port 5173...
start "ValueCell Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo ====================================
echo   Both servers are starting!
echo ====================================
echo.
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo.
echo Press any key to stop all servers...
pause >nul

REM Kill processes
taskkill /FI "WINDOWTITLE eq ValueCell Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ValueCell Frontend*" /T /F >nul 2>&1

echo.
echo Servers stopped.
pause
exit /b 0

:start_backend_only
echo.
echo Starting Backend only...
start "ValueCell Backend" cmd /k "cd /d backend && start.bat"
echo.
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
pause
exit /b 0
