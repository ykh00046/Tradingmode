@echo off
title Tradingmode Production Build
setlocal EnableExtensions
set "ROOT=%~dp0"

echo.
echo ============================================================
echo  TRADINGMODE.LAB - production build
echo ============================================================
echo.

where npm > nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not found in PATH. Install Node.js from https://nodejs.org/
  pause
  exit /b 1
)

cd /d "%ROOT%Tradingmode"
if not exist node_modules (
  echo [setup] Installing frontend dependencies ...
  call npm install
)

echo [build] Compiling frontend with esbuild ...
call npm run build
cd /d "%ROOT%"

echo.
echo ============================================================
echo  Build output : %ROOT%Tradingmode\build\
echo  Deploy that folder to any static web host.
echo ============================================================
echo.
pause
endlocal
