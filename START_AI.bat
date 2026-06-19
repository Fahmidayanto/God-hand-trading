@echo off
color 0A
title SMC AI Trading Intelligence System Launcher
echo ========================================================
echo   MENGHIDUPKAN AI TRADING ENGINE XAUUSD
echo ========================================================
echo.
echo [1] Memulai Service Daemon (Manajer Pipeline AI)...
start "AI Main Pipeline (DO NOT CLOSE)" cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe AI_Trading_Server\main_pipeline_run.py"

echo [2] Memulai FastAPI Server (Penghubung ke Telegram)...
start "AI Telegram API (DO NOT CLOSE)" cmd /k "cd /d "%~dp0" && set PYTHONPATH=.&& .venv\Scripts\python.exe -m uvicorn AI_Trading_Server.api.server:app --host 0.0.0.0 --port 8080"

echo.
echo ========================================================
echo   ✅ SEMUA SISTEM TELAH DILUNCURKAN!
echo   Akan muncul 2 jendela hitam baru. Biarkan tetap terbuka.
echo   Anda boleh menutup layar yang ini.
echo ========================================================
timeout /t 5 > nul
