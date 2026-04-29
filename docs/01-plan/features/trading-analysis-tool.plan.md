---
template: plan
version: 1.2
feature: trading-analysis-tool
date: 2026-04-29
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.1.0
---

# trading-analysis-tool Planning Document

> **Summary**: 암호화폐 및 한국 주식(KOSPI/KOSDAQ) 데이터를 수집하여 기술적 지표를 계산하고, 매매 신호·추세 판별·백테스팅 결과를 Streamlit 웹 대시보드로 제공하는 분석 툴.
>
> **Project**: trading-analysis-tool
> **Version**: 0.1.0
> **Author**: 900033@interojo.com
> **Date**: 2026-04-29
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

개인 투자자가 차트를 일일이 눈으로 보지 않아도, 관심 종목의 추세(상승/하락/횡보)와 매매 신호(골든크로스, RSI 다이버전스 등)를 자동으로 판별하고, 과거 데이터로 전략의 유효성을 백테스팅해 의사결정을 지원하는 도구를 구축한다.

### 1.2 Background

- TradingView는 시각화는 우수하나 다종목 동시 스크리닝·자동 신호 추출·전략 백테스팅을 무료 플랜에서 충분히 지원하지 않는다.
- 공식 API를 통한 데이터 수집(Binance, pykrx, FinanceDataReader)은 합법적이며 안정적이고, TradingView와 동일한 OHLCV 원본을 받을 수 있다.
- Python 생태계의 `pandas-ta`, `backtesting.py`, `streamlit`, `plotly`로 빠르게 MVP 구축이 가능하다.

### 1.3 Related Documents

- 외부 참조: Binance API Docs, pykrx GitHub, pandas-ta Docs, backtesting.py Docs (Context7 활용)
- 후속 문서: `docs/02-design/features/trading-analysis-tool.design.md`

---

## 2. Scope

### 2.1 In Scope

- [ ] 암호화폐(Binance Spot) OHLCV 데이터 수집 (1m, 5m, 15m, 1h, 4h, 1d)
- [ ] 한국 주식(KOSPI/KOSDAQ) 일봉/분봉 데이터 수집 (pykrx + FinanceDataReader)
- [ ] 기술적 지표 계산: SMA/EMA, RSI, MACD, 볼린저밴드, ADX, Stochastic
- [ ] 추세 판별 로직: ADX + 이동평균 배열 기반 상승/하락/횡보 분류
- [ ] 매매 신호 탐지: 골든/데드크로스, RSI 과매수/과매도, RSI 다이버전스, MACD 교차
- [ ] 백테스팅 엔진: 신호 기반 진입/청산, 수익률·MDD·승률·샤프지수 산출
- [ ] Streamlit 웹 대시보드: 종목 선택, 캔들 차트(plotly), 지표 오버레이, 신호 표시, 백테스트 결과 표시
- [ ] 데이터 캐싱: 동일 요청 반복 호출 방지(SQLite 또는 parquet)

### 2.2 Out of Scope

