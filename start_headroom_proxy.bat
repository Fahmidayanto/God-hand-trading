@echo off
setlocal
title Headroom Optimization Proxy (:8787)

echo ===================================================
echo   Headroom Optimization Proxy (Port 8787)
echo ===================================================
echo.

cd /d "%~dp0"

set "HEADROOM=%~dp0..\.venv\Scripts\headroom.exe"

if not exist "%HEADROOM%" (
    where headroom >nul 2>&1
    if not errorlevel 1 (
        set "HEADROOM=headroom"
    ) else (
        echo [ERROR] headroom.exe not found at:
        echo         %HEADROOM%
        echo [INFO]  Please verify Python virtual environment in ..\.venv
        pause
        exit /b 1
    )
)

echo [INFO] Checking if port 8787 is already active...
powershell -Command "if (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] Headroom proxy is ALREADY running on http://127.0.0.1:8787
    echo [INFO] Endpoints:
    echo        - Health:  http://127.0.0.1:8787/health
    echo        - Stats:   http://127.0.0.1:8787/stats
    echo        - Metrics: http://127.0.0.1:8787/metrics
    echo.
    pause
    exit /b 0
)

echo [INFO] Starting Headroom Proxy at http://127.0.0.1:8787 ...
echo [INFO] Routing:
echo        - Claude Code / Anthropic: ANTHROPIC_BASE_URL=http://127.0.0.1:8787
echo        - OpenAI-compatible:      OPENAI_BASE_URL=http://127.0.0.1:8787/v1
echo.
echo [INFO] Press Ctrl+C to stop the proxy.
echo.

"%HEADROOM%" proxy

if errorlevel 1 (
    echo.
    echo [ERROR] Headroom proxy stopped unexpectedly.
    pause
)
exit /b %errorlevel%

