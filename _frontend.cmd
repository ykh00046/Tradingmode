@echo off
title Tradingmode Frontend (http.server :5500)
cd /d "%~dp0Tradingmode"
"%~dp0.venv\Scripts\python.exe" -m http.server 5500
echo.
echo ============================================================
echo  Frontend stopped. Press any key to close this window.
echo ============================================================
pause > nul
