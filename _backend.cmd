@echo off
title Tradingmode Backend (uvicorn :8000)
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
echo.
echo ============================================================
echo  Backend stopped. Press any key to close this window.
echo ============================================================
pause > nul
