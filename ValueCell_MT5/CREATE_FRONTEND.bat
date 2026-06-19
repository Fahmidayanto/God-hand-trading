@echo off
echo ====================================
echo   ValueCell Frontend Setup
echo ====================================
echo.

REM Check if Node.js is installed
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed!
    echo Please install Node.js from: https://nodejs.org/
    pause
    exit /b 1
)

echo Node.js version:
node --version
echo.

echo NPM version:
npm --version
echo.

REM Check if frontend directory exists
if exist frontend (
    echo [WARNING] Frontend directory already exists!
    echo Do you want to recreate it? (This will delete existing frontend)
    choice /C YN /M "Press Y to recreate, N to cancel"
    if errorlevel 2 goto :end
    echo Removing old frontend...
    rmdir /s /q frontend
)

echo.
echo Creating Vite + React project...
echo.

REM Create Vite project
call npm create vite@latest frontend -- --template react

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create Vite project!
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
cd frontend

REM Install base dependencies
call npm install

REM Install additional packages
echo.
echo Installing React Router, Zustand, Axios...
call npm install react-router-dom zustand axios

echo Installing chart libraries...
call npm install lightweight-charts chart.js react-chartjs-2

echo Installing utilities...
call npm install clsx

echo.
echo ====================================
echo   Frontend created successfully!
echo ====================================
echo.
echo Next steps:
echo 1. cd frontend
echo 2. npm run dev
echo.
echo Frontend will be available at: http://localhost:5173
echo.

pause
:end
