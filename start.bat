@echo off
chcp 65001 > nul
setlocal EnableExtensions

REM ============================================================================
REM  trading-analysis-tool - one-click launcher
REM  - 백엔드 (FastAPI/uvicorn) 와 프론트 (http.server) 를 별도 창으로 기동
REM  - 5초 후 기본 브라우저로 http://localhost:5500/ 자동 오픈
REM  - 종료: 각 cmd 창에서 Ctrl+C, 또는 stop.bat 실행
REM ============================================================================

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

echo.
echo ============================================================================
echo  TRADINGMODE.LAB - launching...
echo ============================================================================
echo.

REM --- 가상환경 확인 ---
if not exist "%PY%" (
  echo [ERROR] 가상환경이 없습니다: %PY%
  echo.
  echo 처음 실행이라면 다음을 먼저 수행하세요:
  echo   1^) python -m venv .venv
  echo   2^) .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  echo   3^) .venv\Scripts\python.exe -m pip install pytest pytest-mock pytest-asyncio
  echo.
  pause
  exit /b 1
)

REM --- .env 확인 ---
if not exist "%ROOT%.env" (
  echo [WARN] .env 파일이 없습니다. .env.example 을 복사해 .env 로 만들고 GROQ_API_KEY 등을 입력하세요.
  echo        AI 해설 기능 외 다른 기능은 .env 없이도 동작합니다.
  echo.
)

REM --- 캐시 디렉토리 ---
if not exist "%ROOT%data" mkdir "%ROOT%data"

REM --- Backend (FastAPI) ---
echo [1/2] Backend 기동 (uvicorn :8000)...
start "Tradingmode Backend" cmd /k "cd /d "%ROOT%backend" && "%PY%" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

REM --- Backend 헬스체크 대기 (최대 15초) ---
echo       기동 대기 중...
set /a tries=0
:waitbackend
timeout /t 1 /nobreak > nul
set /a tries+=1
"%PY%" -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1).status==200 else 1)" 2>nul
if errorlevel 1 (
  if %tries% LSS 15 goto waitbackend
  echo       [WARN] Backend health check 미응답 (15초 초과). 그대로 Frontend 기동.
) else (
  echo       Backend OK ^(http://127.0.0.1:8000/api/health^)
)

REM --- Frontend (정적 호스팅) ---
echo [2/2] Frontend 기동 (http.server :5500)...
start "Tradingmode Frontend" cmd /k "cd /d "%ROOT%Tradingmode" && "%PY%" -m http.server 5500"

REM --- 브라우저 자동 오픈 ---
timeout /t 2 /nobreak > nul
start "" "http://localhost:5500/"

echo.
echo ============================================================================
echo  실행 완료
echo ============================================================================
echo  Frontend     : http://localhost:5500/
echo  Backend docs : http://localhost:8000/docs
echo  Demo mode    : http://localhost:5500/?demo=1   (백엔드 없이 합성 데이터)
echo.
echo  종료하려면 각 창에서 Ctrl+C, 또는 stop.bat 실행
echo ============================================================================
echo.
endlocal
