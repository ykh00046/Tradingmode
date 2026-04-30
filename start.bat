@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

echo.
echo ============================================================
echo  TRADINGMODE.LAB - launcher
echo ============================================================
echo  Project root : %ROOT%
echo  Python venv  : %PY%
echo.

if not exist "%PY%" (
  echo [ERROR] Python venv not found.
  echo Run setup.bat first to create the virtual environment.
  echo.
  pause
  exit /b 1
)

if not exist "%ROOT%backend\main.py" (
  echo [ERROR] backend\main.py not found.
  pause
  exit /b 1
)

if not exist "%ROOT%Tradingmode\index.html" (
  echo [ERROR] Tradingmode\index.html not found.
  pause
  exit /b 1
)

if not exist "%ROOT%data" mkdir "%ROOT%data"

echo [1/2] Starting backend on http://127.0.0.1:8000 ...
start "" "%ROOT%_backend.cmd"

echo       Waiting for backend health check (max 25 seconds)...
set /a tries=0
:wait
timeout /t 1 /nobreak > nul
set /a tries+=1
"%PY%" -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1).status == 200 else 1)" 2> nul
if errorlevel 1 (
  if %tries% LSS 25 goto wait
  echo       [WARN] Backend not responding after 25s. Frontend will start anyway.
) else (
  echo       Backend OK after %tries% second^(s^).
)

echo.
echo [2/2] Starting frontend on http://localhost:5500 ...
start "" "%ROOT%_frontend.cmd"

timeout /t 2 /nobreak > nul
start "" "http://localhost:5500/"

echo.
echo ============================================================
echo  Running. Two cmd windows opened (Backend / Frontend).
echo ------------------------------------------------------------
echo  Frontend     : http://localhost:5500/
echo  Backend docs : http://localhost:8000/docs
echo  Demo mode    : http://localhost:5500/?demo=1
echo ------------------------------------------------------------
echo  To stop      : run stop.bat, or close the two cmd windows
echo ============================================================
echo.
pause
endlocal