- 실시간 자동 매매(주문 실행) — 분석/시뮬레이션 전용
- 옵션/선물/FX 등 파생상품 (1차 릴리스)
- 다중 사용자 인증/계정 시스템
- 모바일 네이티브 앱
- 머신러닝 기반 예측 모델 (1차 릴리스, 추후 확장 가능)
- 실시간 알림(Slack/Telegram) — v2 고려

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Binance Spot에서 지정 심볼·타임프레임 OHLCV 캔들 데이터 다운로드 | High | Pending |
| FR-02 | KOSPI/KOSDAQ 종목 코드로 일봉 OHLCV 다운로드 | High | Pending |
| FR-03 | 다운로드한 데이터를 로컬에 캐싱하고 재사용 | High | Pending |
| FR-04 | SMA/EMA(5,20,60,120), RSI(14), MACD(12,26,9), 볼린저밴드(20,2), ADX(14) 계산 | High | Pending |
| FR-05 | 추세 분류: ADX>25 + MA 정배열 → 상승 / 역배열 → 하락 / 그 외 → 횡보 | High | Pending |
| FR-06 | 골든크로스(MA20 ↑ MA60), 데드크로스 신호 감지 | High | Pending |
| FR-07 | RSI 과매수(>70)/과매도(<30) 영역 진입/이탈 신호 | High | Pending |
| FR-08 | RSI 강세/약세 다이버전스 감지 | Medium | Pending |
| FR-09 | MACD 시그널 라인 교차 신호 감지 | Medium | Pending |
| FR-10 | 백테스팅: 신호 기반 진입/청산, 누적수익률·MDD·승률·샤프지수 출력 | High | Pending |
| FR-11 | Streamlit 대시보드 메인 화면: 종목/타임프레임 선택, 캔들 차트 + 지표 오버레이 | High | Pending |
| FR-12 | 매매 신호 페이지: 신호 발생 시점 차트 표시 + 최근 신호 리스트 | High | Pending |
| FR-13 | 백테스팅 페이지: 전략 선택 → 결과 차트 + 통계 테이블 | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 단일 종목·1년치 일봉 분석 < 2초 | 로컬 캐시 hit 기준, `time.perf_counter` 측정 |
| Reliability | 데이터 수집 실패 시 명확한 에러 메시지 + 재시도 로직 | API 에러 핸들링 단위 테스트 |
| Usability | 비개발자도 종목 코드 입력만으로 사용 가능 | Streamlit selectbox + autocomplete 제공 |
| Compatibility | Windows 11 + Python 3.11+ 환경에서 동작 | 본 환경(C:\X\new) 기준 검증 |
| Legal | 공식 API 이용약관 준수, 무료 데이터만 사용 | Binance/pykrx 공식 API 외 미사용 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 High 우선순위 기능 요구사항(FR) 구현 완료
- [ ] BTC/USDT, 삼성전자(005930) 두 종목으로 end-to-end 시연 가능
- [ ] 추세 판별·매매 신호·백테스팅이 한 화면에서 확인 가능
- [ ] `pip install -r requirements.txt && streamlit run app.py` 한 줄로 실행
- [ ] README에 실행법·사용 예시 문서화

### 4.2 Quality Criteria

- [ ] 핵심 모듈(indicators, signals, trend, backtest) 단위 테스트 작성
- [ ] Gap Analysis 매치율 ≥ 90%
- [ ] 빌드/실행 시 에러 0건
- [ ] 신호 로직 검증: 알려진 골든크로스 사례(예: BTC 2020-04) 정확 감지

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Binance API 한국 IP 제한 가능성 | High | Medium | KR 주식 우선 동작 보장, 필요 시 Bybit 등 대체 거래소 어댑터 추가 |
| pykrx 분봉 데이터 부재(일봉만 안정) | Medium | High | KR 주식은 우선 일봉 기준으로 구현, 분봉은 v2로 미룸 |
| pandas-ta 일부 지표 NaN 처리 불일치 | Medium | Medium | 핵심 지표는 검증된 사례로 단위 테스트 + 수동 검증 |
| 매매 신호 거짓 양성(False Positive) 과다 | High | High | 백테스팅으로 정량 검증, 신호 강도 점수화로 필터링 |
| TA-Lib 컴파일 이슈(Windows) | Medium | High | TA-Lib 대신 순수 Python 구현인 `pandas-ta` 사용 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| **Starter** | Simple structure | Static sites, portfolios | ☐ |
| **Dynamic** | Feature-based modules, services layer | Web apps with backend, SaaS MVPs | ☑ |
| **Enterprise** | Strict layer separation, DI, microservices | High-traffic systems | ☐ |

**선정 사유**: 단일 사용자 분석 도구이며, 데이터 로더·지표·신호·백테스트 등 도메인 모듈 분리가 필요. 마이크로서비스/DI까지는 과도. → **Dynamic** 적합.

### 6.2 Key Architectural Decisions

본 프로젝트는 Python 기반 데이터 분석 툴이므로, 템플릿의 프론트엔드 항목 대신 다음 표를 사용:

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 언어/런타임 | Python 3.11 / 3.12 | **Python 3.11+** | pandas-ta·streamlit 안정 호환 |
| UI Framework | Streamlit / Gradio / Dash | **Streamlit** | 사용자 선택, 빠른 프로토타이핑 |
| 차트 라이브러리 | plotly / matplotlib / lightweight-charts | **plotly** | 인터랙티브 캔들·줌·툴팁 |
| 암호화폐 데이터 | python-binance / ccxt | **python-binance** | 단일 거래소 우선, ccxt는 v2에서 |
| KR 주식 데이터 | pykrx / FinanceDataReader | **둘 다** | pykrx(거래소 데이터 정확), FDR(보조·시계열 보강) |
| 지표 계산 | TA-Lib / pandas-ta / 직접 구현 | **pandas-ta** | Windows 설치 간편, 순수 Python |
| 백테스팅 | backtesting.py / vectorbt / bt | **backtesting.py** | 직관적 API, 학습곡선 낮음 |
| 데이터 저장 | SQLite / parquet / csv | **parquet (pyarrow)** | 컬럼 기반·고압축·pandas 친화 |
| 패키지 매니저 | pip / poetry / uv | **uv** | 빠른 설치, 단일 venv 관리 용이 |
| 테스트 | pytest / unittest | **pytest** | 사실상 표준 |

