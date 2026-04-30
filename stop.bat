@echo off
setlocal EnableExtensions

echo.
echo ============================================================
echo  TRADINGMODE.LAB - stopping
echo ============================================================
echo.

echo [1/2] Killing backend on port 8000 ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo       PID %%a
  taskkill /F /PID %%a > nul 2>&1
)

echo [2/2] Killing frontend on port 5500 ...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5500" ^| findstr "LISTENING"') do (
  echo       PID %%a
  taskkill /F /PID %%a > nul 2>&1
)

echo.
echo Done.
echo.
pause
endlocal
