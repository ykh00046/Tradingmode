@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"

echo.
echo ============================================================
echo  TRADINGMODE.LAB - first-time setup
echo ============================================================
echo.

where python > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  echo Install Python 3.11+ first: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

if exist "%ROOT%.venv" (
  echo [SKIP] .venv already exists at %ROOT%.venv
) else (
  echo [1/4] Creating virtual environment ...
  python -m venv "%ROOT%.venv"
  if errorlevel 1 (
    echo [ERROR] venv creation failed.
    pause
    exit /b 1
  )
)

set "PY=%ROOT%.venv\Scripts\python.exe"

echo.
echo [2/4] Installing Python dependencies (this can take 5-10 minutes) ...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%ROOT%backend\requirements.txt"
if errorlevel 1 (
  echo [WARN] Some packages failed to install. Check the log above.
)
"%PY%" -m pip install pytest pytest-mock pytest-asyncio

if not exist "%ROOT%.env" (
  echo.
  echo [3/4] Creating .env from template ...
  copy "%ROOT%.env.example" "%ROOT%.env" > nul
  echo       Edit .env to set GROQ_API_KEY for AI commentary.
) else (
  echo.
  echo [SKIP] .env already exists
)

echo.
echo [4/4] Installing frontend build dependencies (npm) ...
where npm > nul 2>&1
if errorlevel 1 (
  echo [WARN] npm not found in PATH. Install Node.js from https://nodejs.org/
  echo        The frontend dev server needs it; start.bat will retry later.
) else (
  cd /d "%ROOT%Tradingmode"
  call npm install
  cd /d "%ROOT%"
)

echo.
echo ============================================================
echo  Running pytest (75 tests) ...
echo ============================================================
cd /d "%ROOT%backend"
"%PY%" -m pytest -q
cd /d "%ROOT%"

echo.
echo ============================================================
echo  Setup done. Run start.bat to launch the app.
echo ============================================================
echo.
pause
endlocal
