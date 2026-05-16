@echo off
title Tradingmode Frontend (esbuild dev :5173)
cd /d "%~dp0Tradingmode"
if not exist node_modules (echo [setup] installing frontend dependencies, first run only... & call npm install)
call npm run dev
echo.
echo ============================================================
echo  Frontend stopped. Press any key to close this window.
echo ============================================================
pause > nul
