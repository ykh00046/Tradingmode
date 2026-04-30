@echo off
chcp 65001 > nul

REM ============================================================================
REM  trading-analysis-tool - stop running backend/frontend
REM ============================================================================

echo.
echo ============================================================================
echo  TRADINGMODE.LAB - stopping...
echo ============================================================================
echo.

REM 8000 번 포트 점유 PID 종료 (uvicorn)
echo [1/2] Backend (port 8000) 종료...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo     PID %%a 종료
  taskkill /F /PID %%a > nul 2>&1
)

REM 5500 번 포트 점유 PID 종료 (http.server)
echo [2/2] Frontend (port 5500) 종료...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5500" ^| findstr "LISTENING"') do (
  echo     PID %%a 종료
  taskkill /F /PID %%a > nul 2>&1
)

echo.
echo 종료 완료.
echo.
