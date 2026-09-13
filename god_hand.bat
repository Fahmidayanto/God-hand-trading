@echo off
chcp 65001 >nul
title God Hand Trading - VS Code Tasks Launcher

echo ===================================================
echo   God Hand Trading - 4 Services (VS Code Terminal)
echo ===================================================
echo.
echo [INFO] Membuka / memfokuskan workspace di VS Code...
call code -r "%~dp0"
echo.
echo ===================================================
echo   CARA MENJALANKAN 4 TERMINAL DI DALAM VS CODE:
echo ===================================================
echo   1. Di jendela VS Code, cukup tekan shortcut keyboard:
echo      Ctrl + Shift + B
echo.
echo   ATAU
echo.
echo   2. Dari menu bar atas VS Code:
echo      Terminal -^> Run Task... -^> God Hand (Run All 4 Services)
echo.
echo   Keempat service akan otomatis terbuka di 4 tab terminal
echo   internal VS Code (panel bawah editor):
echo   - 1. Headroom Proxy (:8787)
echo   - 2. Codebase Memory MCP (:9749)
echo   - 3. Backend Server (:8000)
echo   - 4. Frontend Dashboard (:5173)
echo ===================================================
echo.
pause
