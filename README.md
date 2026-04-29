# Tradingmode

암호화폐 및 한국 주식(KOSPI/KOSDAQ) 데이터를 수집하여 기술적 지표·매매 신호·추세를 분석하고 백테스팅까지 수행하는 Streamlit 기반 분석 툴.

## 상태

🚧 **개발 중** — PDCA Design 단계 완료, 구현 예정

## 기능 (계획)

- 📥 **데이터 수집**: Binance Spot (암호화폐) + pykrx / FinanceDataReader (한국 주식)
- 📊 **기술적 지표**: SMA/EMA, RSI, MACD, 볼린저밴드, ADX, Stochastic
- 🎯 **매매 신호**: 골든/데드 크로스, RSI 과매수/과매도, RSI 다이버전스, MACD 교차
- 📈 **추세 판별**: ADX + 이동평균 배열로 상승/하락/횡보 자동 분류
- 🤖 **AI 신호 해석**: Groq LLM(`llama-3.3-70b-versatile`)으로 감지된 신호의 자연어 해설 자동 생성
- 💼 **포트폴리오 분석**: 보유 종목(CSV/수동) 일괄 추세·신호·평가금액·손익·비중 집계
- 🔬 **백테스팅**: 신호 기반 진입/청산, 수익률·MDD·승률·샤프지수 산출
- 🖥️ **Streamlit 대시보드**: 캔들 차트(plotly) + 지표 오버레이 + 신호 시각화 + 포트폴리오 페이지
- 🔌 **자동매매 확장 지점**: broker 어댑터 인터페이스 정의 (실제 구현은 v3)

## 시중 도구 대비 차별점

- 🇰🇷 **암호화폐 + 한국 주식 통합** — 단일 자산군 도구 다수, 통합 분석은 적음
- 🤖 **AI 자연어 해설** — 단순 신호 출력이 아닌 "왜 이 신호가 발생했고 무엇을 봐야 하는지" 한국어 설명
- 💼 **포트폴리오 단위 한눈에 보기** — 보유 종목의 추세·신호·손익을 한 화면 집계

## 아키텍처

- **Frontend** (`Tradingmode/`) — React 18 SPA (CDN 기반, 빌드 도구 없음)
- **Backend** (`backend/`) — FastAPI + Python 도메인 모듈
- **통신** — REST/JSON, CORS

## 기술 스택

**Backend (Python 3.11+)**
- FastAPI, uvicorn, Pydantic
- pandas, pandas-ta
- python-binance, pykrx, FinanceDataReader
- backtesting.py
- groq (Groq API 클라이언트, 백엔드만 보유)
- pyarrow (parquet 캐시)

**Frontend (브라우저)**
- React 18 (UMD via unpkg)
- @babel/standalone (런타임 JSX 컴파일)
- 직접 SVG 차트 (v2에서 lightweight-charts 검토)

## 문서

본 프로젝트는 PDCA 방법론으로 진행됩니다. 상세 명세는 `docs/`를 참고하세요.

| 단계 | 문서 |
|------|------|
| Plan | [docs/01-plan/features/trading-analysis-tool.plan.md](docs/01-plan/features/trading-analysis-tool.plan.md) |
| Design | [docs/02-design/features/trading-analysis-tool.design.md](docs/02-design/features/trading-analysis-tool.design.md) |

## 실행 (구현 후)

**Backend**
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env  # GROQ_API_KEY 입력 (https://console.groq.com 무료 발급)
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
# Tradingmode/ 를 정적 서버로 호스팅 (예: VS Code Live Server, Python http.server 등)
cd Tradingmode
python -m http.server 5500
# 브라우저에서 http://localhost:5500 접속
```

> Groq API 키 미설정 시 AI 해설 기능만 비활성화되고 나머지는 정상 동작합니다.
> 백엔드 OpenAPI 문서: http://localhost:8000/docs

## License

TBD