### 6.3 Clean Architecture Approach

```
Selected Level: Dynamic

폴더 구조 (Python 적용):
C:/X/new/
├── app.py                     # Streamlit 진입점
├── pages/                     # Streamlit 멀티페이지
│   ├── 1_차트분석.py
│   ├── 2_매매신호.py
│   └── 3_백테스팅.py
├── core/                      # 도메인 모듈 (services 역할)
│   ├── data_loader.py         # 거래소/주식 어댑터 통합
│   ├── adapters/
│   │   ├── binance_adapter.py
│   │   └── krx_adapter.py
│   ├── indicators.py          # 기술적 지표
│   ├── signals.py             # 매매 신호
│   ├── trend.py               # 추세 판별
│   └── backtest.py            # 백테스팅
├── lib/                       # 공용 유틸 (캐시, 로깅)
│   ├── cache.py
│   └── logger.py
├── types/                     # 타입 정의 (TypedDict, dataclass)
│   └── schemas.py
├── tests/
│   ├── test_indicators.py
│   ├── test_signals.py
│   └── test_backtest.py
├── data/                      # parquet 캐시 (gitignore)
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

- [ ] `CLAUDE.md` (프로젝트 루트) — 미존재, 작성 필요
- [ ] `docs/01-plan/conventions.md` — 미존재, Phase 2에서 작성
- [ ] `pyproject.toml` 내 black/ruff 설정 — 미존재, 추가 필요
- [ ] `.python-version` (pyenv/uv용) — 미존재

### 7.2 Conventions to Define/Verify

| Category | Current State | To Define | Priority |
|----------|---------------|-----------|:--------:|
| **Naming** | missing | snake_case (함수/변수), PascalCase (클래스), UPPER_CASE (상수) | High |
| **Folder structure** | missing | core/lib/types/pages 분리 (위 6.3 기준) | High |
| **Import order** | missing | stdlib → 3rd-party → local (isort 호환) | Medium |
| **Environment variables** | missing | `.env` + `python-dotenv` 사용 | Medium |
| **Error handling** | missing | 데이터 수집 실패 → 사용자 친화적 메시지 + 로그 | Medium |
| **Lint/Format** | missing | ruff(lint) + black(format) | Medium |
| **Type hints** | missing | 모든 public 함수 시그니처에 type hint | Medium |

### 7.3 Environment Variables Needed

| Variable | Purpose | Scope | To Be Created |
|----------|---------|-------|:-------------:|
| `BINANCE_API_KEY` | (선택) Rate limit 완화용 | Server | ☑ (옵션) |
| `BINANCE_API_SECRET` | (선택) 위와 동일 | Server | ☑ (옵션) |
| `CACHE_DIR` | parquet 캐시 경로 | Server | ☑ (기본 `./data`) |
| `LOG_LEVEL` | INFO/DEBUG/WARNING | Server | ☑ |

> Binance public market data는 인증 없이도 조회 가능하므로 API 키는 선택사항.

### 7.4 Pipeline Integration

| Phase | Status | Document Location | Command |
|-------|:------:|-------------------|---------|
| Phase 1 (Schema) | ☐ | `docs/01-plan/schema.md` | `/pipeline-next` |
| Phase 2 (Convention) | ☐ | `docs/01-plan/conventions.md` | `/pipeline-next` |

> Streamlit 단일 앱 구조이므로 Phase 3(목업)·Phase 5(디자인 시스템)은 간소화 가능. 추후 Design 단계에서 결정.

---

## 8. Next Steps

1. [ ] 사용자 검토 및 Plan 승인
2. [ ] Design 문서 작성 (`/pdca design trading-analysis-tool`)
   - 모듈별 함수 시그니처·데이터 플로우·신호 알고리즘 의사코드 명세
3. [ ] 구현 시작 (`/pdca do trading-analysis-tool`)
4. [ ] Gap Analysis (`/pdca analyze trading-analysis-tool`)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | 초안 작성 | 900033@interojo.com |
