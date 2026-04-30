@echo off
chcp 65001 > nul
setlocal EnableExtensions

REM ============================================================================
REM  trading-analysis-tool - first-time setup
REM  - .venv 생성 + 의존성 설치 + .env 템플릿 복사
REM  - 두 번째 실행부터는 start.bat 만 사용
REM ============================================================================

set "ROOT=%~dp0"

echo.
echo ============================================================================
echo  TRADINGMODE.LAB - first-time setup
echo ============================================================================
echo.

REM --- Python 확인 ---
where python > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 이 PATH 에 없습니다. Python 3.11+ 설치 후 다시 실행하세요.
  echo         https://www.python.org/downloads/
  pause
  exit /b 1
)

REM --- venv 생성 ---
if exist "%ROOT%.venv" (
  echo [SKIP] .venv 이미 존재
) else (
  echo [1/3] 가상환경 생성...
  python -m venv "%ROOT%.venv"
  if errorlevel 1 (
    echo [ERROR] venv 생성 실패
    pause
    exit /b 1
  )
)

set "PY=%ROOT%.venv\Scripts\python.exe"

REM --- 의존성 설치 ---
echo [2/3] 의존성 설치 (5~10분 소요)...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%ROOT%backend\requirements.txt"
"%PY%" -m pip install pytest pytest-mock pytest-asyncio
if errorlevel 1 (
  echo [WARN] 일부 패키지 설치 실패 — 수동으로 확인 필요
)

REM --- .env 생성 ---
if not exist "%ROOT%.env" (
  echo [3/3] .env 템플릿 복사...
  copy "%ROOT%.env.example" "%ROOT%.env" > nul
  echo        .env 파일이 생성됐습니다. GROQ_API_KEY 를 입력하세요.
) else (
  echo [SKIP] .env 이미 존재
)

REM --- pytest 빠른 검증 ---
echo.
echo ============================================================================
echo  pytest 실행 (75 테스트, 약 1.5초)
echo ============================================================================
cd /d "%ROOT%backend"
"%PY%" -m pytest -q
cd /d "%ROOT%"

echo.
echo ============================================================================
echo  setup 완료. 이제 start.bat 으로 실행하세요.
echo ============================================================================
echo.
endlocal
pause
