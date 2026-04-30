---
template: design
version: 1.2
feature: trading-analysis-tool
date: 2026-04-29
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.1.0
---

# trading-analysis-tool Design Document

> **Summary**: Python 기반 시계열 데이터 수집·기술적 지표 계산·매매 신호 탐지·추세 판별·백테스팅을 수행하고 Streamlit 대시보드로 시각화하는 분석 툴의 모듈 설계.
>
> **Project**: trading-analysis-tool
> **Version**: 0.1.0
> **Author**: 900033@interojo.com
> **Date**: 2026-04-29
> **Status**: Draft
> **Planning Doc**: [trading-analysis-tool.plan.md](../../01-plan/features/trading-analysis-tool.plan.md)

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | Schema Definition | N/A (pyproject 내 Pydantic/dataclass로 대체) |
| Phase 2 | Coding Conventions | 본 문서 §10에 인라인 정의 |
| Phase 3 | Mockup | N/A (Streamlit 기본 컴포넌트 사용) |
| Phase 4 | API Spec | 본 문서 §4에 모듈 API로 정의 |
| Phase 5 | Design System | N/A (Streamlit 기본 테마, 별도 디자인 미적용) |

> **Note**: 단일 사용자 데스크톱 분석 툴이므로 Pipeline 일부 단계는 생략. UI는 Streamlit 기본 테마 사용(브랜드 디자인 적용 안 함).

---

## 1. Overview

### 1.1 Design Goals

- **모듈성**: 데이터 소스(거래소/주식)와 broker(주문)를 어댑터 패턴으로 추상화 → 신규 소스/거래소 추가가 코어 변경 없이 가능
- **프론트/백엔드 분리**: React SPA(`Tradingmode/`) ↔ FastAPI(`backend/`)를 REST로 통신, 도메인 로직은 백엔드에 집중
- **재현성**: 동일 입력에 대해 동일 신호·백테스트 결과가 나오도록 결정론적 로직 작성 (LLM 호출 제외, LLM은 별도 캐시)
- **성능**: parquet 캐시로 동일 요청 재호출 방지, 단일 종목·1년치 분석 < 2초 (캐시 hit 기준), 프론트 첫 페인트 < 1초
- **검증가능성**: 모든 결정론적 로직(지표·신호·추세·포트폴리오 집계)은 단위 테스트 가능, OpenAPI 스키마로 프론트↔백엔드 계약 검증
- **확장성**: 백테스팅 전략, AI 프로바이더, broker를 모두 인터페이스/Protocol로 정의해 교체 가능
- **AI 보조성**: AI는 *보조 해설*만, 최종 매매 판단은 사용자 — 환각 방지를 위해 지표 수치 명시 + low temperature
- **포트폴리오 일괄성**: 단일 종목 분석을 그대로 N개로 확장하여 보유 자산 전체를 한 화면에서 파악
- **보안 우선**: API 키(Groq, Binance)는 백엔드만 보유, 프론트 코드/번들에 절대 노출 X

### 1.2 Design Principles

- **단일 책임 원칙(SRP)**: 데이터 수집/지표/신호/추세/백테스트/UI를 모듈 단위로 완전 분리
- **순수 함수 우선**: 지표·신호·추세 함수는 입력 DataFrame에 의존, 외부 상태 미보유
- **계산 ≠ 표시**: core 모듈은 시각화에 무관, Streamlit 페이지가 plotly로 별도 렌더
- **Fail Loud**: 데이터 수집 실패 시 명시적 예외 + 사용자 메시지, 묵음 실패 금지
- **타입 힌트 필수**: 모든 public 함수 시그니처에 type hint (mypy/ruff 호환)

---

## 2. Architecture

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│              Frontend (Tradingmode/, React 18 SPA)               │
│  index.html → app.jsx (TopBar + Watchlist + Router)              │
│  ├─ charts.jsx (ChartPage)                                       │
│  ├─ signals-page.jsx (SignalsPage + AI 해설)                     │
│  ├─ portfolio-page.jsx (PortfolioPage)                           │
│  └─ api.js (fetch 래퍼 — 모든 백엔드 호출 단일 진입점)            │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP/JSON (REST + CORS)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│           Backend API (backend/, FastAPI + uvicorn)              │
│  main.py (FastAPI app + CORSMiddleware)                          │
│  api/ohlcv.py · indicators.py · signals.py · trend.py            │
│  api/portfolio.py · backtest.py · ai.py · market.py              │
│  Pydantic 모델 ↔ core.types.schemas (자동 변환)                   │
└──┬───────────────┬─────────────────────────────────┬─────────────┘
   │ uses          │ uses                            │ uses
   ▼               ▼                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│              Backend Application (backend/core/)                 │
│  data_loader.py  backtest.py  portfolio.py  ai_interpreter.py    │
└──┬───────────────┬─────────────────────────────────┬─────────────┘
   │               │                                 │
   ▼               ▼                                 ▼
┌──────────────┐  ┌─────────────────────────┐  ┌───────────────────┐
│ Domain       │  │ Infrastructure          │  │ External APIs     │
│ indicators   │  │ adapters/binance, krx   │  │ Binance / pykrx   │
│ signals      │  │ brokers/base (v3 IF)    │  │ Groq LLM API      │
│ trend        │  │ lib/cache, logger       │  │ FX (FDR)          │
│ types/schemas│  │                         │  │                   │
│ types/errors │  │                         │  │                   │
└──────────────┘  └─────────────────────────┘  └───────────────────┘
```

**범례**:
- 프론트는 도메인 로직 0%, **백엔드 호출과 시각화·인터랙션만** 담당.
- `api/*.py`는 thin controller — 입력 검증 → core 호출 → Pydantic 응답 변환.
- `core.ai_interpreter`는 백엔드만 소유(Groq 키 보호).
- `Tradingmode/data.js`의 합성 데이터 함수는 v0.4에서 `api.js` 호출로 점진 교체.

### 2.2 Data Flow

```
[사용자 입력: 심볼 + 타임프레임 + 기간]
            │
            ▼
[data_loader.fetch(symbol, interval, start, end)]
            │
            ├─→ cache hit? ─→ parquet 로드 → return DataFrame
            │
            └─→ cache miss
                    │
                    ▼
                [adapter.download()]
                    │
                    ▼
                [validate & normalize → OHLCV DataFrame]
                    │
                    ▼
                [cache.save(parquet)]
                    │
                    ▼
                return DataFrame

DataFrame (OHLCV)
    │
    ├─→ [indicators.compute(df, config)] → DataFrame + 지표 컬럼
    │            │
    │            ├─→ [trend.classify(df)] → TrendState
    │            │
    │            ├─→ [signals.detect(df)] → List[Signal]
    │            │
    │            └─→ [backtest.run(df, strategy)] → BacktestResult
    │
    ▼
[Streamlit 페이지 → plotly 차트 + 표]
```

### 2.3 Dependencies

**Frontend (`Tradingmode/`)**

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `index.html` | React 18 UMD, Babel standalone (CDN) | 진입 |
| `app.jsx` | api.js, charts.jsx, signals-page.jsx, portfolio-page.jsx | TopBar + Watchlist + 라우팅 |
| `charts.jsx` | api.js | OHLCV/지표 fetch + 캔들 렌더 + 드로잉 |
| `signals-page.jsx` | api.js | 신호 fetch + AI 해설 fetch (POST `/api/ai/explain`) |
| `portfolio-page.jsx` | api.js | 포트폴리오 fetch + treemap |
| `api.js` (NEW) | fetch (browser native) | `API_BASE_URL` 기반 fetch 래퍼, 에러 정규화, 캐시 |
| `data.js` | (전환 예정) | v0.4: 합성 데이터 → api.js 호출로 점진 교체 |

**Backend (`backend/`)**

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `main.py` | fastapi, uvicorn, CORSMiddleware | 서버 진입 + 미들웨어 |
| `api/ohlcv.py` | core.data_loader | GET /api/ohlcv |
| `api/indicators.py` | core.indicators | GET /api/indicators |
| `api/signals.py` | core.signals | GET /api/signals |
| `api/trend.py` | core.trend | GET /api/trend |
| `api/portfolio.py` | core.portfolio | POST /api/portfolio |
| `api/backtest.py` | core.backtest | POST /api/backtest |
| `api/ai.py` | core.ai_interpreter | POST /api/ai/explain |
| `api/market.py` | core.data_loader | GET /api/market/snapshot (TopBar 시세 테이프) |
| `core.data_loader` | core.adapters.*, lib.cache | 데이터 통합 진입점 |
| `core.indicators` | pandas-ta, pandas | 지표 계산 |
| `core.signals` | core.indicators | 신호 |
| `core.trend` | core.indicators | 추세 |
| `core.backtest` | backtesting.py, core.signals | 백테스트 |
| `core.adapters.binance_adapter` | python-binance | Binance Spot API |
| `core.adapters.krx_adapter` | pykrx, FinanceDataReader | KR 주식 데이터 |
| `core.ai_interpreter` | groq, core.types | LLM 신호 해석 (백엔드만) |
| `core.portfolio` | core.data_loader, core.signals, core.trend, core.indicators | 보유 종목 일괄 분석 |
| `core.brokers.base` | core.types (인터페이스만) | v3 자동매매 확장 지점 (구현 X) |
| `lib.cache` | pyarrow, pathlib | parquet 캐시 |

---

## 3. Data Model

### 3.1 Entity Definition (Python)

```python
# core/types/schemas.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, TypedDict
import pandas as pd


class Market(str, Enum):
    CRYPTO = "crypto"
    KR_STOCK = "kr_stock"


class Interval(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# OHLCV DataFrame Schema (pandas DataFrame columns)
# index:  pd.DatetimeIndex (UTC for crypto, KST for KR stock)
# columns:
#   open:   float64
#   high:   float64
#   low:    float64
#   close:  float64
#   volume: float64


@dataclass(frozen=True)
class FetchRequest:
    market: Market
    symbol: str           # "BTCUSDT" or "005930"
    interval: Interval
    start: datetime
    end: datetime


class TrendState(str, Enum):
    UPTREND = "uptrend"           # ADX>25 + MA 정배열
    DOWNTREND = "downtrend"       # ADX>25 + MA 역배열
    SIDEWAYS = "sideways"         # ADX≤25 또는 MA 혼재


class SignalKind(str, Enum):
    """매매 신호 종류 (TrendState와 동일한 Enum 패턴 통일)"""
    GOLDEN_CROSS = "golden_cross"        # MA20 ↑ MA60
    DEATH_CROSS = "death_cross"          # MA20 ↓ MA60
    RSI_OVERBOUGHT = "rsi_overbought"    # RSI 70 상향 진입
    RSI_OVERSOLD = "rsi_oversold"        # RSI 30 하향 진입
    RSI_BULL_DIV = "rsi_bull_div"        # 가격 신저점 + RSI 신저점 미경신
    RSI_BEAR_DIV = "rsi_bear_div"        # 가격 신고점 + RSI 신고점 미경신
    MACD_BULL_CROSS = "macd_bull_cross"  # MACD ↑ Signal
    MACD_BEAR_CROSS = "macd_bear_cross"  # MACD ↓ Signal


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class Signal:
    timestamp: pd.Timestamp
    kind: SignalKind
    action: SignalAction
    price: float          # close at signal time
    strength: float       # 0.0 ~ 1.0 (v0.2는 항상 1.0 고정, 정밀화는 v2 — §4.3 참조)
    detail: dict          # ex: {"ma_short": 65000, "ma_long": 64000}


@dataclass(frozen=True)
class BacktestResult:
    total_return: float           # 누적 수익률 (%)
    annual_return: float          # 연환산 수익률 (%)
    max_drawdown: float           # MDD (%)
    win_rate: float               # 승률 (%)
    sharpe_ratio: float           # 샤프 지수
    num_trades: int               # 총 거래 수
    equity_curve: pd.Series       # 시점별 자산 곡선
    trades: pd.DataFrame          # 개별 거래 로그


# === AI 신호 해석 ===

@dataclass(frozen=True)
class AICommentary:
    """Groq LLM이 생성한 신호 해설"""
    signal_kind: SignalKind
    timestamp: pd.Timestamp
    summary: str           # "골든크로스 발생, 단기 상승 모멘텀 신호"
    detail: str            # 지표 수치 기반 상세 설명 (한국어, 2~4문장)
    confidence: Literal["low", "medium", "high"]   # 강도 레이블 (LLM 생성)
    model: str             # "llama-3.3-70b-versatile"
    generated_at: pd.Timestamp
    disclaimer: str = "본 해설은 참고용이며 투자 자문이 아닙니다."


# === 포트폴리오 ===

@dataclass(frozen=True)
class Holding:
    """보유 종목 1건. currency는 명시 강제(crypto는 USDT, KR 주식은 KRW)"""
    market: Market
    symbol: str
    quantity: float           # 보유 수량
    avg_price: float          # 평균 매입 단가 (currency 통화)
    currency: Literal["KRW", "USD", "USDT"]


@dataclass(frozen=True)
class FxQuote:
    """환율 인용 — 포트폴리오 평가 재현성/감사용"""
    pair: str                 # "USDT/KRW", "USD/KRW"
    rate: float
    as_of: pd.Timestamp
    source: str = "FinanceDataReader"


@dataclass(frozen=True)
class Portfolio:
    holdings: list[Holding]
    base_currency: Literal["KRW", "USD"] = "KRW"   # 평가 기준 통화


@dataclass(frozen=True)
class HoldingAnalysis:
    """보유 1건의 분석 결과 (모든 금액 필드는 base_currency 기준으로 변환됨)"""
    holding: Holding
    current_price_local: float      # 현지(원본) 통화 기준 현재가
    current_price: float            # base_currency 환산 현재가
    market_value: float             # quantity × current_price (base_currency)
    cost_basis: float               # quantity × avg_price × fx_rate (base_currency)
    pnl: float                      # market_value - cost_basis
    pnl_pct: float                  # pnl / cost_basis × 100
    weight: float                   # 0.0 ~ 1.0 (포트폴리오 내 비중)
    fx_rate: float                  # 적용된 환율 (currency → base_currency)
    trend: TrendState
    latest_signals: list[Signal]    # 최근 N개 신호


@dataclass(frozen=True)
class PortfolioAnalysis:
    """포트폴리오 전체 집계"""
    portfolio: Portfolio
    holdings_analysis: list[HoldingAnalysis]
    total_market_value: float
    total_cost_basis: float
    total_pnl: float
    total_pnl_pct: float
    trend_summary: dict[TrendState, int]    # {UPTREND: 3, DOWNTREND: 1, SIDEWAYS: 2}
    base_currency: Literal["KRW", "USD"]
    fx_rates: dict[str, FxQuote]            # {"USDT/KRW": FxQuote(...), "USD/KRW": ...}
    as_of: pd.Timestamp                     # 평가 기준 시점


# Note: Strategy / BrokerProtocol Protocol 정의는 §4.2 시그니처 섹션 참조.
#       구현 시 같은 파일(core/types/schemas.py)에 배치 — 타입은 한 파일에 모음.

# === 자동매매 (v3 - 인터페이스만) ===

@dataclass(frozen=True)
class OrderRequest:
    market: Market
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit"]
    limit_price: float | None = None


@dataclass(frozen=True)
class OrderResult:
    """주문 결과 (v3 구현 시 사용)"""
    order_id: str
    status: Literal["pending", "filled", "rejected", "cancelled"]
    filled_quantity: float
    filled_price: float | None
    timestamp: pd.Timestamp
```

### 3.2 Entity Relationships

```
FetchRequest ─── (1) ──→ OHLCV DataFrame
OHLCV DataFrame ─── (1:N) ──→ Indicator columns (RSI, MACD, ...)
OHLCV+Indicators ─── (1) ──→ TrendState
OHLCV+Indicators ─── (1:N) ──→ Signal
OHLCV+Signals + Strategy ─── (1) ──→ BacktestResult
```

### 3.3 Storage Schema (parquet 캐시)

캐시 파일 경로 규칙:
```
data/
└── {market}/
    └── {symbol}/
        └── {interval}/
            └── {start_date}_{end_date}.parquet

예시:
data/crypto/BTCUSDT/1d/2024-01-01_2026-04-29.parquet
data/kr_stock/005930/1d/2024-01-01_2026-04-29.parquet
```

DataFrame 스키마는 §3.1 OHLCV와 동일.

---

## 4. API Specification

> 본 섹션은 두 종류의 API를 다룬다:
> - **§4.1~4.3**: 백엔드 내부 모듈 API (Python 함수 시그니처)
> - **§4.5**: REST API (FastAPI 엔드포인트, 프론트↔백엔드 계약)

## 4. API Specification (내부 모듈 API)

### 4.1 모듈 함수 목록

| Module | Function | 설명 |
|--------|----------|------|
| `core.data_loader` | `fetch(req: FetchRequest) -> pd.DataFrame` | OHLCV 데이터 통합 진입점 |
| `core.indicators` | `compute(df, config) -> pd.DataFrame` | 모든 지표 일괄 계산 |
| `core.indicators` | `add_sma(df, periods)` | SMA 컬럼 추가 |
| `core.indicators` | `add_ema(df, periods)` | EMA 컬럼 추가 (MACD 내부용) |
| `core.indicators` | `add_rsi(df, period=14)` | RSI 컬럼 추가 |
| `core.indicators` | `add_macd(df, fast=12, slow=26, signal=9)` | MACD 컬럼 추가 |
| `core.indicators` | `add_bbands(df, length=20, std=2.0)` | 볼린저밴드 추가 |
| `core.indicators` | `add_adx(df, length=14)` | ADX 컬럼 추가 |
| `core.signals` | `detect_all(df) -> list[Signal]` | 모든 신호 종합 감지 |
| `core.signals` | `detect_ma_cross(df, short=20, long=60)` | MA 교차 신호 |
| `core.signals` | `detect_rsi_signals(df)` | RSI 과매수/과매도 |
| `core.signals` | `detect_rsi_divergence(df, lookback=20)` | RSI 다이버전스 |
| `core.signals` | `detect_macd_cross(df)` | MACD 교차 신호 |
| `core.trend` | `classify(df, adx_threshold=25) -> TrendState` | 현재 시점 추세 분류 |
| `core.trend` | `classify_series(df) -> pd.Series` | 시계열 전체 추세 분류 |
| `core.backtest` | `run(df, strategy, cash=10_000_000) -> BacktestResult` | 백테스팅 실행 |
| `core.ai_interpreter` | `interpret_signal(signal, df_window, model=...) -> AICommentary` | 단일 신호 해설 생성 |
| `core.ai_interpreter` | `interpret_signals_batch(signals, df) -> list[AICommentary]` | 다수 신호 일괄 해설 (캐시 활용) |
| `core.portfolio` | `load_holdings_from_csv(path) -> Portfolio` | CSV → Portfolio |
| `core.portfolio` | `analyze(portfolio, as_of=None) -> PortfolioAnalysis` | 포트폴리오 일괄 분석 |
| `core.portfolio` | `aggregate_trend(holdings_analysis) -> dict[TrendState, int]` | 추세 분포 집계 |
| `core.brokers.base` | `class BrokerProtocol(Protocol): place_order(req) -> OrderResult` | v3 인터페이스 정의 (구현 X) |
| `core.market_snapshot` | `fetch_snapshot() -> MarketSnapshot` | KOSPI/KOSDAQ/USD-KRW/BTC/DXY/VIX 일괄 조회 (TopBar용). DXY/VIX는 `FinanceDataReader('DXY')`/`('VIX')` 사용 |

### 4.2 핵심 함수 시그니처 상세

#### `core.data_loader.fetch`

```python
def fetch(req: FetchRequest) -> pd.DataFrame:
    """
    OHLCV 데이터를 가져온다. 캐시 우선 조회 후 미스 시 어댑터 호출.

    Args:
        req: 수집 요청 (market, symbol, interval, start, end)

    Returns:
        OHLCV DataFrame (DatetimeIndex, columns=[open,high,low,close,volume])

    Raises:
        DataSourceError: API 호출 실패
        InvalidSymbolError: 심볼 미존재
    """
```

#### `core.indicators.compute`

```python
class IndicatorConfig(TypedDict, total=False):
    sma_periods: list[int]        # default [5, 20, 60, 120] (차트 오버레이)
    rsi_period: int               # default 14
    macd: tuple[int, int, int]    # default (12, 26, 9)  ← 내부 EMA 12/26 사용
    bbands: tuple[int, float]     # default (20, 2.0)
    adx_length: int               # default 14
    # Note: 별도 EMA(5,20,60,120) 차트는 v2 — v0.2는 SMA 오버레이만


def compute(df: pd.DataFrame, config: IndicatorConfig | None = None) -> pd.DataFrame:
    """
    OHLCV DataFrame에 모든 지표 컬럼을 추가하여 반환.

    Returns DataFrame with additional columns:
        SMA_5, SMA_20, SMA_60, SMA_120
        RSI_14
        MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9   (내부적으로 EMA 12/26 사용)
        BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        ADX_14, DMP_14, DMN_14
    """
```

#### `core.signals.detect_all`

```python
def detect_all(df: pd.DataFrame) -> list[Signal]:
    """
    지표가 추가된 DataFrame에서 모든 신호를 시간순으로 감지.
    내부적으로 detect_ma_cross, detect_rsi_signals, detect_rsi_divergence,
    detect_macd_cross를 호출하고 timestamp 기준 정렬하여 반환.
    """
```

#### `core.trend.classify`

```python
def classify(df: pd.DataFrame, adx_threshold: float = 25.0) -> TrendState:
    """
    가장 최근 시점의 추세를 분류한다.

    Logic:
        adx = df["ADX_14"].iloc[-1]
        sma20, sma60, sma120 = df[["SMA_20","SMA_60","SMA_120"]].iloc[-1]

        if adx <= adx_threshold:
            return SIDEWAYS
        if sma20 > sma60 > sma120:
            return UPTREND
        if sma20 < sma60 < sma120:
            return DOWNTREND
        return SIDEWAYS
    """
```

#### `core.backtest.run`

```python
from typing import Protocol

class Strategy(Protocol):
    """backtesting.py의 Strategy를 래핑하는 인터페이스"""
    def init(self) -> None: ...
    def next(self) -> None: ...


def run(
    df: pd.DataFrame,
    strategy: type[Strategy],
    cash: float = 10_000_000,
    commission: float = 0.0005,  # 0.05%
) -> BacktestResult:
    """
    backtesting.py 라이브러리로 전략 백테스트 후 표준화된 BacktestResult 반환.
    """
```

#### `core.ai_interpreter.interpret_signal`

```python
# Groq SDK: from groq import Groq
# 모델: llama-3.3-70b-versatile (free tier)
# Context7 reference: /groq/groq-python

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def interpret_signal(
    signal: Signal,
    df_window: pd.DataFrame,    # 신호 시점 전후 30봉
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
) -> AICommentary:
    """
    단일 신호의 자연어 해설을 Groq LLM으로 생성.

    Prompt 구조:
        - System: 너는 기술적 분석 어시스턴트다. 사용자가 제공한 신호와
                 지표 수치를 토대로 *간결한* 해설을 작성한다. 추측·예측 금지.
                 항상 한국어로 답변. 마지막에 면책 문구 포함.
        - User: 신호 종류={kind}, 시점={ts}, 가격={price}
                지표 수치: SMA20={...}, SMA60={...}, RSI={...}, MACD={...}, ADX={...}
                요청: 1) 해당 신호가 어떤 의미인지 2) 현재 지표 수치 종합 평가 3) 주의 포인트
                형식: JSON {summary, detail, confidence: low|medium|high}

    캐시 키: f"{signal.kind}:{signal.timestamp.isoformat()}:{model}"
    캐시 hit 시 LLM 호출 생략.
    """


def interpret_signals_batch(
    signals: list[Signal],
    df: pd.DataFrame,
    max_concurrent: int = 5,
) -> list[AICommentary]:
    """
    [Sync 래퍼] 내부적으로 async 함수 `_interpret_async()`를 `asyncio.run()`으로 실행.
    Streamlit(sync 컨텍스트)에서 호출 가능. Free tier rate limit(~30 req/min) 준수를 위해
    `asyncio.Semaphore(max_concurrent)`로 동시성 제어. 결과는 input 순서 유지.

    구현 패턴:
        async def _interpret_async(signals, df, sem) -> list[AICommentary]: ...
        def interpret_signals_batch(signals, df, max_concurrent=5):
            sem = asyncio.Semaphore(max_concurrent)
            return asyncio.run(_interpret_async(signals, df, sem))

    Streamlit 호출 예시:
        commentaries = interpret_signals_batch(signals[:20], df)
    """
```

#### `core.portfolio.analyze`

```python
def analyze(
    portfolio: Portfolio,
    as_of: pd.Timestamp | None = None,
    interval: Interval = Interval.D1,
    lookback_days: int = 180,
) -> PortfolioAnalysis:
    """
    보유 종목 각각에 대해 data_loader.fetch + indicators.compute +
    trend.classify + signals.detect_all 을 호출하고, 평가금액·손익·비중을 집계.

    환율 처리:
        - 보유 USDT/USD 종목은 base_currency=KRW일 때 환율로 변환
        - 환율은 FinanceDataReader('USD/KRW') 사용

    Returns: PortfolioAnalysis (모든 holdings_analysis + 합계 + trend_summary)
    """


def load_holdings_from_csv(path: str | Path) -> Portfolio:
    """
    CSV 컬럼: market,symbol,quantity,avg_price,currency
    예시:
        crypto,BTCUSDT,0.05,65000,USDT
        kr_stock,005930,100,72000,KRW
    """
```

#### `core.brokers.base.BrokerProtocol` (v3 placeholder)

```python
from typing import Protocol

class BrokerProtocol(Protocol):
    """
    자동매매 broker 인터페이스. 본 사이클에서는 정의만, 구현 X.
    v3에서 KISAdapter, KiwoomAdapter, BinanceTradeAdapter 등을 구현.
    """
    name: str

    def place_order(self, req: OrderRequest) -> OrderResult:
        """주문 실행 — v3에서 구현"""
        ...

    def cancel_order(self, order_id: str) -> bool: ...

    def get_positions(self) -> list[Holding]: ...

    def get_balance(self, currency: str) -> float: ...
```

### 4.3 신호 알고리즘 의사코드

> **Signal.strength**: v0.2에서는 모든 신호 `strength = 1.0` 고정.
> v2에서 다음 공식으로 정밀화 예정:
> - 골든/데드 크로스: `min(1.0, abs(curr_short - curr_long) / curr_long * 100)`
> - RSI 신호: `abs(curr_rsi - 50) / 50`
> - RSI 다이버전스: `abs(price_low_a - price_low_b) / price_low_b * (rsi_low_a - rsi_low_b) / 30`
> - MACD 교차: `abs(curr_macd - curr_sig) / abs(curr_sig + 1e-9)` 정규화

#### 골든/데드 크로스
```
prev_short = df["SMA_20"].shift(1)
prev_long  = df["SMA_60"].shift(1)
curr_short = df["SMA_20"]
curr_long  = df["SMA_60"]

golden = (prev_short <= prev_long) & (curr_short > curr_long)
death  = (prev_short >= prev_long) & (curr_short < curr_long)

→ 각 True 시점에 Signal(kind, action=buy/sell, ...)
```

#### RSI 과매수/과매도
```
prev_rsi = df["RSI_14"].shift(1)
curr_rsi = df["RSI_14"]

overbought_entry = (prev_rsi <= 70) & (curr_rsi > 70)  # action=sell
oversold_entry   = (prev_rsi >= 30) & (curr_rsi < 30)  # action=buy
```

#### RSI 강세 다이버전스 (의사코드)
```
lookback = 20
for each window of size lookback:
    price_low_idx  = argmin(close in window)
    rsi_low_idx    = argmin(RSI_14 in window)

    # 강세 다이버전스: 가격은 신저점 갱신, RSI는 미갱신
    if close[t] < close[price_low_idx_prev_window]:
        if RSI_14[t] > RSI_14[rsi_low_idx_prev_window]:
            signal = bull_div (action=buy)
```

#### MACD 교차
```
prev_macd = df["MACD_12_26_9"].shift(1)
prev_sig  = df["MACDs_12_26_9"].shift(1)
curr_macd = df["MACD_12_26_9"]
curr_sig  = df["MACDs_12_26_9"]

bull_cross = (prev_macd <= prev_sig) & (curr_macd > curr_sig)  # action=buy
bear_cross = (prev_macd >= prev_sig) & (curr_macd < curr_sig)  # action=sell
```

---

## 4.5 REST API Specification (FastAPI 엔드포인트)

> 모든 응답은 JSON. 에러는 `{"error": {"code": "...", "message": "...", "details": {}}}` 표준 포맷.
> 모든 엔드포인트 prefix: `/api`

### 4.5.1 엔드포인트 목록

| Method | Path | 입력 | 출력 | core 호출 |
|--------|------|------|------|-----------|
| GET | `/api/health` | — | `{status:"ok", version:"0.4.0"}` | — |
| GET | `/api/ohlcv` | query: `market`, `symbol`, `interval`, `start`, `end` | `OHLCVResponse` | `data_loader.fetch` |
| GET | `/api/indicators` | query: 위 + `config` (JSON) | `IndicatorsResponse` | `data_loader.fetch` + `indicators.compute` |
| GET | `/api/signals` | query: 위 OHLCV 입력 | `SignalsResponse` | `signals.detect_all` |
| GET | `/api/trend` | query: 위 OHLCV 입력 | `TrendResponse` | `trend.classify` |
| POST | `/api/ai/explain` | body: `AIExplainRequest` | `AICommentary` | `ai_interpreter.interpret_signal` |
| POST | `/api/portfolio` | body: `PortfolioRequest` | `PortfolioAnalysis` | `portfolio.analyze` |
| POST | `/api/backtest` | body: `BacktestRequest` | `BacktestResult` | `backtest.run` |
| GET | `/api/market/snapshot` | — | `MarketSnapshot` (KOSPI/KOSDAQ/USD-KRW/BTC/DXY/VIX) | `data_loader.fetch` (배치) |

### 4.5.2 주요 요청/응답 스키마 (Pydantic)

```python
# backend/api/schemas.py — Pydantic 모델 (core.types와 1:1 매핑)
from pydantic import BaseModel, Field
from typing import Literal

class OHLCVResponse(BaseModel):
    market: Literal["crypto", "kr_stock"]
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h", "4h", "1d"]
    candles: list[dict]   # [{t, o, h, l, c, v}, ...]   t = unix ms
    cached: bool          # 캐시 hit 여부

class IndicatorsResponse(OHLCVResponse):
    indicators: dict      # {"SMA_20": [...], "RSI_14": [...], "MACD_12_26_9": [...], ...}

class SignalsResponse(BaseModel):
    market: str
    symbol: str
    signals: list[dict]   # [{t, kind, action, price, strength, detail}, ...]

class TrendResponse(BaseModel):
    market: str
    symbol: str
    trend: Literal["uptrend", "downtrend", "sideways"]
    adx: float
    ma_alignment: dict    # {"sma_20": ..., "sma_60": ..., "sma_120": ...}

class AIExplainRequest(BaseModel):
    signal_kind: str
    timestamp: int        # unix ms
    symbol: str
    market: str
    indicators_at_signal: dict  # {"rsi": 56.3, "macd": 12.5, "ma_short": 67200, ...}
    price: float

class PortfolioRequest(BaseModel):
    holdings: list[dict]  # [{market, symbol, quantity, avg_price, currency}, ...]
    base_currency: Literal["KRW", "USD"] = "KRW"
    as_of: int | None = None  # unix ms, None = 최신

class BacktestRequest(BaseModel):
    market: str
    symbol: str
    interval: str
    start: int
    end: int
    strategy: Literal["ma_cross"] = "ma_cross"
    cash: float = 10_000_000
    commission: float = 0.0005

class MarketSnapshot(BaseModel):
    kospi: dict           # {value, change_pct}
    kosdaq: dict
    usd_krw: dict
    btc: dict
    dxy: dict
    vix: dict
    timestamp: int

# === 응답 스키마 (dataclass → Pydantic 변환) ===

class AICommentaryResponse(BaseModel):
    signal_kind: str
    timestamp: int                # unix ms (pd.Timestamp → ms)
    summary: str
    detail: str
    confidence: Literal["low", "medium", "high"]
    model: str
    generated_at: int
    disclaimer: str

class HoldingAnalysisResponse(BaseModel):
    market: str
    symbol: str
    quantity: float
    avg_price: float
    currency: str
    current_price_local: float
    current_price: float          # base_currency 기준
    market_value: float
    cost_basis: float
    pnl: float
    pnl_pct: float
    weight: float
    fx_rate: float
    trend: Literal["uptrend", "downtrend", "sideways"]
    latest_signals: list[dict]    # 최근 N개 (Signal 직렬화)

class FxQuoteResponse(BaseModel):
    pair: str                     # "USDT/KRW"
    rate: float
    as_of: int                    # unix ms
    source: str

class PortfolioAnalysisResponse(BaseModel):
    holdings_analysis: list[HoldingAnalysisResponse]
    total_market_value: float
    total_cost_basis: float
    total_pnl: float
    total_pnl_pct: float
    trend_summary: dict[str, int]  # {"uptrend": 3, "downtrend": 1, "sideways": 2}
    base_currency: Literal["KRW", "USD"]
    fx_rates: dict[str, FxQuoteResponse]
    as_of: int

class BacktestResultResponse(BaseModel):
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    sharpe_ratio: float
    num_trades: int
    equity_curve: list[dict]      # [{t: unix_ms, equity: float}, ...] (pd.Series → list of dict)
    trades: list[dict]            # [{entry_t, exit_t, side, qty, entry_price, exit_price, pnl}, ...]
```

**dataclass ↔ Pydantic ↔ JSON 직렬화 매핑**

| 도메인 (`core/types/schemas.py`) | API 응답 (`backend/api/schemas.py`) | JSON 직렬화 처리 |
|---------------------------------|-------------------------------------|-----------------|
| `Signal` (frozen dataclass) | inline dict in `SignalsResponse.signals` | enum → str.value, pd.Timestamp → unix ms |
| `AICommentary` | `AICommentaryResponse` | timestamp/generated_at → unix ms |
| `Holding` | inline in `HoldingAnalysisResponse` | as-is |
| `HoldingAnalysis` | `HoldingAnalysisResponse` | trend Enum → str |
| `FxQuote` | `FxQuoteResponse` | as_of → unix ms |
| `PortfolioAnalysis` | `PortfolioAnalysisResponse` | trend_summary 키 enum→str |
| `BacktestResult` | `BacktestResultResponse` | **`pd.Series`/`DataFrame` → `list[dict]`** |
| `TrendState`, `SignalKind`, `SignalAction`, `Market`, `Interval` | `Literal[...]` 또는 `str` | Enum.value 사용 |

> **변환 헬퍼**: `backend/api/converters.py`에 `to_response(dataclass) -> Pydantic` 함수 모음. dataclass의 `pd.Timestamp` 필드는 `int(ts.timestamp() * 1000)`로 변환.

### 4.5.3 CORS 정책

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5500").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

### 4.5.4 에러 응답 표준

```json
{
  "error": {
    "code": "DATA_SOURCE_ERROR",
    "message": "Binance API timeout after 3 retries",
    "details": {
      "endpoint": "/api/v3/klines",
      "symbol": "BTCUSDT"
    }
  }
}
```

| HTTP | code | 도메인 예외 (`core/types/errors.py`) | 발생 시점 |
|------|------|---------------------------------------|----------|
| 400 | `INVALID_INPUT` | `PortfolioError`, Pydantic `ValidationError` | 입력 검증 실패 (CSV 형식, 필수 필드 누락) |
| 404 | `INVALID_SYMBOL` | `InvalidSymbolError` | 심볼 미존재 |
| 422 | `INSUFFICIENT_DATA` | `InsufficientDataError` | 지표 계산 데이터 부족 (예: SMA_120인데 데이터 100개) |
| 429 | `RATE_LIMIT_EXCEEDED` | `DataSourceError` with `rate_limit=True` | 외부 API rate limit (Binance 1200/min) |
| 502 | `DATA_SOURCE_ERROR` | `DataSourceError` (rate_limit 외) | 외부 API 호출 실패 (timeout, 네트워크) |
| 503 | `AI_SERVICE_ERROR` | `AIServiceError` | Groq API 실패 — 해설만 영향, 신호는 정상 |
| 500 | `INTERNAL_ERROR` | `CacheError`, 그 외 `Exception` | 캐시 I/O 실패, 예상 못한 에러 |

> **중요**: `CacheError`는 백엔드 내부에서 가능하면 graceful (로그 남기고 캐시 우회 fetch)로 처리, 사용자에게는 `INTERNAL_ERROR`로 노출되지 않는 것이 이상적. 노출은 라스트 리조트.

### 4.5.5 프론트 fetch 패턴 (`Tradingmode/api.js`)

```javascript
// api.js — 모든 백엔드 호출의 단일 진입점
// 핵심 정책: AbortController, 타임아웃, 응답 검증, ApiError 표준화

const API_BASE = window.API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT = 15000;  // 15s

class ApiError extends Error {
  constructor(code, message, status, details = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

// 공통 응답 검증 (apiGet/apiPost가 공유)
async function _check(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = body?.error || {};
    throw new ApiError(
      err.code || 'UNKNOWN',
      err.message || res.statusText,
      res.status,
      err.details || {}
    );
  }
  return res.json();
}

// 타임아웃 + AbortSignal 결합 (사용자 signal과 자동 timeout 둘 다 지원)
function _withTimeout(signal, ms) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(new ApiError('TIMEOUT', `요청 시간 초과 (${ms}ms)`, 0)), ms);
  if (signal) signal.addEventListener('abort', () => ctl.abort(signal.reason));
  return { signal: ctl.signal, clear: () => clearTimeout(t) };
}

async function apiGet(path, params = {}, { signal, timeout = DEFAULT_TIMEOUT } = {}) {
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => v !== undefined && url.searchParams.set(k, v));
  const { signal: s, clear } = _withTimeout(signal, timeout);
  try {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' }, signal: s });
    return await _check(res);
  } finally { clear(); }
}

async function apiPost(path, body, { signal, timeout = DEFAULT_TIMEOUT } = {}) {
  const { signal: s, clear } = _withTimeout(signal, timeout);
  try {
    const res = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body),
      signal: s,
    });
    return await _check(res);
  } finally { clear(); }
}

window.api = {
  health:         (opt)        => apiGet('/api/health', {}, opt),
  ohlcv:          (params, opt) => apiGet('/api/ohlcv', params, opt),
  indicators:     (params, opt) => apiGet('/api/indicators', params, opt),
  signals:        (params, opt) => apiGet('/api/signals', params, opt),
  trend:          (params, opt) => apiGet('/api/trend', params, opt),
  marketSnapshot: (opt)         => apiGet('/api/market/snapshot', {}, opt),
  aiExplain:      (body, opt)   => apiPost('/api/ai/explain', body, opt),
  portfolio:      (body, opt)   => apiPost('/api/portfolio', body, opt),
  backtest:       (body, opt)   => apiPost('/api/backtest', body, opt),
};
window.ApiError = ApiError;
```

**Race condition 회피 (종목 빠른 전환 시 마지막 요청만 반영)**

```javascript
// 컴포넌트에서 사용 패턴
const ctlRef = useRef(null);
async function loadCurrent(symbol) {
  ctlRef.current?.abort();              // 직전 요청 취소
  const ctl = new AbortController();
  ctlRef.current = ctl;
  try {
    const data = await api.ohlcv({ ...params }, { signal: ctl.signal });
    if (!ctl.signal.aborted) setCandles(data.candles);
  } catch (e) {
    if (e.name !== 'AbortError') handleError(e);
  }
}
```

### 4.5.6 폴링·캐싱 정책

| 엔드포인트 | 호출 패턴 | 주기 / TTL |
|-----------|----------|-----------|
| `/api/market/snapshot` | TopBar에서 setInterval | **30초**, `document.visibilityState !== 'visible'` 시 일시정지, 백엔드 캐시 30s |
| `/api/ohlcv`, `/indicators`, `/signals`, `/trend` | 종목/타임프레임 변경 시 단발 | 단발 (캐시는 백엔드 parquet) |
| `/api/ai/explain` | 사용자 expander 클릭 시 단발 | 단발, 백엔드 (signal_kind, timestamp, model) 키로 영구 캐시 |
| `/api/portfolio` | CSV 업로드 / 입력 변경 시 단발 | 단발 |
| `/api/backtest` | "백테스트 실행" 버튼 단발 | 단발 |
| `/api/health` | 앱 마운트 시 1회 (백엔드 가용성 체크) | 단발 |

```javascript
// app.jsx — TopBar 폴링 패턴
useEffect(() => {
  let alive = true;
  let timerId = null;
  const ctlRef = { current: null };

  async function tick() {
    if (!alive || document.visibilityState !== 'visible') return;
    ctlRef.current?.abort();
    ctlRef.current = new AbortController();
    try {
      const snap = await api.marketSnapshot({ signal: ctlRef.current.signal });
      if (alive) setSnapshot(snap);
    } catch (e) { /* TopBar 시세는 silent fail (toast 안 띄움) */ }
  }

  tick();
  timerId = setInterval(tick, 30000);
  document.addEventListener('visibilitychange', tick);
  return () => {
    alive = false;
    clearInterval(timerId);
    document.removeEventListener('visibilitychange', tick);
    ctlRef.current?.abort();
  };
}, []);
```

---

## 5. UI/UX Design

> **방침**: 사용자 제공 React 프로토타입(`Tradingmode/`)을 정식 프론트엔드로 채택.
> 기존 디자인(다크 테마, OKLCH 색상, JetBrains Mono 모노스페이스, TRADINGMODE.LAB 브랜딩) 유지.
> v0.4 작업은 합성 데이터(`data.js`) → 백엔드 fetch(`api.js`) 점진 교체.

### 5.0 프론트엔드 파일 ↔ 기능 매핑

| File | 책임 | 백엔드 호출 |
|------|------|------------|
| `index.html` | 진입점, React/Babel CDN 로드, 스크립트 순서 정의 | — |
| `app.jsx` | 앱 셸: TopBar, Watchlist, 탭 라우팅, 전역 상태 | `api.marketSnapshot()` (TopBar 폴링) |
| `charts.jsx` | ChartPage — 캔들/지표 오버레이, 줌/팬, 드로잉(추세선·피보) | `api.ohlcv`, `api.indicators`, `api.signals`, `api.trend` |
| `signals-page.jsx` | SignalsPage — 신호 리스트, 필터, AI 해설 expander | `api.signals` (universe 전체), `api.aiExplain` (클릭 시) |
| `portfolio-page.jsx` | PortfolioPage — 보유 종목 테이블, treemap, 성과 차트 | `api.portfolio` (POST holdings) |
| `tweaks-panel.jsx` | 색상·임계값·표시 옵션 조절 패널 (개발용) | — |
| `data.js` | (전환 중) 합성 OHLCV 생성기 — v0.4 후반에 `api.js` 호출로 대체 | — |
| `api.js` ✨ NEW | 모든 백엔드 fetch 단일 진입점, 에러 정규화 | 자체 |
| `styles.css` | 다크 테마, OKLCH 색상 토큰, 레이아웃 | — |

### 5.1 화면 구조 (React SPA)

```
┌──────────────────────────────────────────────────────────────────┐
│ TopBar  (TRADINGMODE.LAB v0.x · DEV)                             │
│  Logo │ KOSPI ▲0.42% · KOSDAQ ▼0.31% · USD/KRW · BTC · DXY · VIX │
│       │                                            🟢 LIVE  KST  │
├──────────────┬───────────────────────────────────────────────────┤
│ Watchlist    │ Tabs: [Chart] [Signals] [Portfolio]               │
│ (사이드바)    │ ────────────────────────────────────────────────── │
│ [전체|KR|CR] │ DataStatusBar: 🟢 OK · Binance Spot · 캐시 적중  │
│ ┌──────────┐ │ ┌───────────────────────────────────────────────┐│
│ │BTCUSDT ↑ │ │ │ [현재 추세] 🟢 상승  ADX=32  MA정배열         ││
│ │005930  · │ │ │ Interval: [1d] [1h] [15m]   Zoom: [1M][3M][1Y]││
│ │... 미니   │ │ │ ────────────────────────────────────────── ││
│ │ 스파크    │ │ │ [SVG 캔들차트 + SMA(5/20/60/120) 오버레이]    ││
│ │ ─────    │ │ │ [RSI 서브차트] [MACD 서브차트]                ││
│ └──────────┘ │ │ [드로잉: 추세선 · 피보나치]                   ││
│              │ └───────────────────────────────────────────────┘│
└──────────────┴───────────────────────────────────────────────────┘

* Tabs 클릭 시 메인 영역만 교체 (Watchlist/TopBar는 항상 유지).
* DataStatusBar는 매 fetch마다 OK / LOADING / RATE_LIMIT / ERROR 갱신.
```

### 5.2 User Flow

```
[1] 백엔드 기동
    $ cd backend && uvicorn main:app --reload --port 8000
    $ open http://localhost:8000/docs   (OpenAPI 확인)

[2] 프론트 정적 호스팅
    $ python -m http.server 5500 --directory Tradingmode
    $ 브라우저로 http://localhost:5500 접속

[3] 사용 흐름 (단일 SPA)
    초기 로드 → app.jsx mount → api.marketSnapshot() (TopBar)
        │                    → api.ohlcv/indicators/signals/trend (현재 종목)
        ▼
    Watchlist 종목 클릭 → currentSymbol 변경 → 메인 영역 자동 재페치
        │
        ├─→ [Chart Tab]     → charts.jsx → 캔들+지표+신호 마커+드로잉
        │
        ├─→ [Signals Tab]   → signals-page.jsx → 전체 universe 신호 리스트
        │                                    → 항목 클릭 → api.aiExplain()
        │                                    → AI 해설 expander 렌더
        │
        └─→ [Portfolio Tab] → portfolio-page.jsx
                              → CSV 업로드 또는 MOCK_HOLDINGS
                              → api.portfolio() POST → 집계 표시

[3] 백테스팅 (별도 03 탭)
    BacktestPage → 전략 선택 → api.backtest() POST
        → equity curve + 통계 표시
        → 현재 종목 컨텍스트 공유 (instrument prop)

[4] 포트폴리오
    PortfolioPage → api.portfolio() POST → 집계 표시
```

### 5.3 React 페이지 컴포넌트

> **백테스팅 위치 결정 (v1 채택)**: 별도 **03 백테스팅** 탭으로 분리 (FR-13 "Chart 페이지 또는 별도" 중 별도 탭 선택).
> 이유: 화면 활용도가 높고, 장기 기간 결과 표(equity curve + 통계)를 넓게 표시하기 유리하다.
> 현재 종목 컨텍스트는 `instrument` prop으로 BacktestPage에 전달하므로 차트와 동기화된다.

| Page | 탭 번호 | 핵심 컴포넌트 | API 호출 |
|------|:------:|--------------|---------|
| `app.jsx` | — | `TopBar`(시세 테이프), `Watchlist`(KR/CRYPTO 필터, 미니 스파크), `DataStatusBar`, 4탭 라우팅 | `api.marketSnapshot()` (30s 폴링) |
| `charts.jsx` (ChartPage) | 01 | 캔들 차트(SVG), MA 오버레이, RSI/MACD 서브차트, 드로잉 도구(trend/fib), 줌 프리셋(1M/3M/6M/1Y) | `api.ohlcv`, `api.indicators`, `api.trend`, `api.signals` |
| `signals-page.jsx` (SignalsPage) | 02 | BUY/SELL 필터, 시장 필터, recency 슬라이더, 신호 리스트, **AI 해설 expander** (llama-3.3-70b-versatile) | `api.signals` (universe 전체), `api.aiExplain` |
| `backtest.jsx` (BacktestPage) | 03 | 전략 선택(MA Cross), cash/commission 설정, equity curve, 통계 테이블(수익률·MDD·샤프·승률) | `api.backtest` |
| `portfolio-page.jsx` (PortfolioPage) | 04 | 보유 테이블(추세·손익·비중), 도넛 배분, 성과 곡선(1M/3M/6M/1Y/ALL), 백엔드 FX/trend 연동 | `api.portfolio` |

### 5.4 포트폴리오 페이지 레이아웃

> 실제 구현은 `Tradingmode/portfolio-page.jsx` 참조. 아래는 와이어프레임.

```
┌────────────────────────────────────────────────────────────┐
│ Portfolio                                                  │
├────────────────────────────────────────────────────────────┤
│ [📁 CSV 업로드] [+ 수동 추가]   기준통화: [KRW ▼] 기간: [3M ▼] │
├────────────────────────────────────────────────────────────┤
│ 평가금액: ₩142.3M   손익: +₩8.4M (+6.27%)  일변동: +0.42%   │
│ 추세 분포: 🟢 상승 5 / 🔴 하락 2 / ⚪ 횡보 1               │
├────────────────────────────────────────────────────────────┤
│ [Treemap — 비중 시각화]      [성과 곡선 — 기간별]           │
├────────────────────────────────────────────────────────────┤
│ 종목     │ 추세 │ 평가금액 │ 손익(%)  │ 비중 │ 최근신호    │
│ BTC/USDT │ 🟢  │ ₩42.5M  │ +18.2%  │ 30% │ 골든크로스   │
│ 005930   │ ⚪  │ ₩28.4M  │ -1.1%   │ 20% │ -          │
│ ...                                                        │
└────────────────────────────────────────────────────────────┘
```

### 5.5 AI 해설 UI (Signals 페이지 내)

```
🎯 [골든크로스] 2026-04-22 ₩68,500
   📈 차트 마커 클릭 → 다음 expander 펼침
   ▼ 🤖 AI 해설 (llama-3.3-70b-versatile)
       요약: 단기/중기 이평선이 상향 교차하며 강세 모멘텀이 형성됨.
       상세: SMA20(67,200)이 SMA60(66,800)을 상향 돌파했으며
            ADX는 28.5로 추세 강도가 충분합니다. RSI 56으로 과열 영역
            아니므로 추가 상승 여력이 있어 보입니다. 다만...
       신뢰도: medium  |  ⚠️ 본 해설은 참고용, 투자 자문 아님
```

**프론트 호출 흐름**:
```
사용자 expander 클릭
  → signals-page.jsx: api.aiExplain({signal_kind, timestamp, symbol, indicators_at_signal})
  → POST /api/ai/explain
  → backend/api/ai.py: 입력 검증 + 캐시 키 조회
  → core.ai_interpreter.interpret_signal(signal, df_window)
  → Groq SDK 호출 (백엔드만, 키 보호)
  → AICommentary 반환 (캐시 저장)
  → 프론트 expander에 렌더 (loading/ready/error 상태)
```

> **캐시**: `(symbol, signal_kind, timestamp, model)` 키로 백엔드에서 영구 캐시 → 동일 신호 재해설 시 LLM 호출 0회.

---

## 6. Error Handling

### 6.1 Error Class 정의

```python
# core/types/errors.py  (Domain cross-cut — pages/core 모두 import 가능)
class TradingToolError(Exception):
    """모든 도메인 에러의 베이스"""

class DataSourceError(TradingToolError):
    """외부 API 호출 실패 (네트워크/Rate limit/서버 에러)"""

class InvalidSymbolError(TradingToolError):
    """존재하지 않는 심볼 또는 잘못된 형식"""

class InsufficientDataError(TradingToolError):
    """지표 계산에 필요한 최소 데이터 미달 (예: SMA_120인데 데이터 100개)"""

class CacheError(TradingToolError):
    """캐시 읽기/쓰기 실패"""

class AIServiceError(TradingToolError):
    """Groq API 호출 실패 (rate limit, 인증 실패, 네트워크)"""

class PortfolioError(TradingToolError):
    """포트폴리오 입력/분석 실패 (CSV 형식 오류, 종목 없음 등)"""
```

### 6.2 에러 처리 정책

| Error | 발생 위치 | 처리 |
|-------|----------|------|
| `DataSourceError` | adapters/* | 3회 지수 백오프 재시도 후 사용자에 메시지 표시 |
| `InvalidSymbolError` | data_loader, adapters | 즉시 `st.error()`로 표시, 입력 재요청 |
| `InsufficientDataError` | indicators | 사용자에게 기간 확장 안내 |
| `CacheError` | lib.cache | 경고 후 캐시 우회하여 직접 호출 (degraded) |
| `AIServiceError` | ai_interpreter | AI 해설 비활성화 + 신호만 표시 (degraded), 사이드바에 경고 |
| `PortfolioError` | portfolio | CSV 형식 안내 + 예시 표시 |
| `KeyboardInterrupt` | 모든 곳 | 정상 종료 |

### 6.3 사용자 메시지 포맷

**백엔드** — FastAPI exception_handler가 도메인 예외를 표준 JSON으로 변환:

```python
# backend/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core.types.errors import (
    DataSourceError, InvalidSymbolError, InsufficientDataError,
    AIServiceError, PortfolioError, CacheError, TradingToolError,
)

app = FastAPI()

ERROR_MAP = {
    InvalidSymbolError:       (404, "INVALID_SYMBOL"),
    InsufficientDataError:    (422, "INSUFFICIENT_DATA"),
    PortfolioError:           (400, "INVALID_INPUT"),
    AIServiceError:           (503, "AI_SERVICE_ERROR"),
    DataSourceError:          (502, "DATA_SOURCE_ERROR"),
    CacheError:               (500, "INTERNAL_ERROR"),
}

@app.exception_handler(TradingToolError)
async def domain_error_handler(request: Request, exc: TradingToolError):
    status, code = ERROR_MAP.get(type(exc), (500, "INTERNAL_ERROR"))
    # Rate limit은 DataSourceError의 detail로 분기
    if isinstance(exc, DataSourceError) and getattr(exc, "rate_limit", False):
        status, code = 429, "RATE_LIMIT_EXCEEDED"
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": str(exc), "details": getattr(exc, "details", {})}},
    )
```

**프론트** — `api.js`의 `ApiError`를 catch하여 DataStatusBar/토스트로 표시:

```javascript
// charts.jsx (또는 다른 페이지)
try {
  setStatus({ status: 'loading', message: `${symbol} ${interval} 수집 중…`, source: ... });
  const data = await api.ohlcv({ market, symbol, interval, start, end });
  setStatus({ status: 'ok', message: data.cached ? '캐시 적중' : '신규 수집', source: ... });
  setCandles(data.candles);
} catch (e) {
  // e: ApiError { code, message, status }
  const statusMap = {
    'RATE_LIMIT_EXCEEDED': { status: 'rate_limit', message: e.message },
    'DATA_SOURCE_ERROR':   { status: 'error',      message: `데이터 수집 실패: ${e.message}` },
    'INVALID_SYMBOL':      { status: 'error',      message: `종목 코드를 확인해주세요: ${e.message}` },
    'INSUFFICIENT_DATA':   { status: 'error',      message: `기간이 짧습니다. 더 긴 기간을 선택하세요.` },
    'AI_SERVICE_ERROR':    { status: 'error',      message: 'AI 해설 일시 사용 불가 (신호는 정상 표시)' },
  };
  setStatus(statusMap[e.code] || { status: 'error', message: e.message });
}
```

**에러 코드 → DataStatusBar 매핑**

| 백엔드 응답 `error.code` | DataStatusBar 상태 | 사용자 메시지 |
|--------------------------|-------------------|--------------|
| `RATE_LIMIT_EXCEEDED` | `rate_limit` (오렌지) | "Binance 1200 req/min 초과 — 60초 백오프" |
| `DATA_SOURCE_ERROR` | `error` (빨강) | "데이터 수집 실패 (재시도 권장)" |
| `INVALID_SYMBOL` | `error` | "종목 코드를 확인해주세요" |
| `INSUFFICIENT_DATA` | `error` | "기간이 짧습니다" |
| `AI_SERVICE_ERROR` | `error` (해설 영역만) | "AI 해설 사용 불가, 신호는 정상" |
| `INTERNAL_ERROR` | `error` | "서버 오류 (로그 확인)" |
| (성공) | `ok` (초록) / `loading` (노랑) | 평상시 |

---

## 7. Security Considerations

> **컨텍스트**: 로컬 단일 사용자 분석 툴. 인증/권한/네트워크 노출 없음.

- [x] 입력 검증: 심볼 형식 정규식 검증 (예: `^[A-Z0-9]{1,20}$`)
- [x] API 키 보호: `.env` + `python-dotenv`, `.gitignore`에 등록 (Binance, Groq 모두)
- [x] 캐시 디렉토리 권한: 사용자 홈 또는 프로젝트 내, 절대 경로 검증으로 path traversal 방지
- [x] Rate Limit 준수: Binance 1200 req/min, **Groq free tier ~30 req/min** (semaphore + 캐시)
- [x] LLM 프롬프트 인젝션 방지: 사용자 입력을 직접 prompt에 끼워넣지 않음. 모든 입력은 Pydantic/dataclass로 검증 후 구조화된 필드로 전달
- [x] LLM 환각 면책: 모든 AI 출력에 "투자 자문 아님" 면책 문구 자동 첨부
- [x] 포트폴리오 CSV 검증: 컬럼 수·타입·범위 검증 (예: quantity > 0, avg_price > 0)
- [ ] HTTPS 강제: 외부 라이브러리에서 자동 처리 (별도 작업 없음)
- [ ] 인증/인가: N/A (단일 사용자)
- [ ] **자동매매 안전장치**: v3 구현 시 추가 (현재는 인터페이스 정의만)

---

## 8. Test Plan

### 8.1 Test Scope

| Type | Target | Tool |
|------|--------|------|
| Unit Test | indicators, signals, trend, backtest | pytest |
| Integration Test | data_loader (mocked adapter) | pytest + responses/vcr |
| Smoke Test | Streamlit 페이지 렌더 | streamlit-testing-library |
| Manual Test | 실제 종목으로 end-to-end 시연 | 수동 실행 |

### 8.2 핵심 테스트 케이스

#### indicators
- [ ] **Happy**: 100일치 OHLCV 입력 → SMA_20 컬럼 정확히 80개 유효값
- [ ] **Edge**: 데이터 50개 + SMA_120 요청 → `InsufficientDataError`
- [ ] **수치 검증**: 알려진 값으로 RSI 직접 계산 vs `add_rsi()` 결과 일치

#### signals
- [ ] **Happy (golden cross)**: 합성 데이터에서 MA20이 MA60 상향 돌파 → 정확한 timestamp의 Signal 1개 반환
- [ ] **Edge**: 데이터 부족 시 빈 list 반환 (예외 아님)
- [ ] **다이버전스**: 의도적으로 조작한 데이터에서 강세 다이버전스 1건 정확히 감지

#### trend
- [ ] MA 정배열 + ADX=30 → UPTREND
- [ ] MA 역배열 + ADX=30 → DOWNTREND
- [ ] ADX=20 (어떤 배열이든) → SIDEWAYS

#### backtest
- [ ] 항상 Buy/Hold 전략 → total_return ≈ (close[-1]/close[0] - 1) * 100
- [ ] num_trades, equity_curve 길이 일치
- [ ] BacktestResult 필드 모두 numeric, NaN 없음

#### data_loader (integration)
- [ ] 캐시 hit 시 어댑터 호출 0회 (mock으로 검증)
- [ ] 캐시 miss 시 어댑터 호출 1회, 이후 캐시 파일 생성됨
- [ ] InvalidSymbolError 발생 시 캐시 미생성

#### ai_interpreter
- [ ] **Mock Groq client**: 동일 (signal_kind, timestamp) 입력 → LLM 호출 1회만, 2회차는 캐시 hit
- [ ] AICommentary.disclaimer 자동 첨부됨
- [ ] AIServiceError 발생 시 None 또는 fallback Commentary 반환 (앱 중단 X)
- [ ] 프롬프트에 사용자 입력이 그대로 포함되지 않음 (인젝션 방지 검증)

#### portfolio
- [ ] CSV 정상 입력 → Holdings list 정확히 파싱
- [ ] 잘못된 CSV(컬럼 누락) → PortfolioError
- [ ] analyze() 결과 weight 합계 ≈ 1.0 (±0.001)
- [ ] 추세 분포 카운트가 holdings 수와 일치
- [ ] USDT 보유 + base=KRW일 때 환율 적용 검증

---

## 9. Clean Architecture

### 9.1 Layer Structure

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **Frontend** | UI 렌더, 사용자 인터랙션, 백엔드 호출, 시각화 (도메인 로직 0%) | `Tradingmode/` |
| **API Boundary** | HTTP 입력 검증, Pydantic ↔ dataclass 변환, 에러 매핑 | `backend/api/` |
| **Application** | 분석 오케스트레이션, 비즈니스 로직 | `backend/core/data_loader.py`, `backend/core/backtest.py`, `portfolio.py`, `ai_interpreter.py` |
| **Domain** | 순수 도메인 함수, 타입 정의 | `backend/core/indicators.py`, `signals.py`, `trend.py`, `types/schemas.py`, `types/errors.py` |
| **Infrastructure** | 외부 API, 캐시, 로깅 | `backend/core/adapters/`, `backend/core/brokers/`, `backend/lib/` |

### 9.2 Dependency Rules

```
Frontend ──HTTP/JSON──→ API Boundary → Application → Domain ← Infrastructure
                                            │
                                            └→ Infrastructure

(Frontend은 백엔드 외부 — Python 코드 import 불가)
```

- 프론트는 **`api.js`만을 통해** 백엔드 호출 (직접 fetch 사용 X)
- `backend/api/*.py`는 **thin controller**: 검증 → core 호출 → 변환만, 비즈니스 로직 X
- `backend/core/indicators / signals / trend`는 외부 의존성 없음 (pandas-ta는 Domain에 허용)
- `backend/core/adapters`는 `core.types`만 import 가능

### 9.3 File Import Rules

| From | Can Import | Cannot Import |
|------|-----------|---------------|
| `Tradingmode/*.jsx` | `Tradingmode/api.js`, React | 백엔드 Python 직접 (HTTP만) |
| `backend/api/*` | `backend/core.*`, `backend/lib.*` (제한적), Pydantic | 외부 라이브러리 직접 (core 경유) |
| `backend/core/data_loader` (Application) | `core.adapters.*`, `core.types.*`, `lib.cache` | `backend/api/*` |
| `backend/core/indicators/signals/trend` (Domain) | `pandas`, `pandas-ta`, `core.types.*` | `core.adapters.*`, `lib.*`, `api/*` |
| `backend/core/adapters/*` (Infra) | `core.types.*`, 외부 라이브러리 | `core.indicators`, `api/*` |
| `backend/core/ai_interpreter` (Application) | `core.types.*`, `lib.cache`, `groq` | `api/*`, 도메인 함수에 강한 결합 X |

### 9.4 모듈별 레이어 매핑

| Module | Layer | Path |
|--------|-------|------|
| `Tradingmode/index.html` | Frontend | `C:/X/new/Tradingmode/` |
| `Tradingmode/app.jsx` | Frontend | `C:/X/new/Tradingmode/` |
| `Tradingmode/charts.jsx` | Frontend | `C:/X/new/Tradingmode/` |
| `Tradingmode/signals-page.jsx` | Frontend | `C:/X/new/Tradingmode/` |
| `Tradingmode/portfolio-page.jsx` | Frontend | `C:/X/new/Tradingmode/` |
| `Tradingmode/api.js` ✨ | Frontend (백엔드 fetch 단일 진입점) | `C:/X/new/Tradingmode/` |
| `backend/main.py` | API Boundary | `C:/X/new/backend/` |
| `backend/api/*.py` | API Boundary | `C:/X/new/backend/api/` |
| `backend/core/data_loader.py` | Application | `C:/X/new/backend/core/` |
| `backend/core/backtest.py` | Application | `C:/X/new/backend/core/` |
| `backend/core/portfolio.py` | Application | `C:/X/new/backend/core/` |
| `backend/core/ai_interpreter.py` | Application | `C:/X/new/backend/core/` |
| `backend/core/indicators.py` | Domain | `C:/X/new/backend/core/` |
| `backend/core/signals.py` | Domain | `C:/X/new/backend/core/` |
| `backend/core/trend.py` | Domain | `C:/X/new/backend/core/` |
| `backend/core/types/schemas.py` | Domain | `C:/X/new/backend/core/types/` |
| `backend/core/types/errors.py` | Domain (cross-cut) | `C:/X/new/backend/core/types/` |
| `backend/core/adapters/binance_adapter.py` | Infrastructure | `C:/X/new/backend/core/adapters/` |
| `backend/core/adapters/krx_adapter.py` | Infrastructure | `C:/X/new/backend/core/adapters/` |
| `backend/core/brokers/base.py` | Infrastructure (v3 IF만) | `C:/X/new/backend/core/brokers/` |
| `backend/lib/cache.py` | Infrastructure | `C:/X/new/backend/lib/` |
| `backend/lib/logger.py` | Infrastructure | `C:/X/new/backend/lib/` |

---

## 10. Coding Convention

### 10.1 Naming Conventions (Python)

| Target | Rule | Example |
|--------|------|---------|
| Modules / Files | snake_case.py | `data_loader.py`, `binance_adapter.py` |
| Classes | PascalCase | `BinanceAdapter`, `BacktestResult` |
| Functions / Variables | snake_case | `fetch_ohlcv`, `rsi_period` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_CACHE_DIR`, `MAX_RETRIES` |
| Type aliases | PascalCase | `SignalKind`, `Interval` |
| Enums | PascalCase (class), UPPER_SNAKE (member) | `class Market: CRYPTO = ...` |
| Private | `_` prefix | `_normalize_dataframe` |
| Folders | snake_case (Python 표준) | `core/`, `core/adapters/` |

### 10.2 Import Order (isort 호환)

```python
# 1. 표준 라이브러리
from datetime import datetime
from pathlib import Path

# 2. 서드파티
import pandas as pd
import pandas_ta as ta
from binance.client import Client

# 3. 로컬 absolute
from core.types.schemas import Signal, TrendState
from lib.cache import load_or_fetch

# 4. 로컬 relative (같은 패키지 내부만)
from .helpers import normalize_symbol
```

### 10.3 Environment Variables

| Prefix | Purpose | Scope | Example |
|--------|---------|-------|---------|
| `BINANCE_` | Binance 인증 (선택) | Backend | `BINANCE_API_KEY`, `BINANCE_API_SECRET` |
| `GROQ_` | Groq API 키 (백엔드만 보유) | Backend | `GROQ_API_KEY`, `GROQ_MODEL=llama-3.3-70b-versatile` |
| `CACHE_` | 캐시 설정 | Backend | `CACHE_DIR=./data` |
| `LOG_` | 로깅 설정 | Backend | `LOG_LEVEL=INFO` |
| `BACKEND_` | FastAPI 호스트/포트 | Backend | `BACKEND_HOST=127.0.0.1`, `BACKEND_PORT=8000` |
| `CORS_ORIGINS` | CORS 허용 origin 콤마 구분 리스트 | Backend | `CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500` |
| `API_BASE_URL` | 프론트가 호출할 백엔드 URL | Frontend (런타임 주입) | `window.API_BASE_URL = 'http://localhost:8000'` |

> 백엔드는 `.env` + `python-dotenv`. 프론트 `API_BASE_URL`은 `index.html`에 `<script>window.API_BASE_URL = '...'</script>` 또는 빌드 시 주입(v2).
> `.gitignore`에 `.env` 등록.

### 10.4 Linting / Formatting

| Tool | 설정 |
|------|------|
| `ruff` | line-length=100, select=E/F/W/I/N/UP/B |
| `black` | line-length=100, target-version=py311 |
| `mypy` | strict optional, allow_untyped_defs=False (단계적 도입) |

`pyproject.toml`에 통합 정의.

### 10.5 본 기능 적용

| Item | 적용 |
|------|------|
| Component naming (백엔드) | snake_case 모듈, PascalCase 클래스 (예: `BinanceAdapter`) |
| Component naming (프론트) | PascalCase React 컴포넌트 (`TopBar`, `Watchlist`, `ChartPage`) |
| File organization | `Tradingmode/`(프론트) + `backend/{api,core,lib,tests}` 분리 |
| State management | 프론트: React `useState`/`Context` (라우팅 상태·현재 종목·DataStatus). 백엔드: stateless (캐시는 parquet/JSON) |
| Error handling | 백엔드: `core/types/errors.py` + FastAPI `exception_handler` → JSON. 프론트: `api.js` `ApiError` → DataStatusBar 갱신 + 토스트 |
| Type hints | 백엔드: 모든 public 함수 시그니처 필수. 프론트: JSDoc `@typedef` (v0.4) → TypeScript(v2) |

---

## 11. Implementation Guide

### 11.1 File Structure (실제 생성 대상)

```
C:/X/new/
├── Tradingmode/                 # 프론트엔드 (사용자 제공 + api.js 추가)
│   ├── index.html
│   ├── app.jsx
│   ├── charts.jsx
│   ├── signals-page.jsx
│   ├── portfolio-page.jsx
│   ├── tweaks-panel.jsx
│   ├── data.js                  # 합성 데이터 (점진적으로 api.js로 대체)
│   ├── api.js                   # ✨ NEW: 백엔드 fetch 단일 진입점
│   ├── styles.css
│   └── uploads/                 # CSV 업로드 임시 (옵션)
│
├── backend/                     # FastAPI 백엔드
│   ├── main.py                  # FastAPI 앱 + CORSMiddleware
│   ├── api/
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic 모델
│   │   ├── ohlcv.py
│   │   ├── indicators.py
│   │   ├── signals.py
│   │   ├── trend.py
│   │   ├── portfolio.py
│   │   ├── backtest.py
│   │   ├── ai.py
│   │   └── market.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── data_loader.py
│   │   ├── indicators.py
│   │   ├── signals.py
│   │   ├── trend.py
│   │   ├── backtest.py
│   │   ├── ai_interpreter.py
│   │   ├── portfolio.py
│   │   ├── types/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── errors.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── binance_adapter.py
│   │   │   └── krx_adapter.py
│   │   └── brokers/
│   │       ├── __init__.py
│   │       └── base.py
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   └── logger.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_indicators.py
│   │   ├── test_signals.py
│   │   ├── test_trend.py
│   │   ├── test_backtest.py
│   │   ├── test_data_loader.py
│   │   ├── test_ai_interpreter.py
│   │   ├── test_portfolio.py
│   │   └── test_api/            # ✨ NEW: FastAPI TestClient 통합 테스트
│   │       ├── test_ohlcv.py
│   │       ├── test_signals.py
│   │       └── test_ai.py
│   ├── pyproject.toml
│   └── requirements.txt
│
├── docs/                        # PDCA 문서
├── data/                        # parquet 캐시 (gitignore, backend가 사용)
├── examples/
│   └── holdings_sample.csv
├── .env.example
├── .gitignore
└── README.md
```

### 11.2 Implementation Order

> **원칙**: 백엔드 Domain → Infra → Application → API → 프론트 fetch 통합 순서.
> 프론트는 이미 사용자가 합성 데이터로 동작 가능하므로, **백엔드 우선 구현 후 프론트 `data.js`를 `api.js`로 교체**.

#### Backend (단계 1~6, 약 4시간)

1. **Setup (10분)**
   - [ ] `backend/pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore` 작성
   - [ ] uv 또는 venv로 가상환경 생성, 의존성 설치

2. **Domain Layer (50분)**
   - [ ] `backend/core/types/schemas.py` — dataclass/Enum/Protocol (Holding, Portfolio, AICommentary, BrokerProtocol, Strategy)
   - [ ] `backend/core/types/errors.py` — 커스텀 예외 (DataSourceError, InvalidSymbolError, InsufficientDataError, AIServiceError, PortfolioError, CacheError)
   - [ ] `backend/core/indicators.py` — pandas-ta 래퍼, `compute()` 일괄 함수
   - [ ] `backend/tests/test_indicators.py`
   - [ ] `backend/core/signals.py` — 4종 신호 감지 + `detect_all()`
   - [ ] `backend/tests/test_signals.py`
   - [ ] `backend/core/trend.py` — `classify()`
   - [ ] `backend/tests/test_trend.py`

3. **Infrastructure Layer (50분)**
   - [ ] `backend/lib/logger.py`
   - [ ] `backend/lib/cache.py` — OHLCV parquet + AI 응답 JSON 캐시
   - [ ] `backend/core/adapters/binance_adapter.py`
   - [ ] `backend/core/adapters/krx_adapter.py`
   - [ ] `backend/core/brokers/base.py` — `BrokerProtocol` (구현 X)

4. **Application Layer (60분)**
   - [ ] `backend/core/data_loader.py` — 캐시 hit/miss + 어댑터 라우팅
   - [ ] `backend/tests/test_data_loader.py` (mock 어댑터)
   - [ ] `backend/core/backtest.py` + `MaCrossStrategy`
   - [ ] `backend/tests/test_backtest.py`
   - [ ] `backend/core/ai_interpreter.py` — Groq client + 프롬프트 + 캐시
   - [ ] `backend/tests/test_ai_interpreter.py` (Mock Groq)
   - [ ] `backend/core/portfolio.py` — load_holdings_from_csv + analyze + FX 변환
   - [ ] `backend/tests/test_portfolio.py`

5. **API Boundary Layer (60분)** ✨ NEW
   - [ ] `backend/main.py` — FastAPI app + CORSMiddleware + `exception_handler(TradingToolError)` (§6.3 참조)
   - [ ] `backend/api/__init__.py` — health endpoint (`/api/health`)
   - [ ] `backend/api/schemas.py` — Pydantic 요청/응답 모델 (§4.5.2 참조)
   - [ ] `backend/api/converters.py` — dataclass → Pydantic 변환 헬퍼 (pd.Timestamp → unix ms 등)
   - [ ] `backend/api/ohlcv.py` — GET /api/ohlcv
   - [ ] `backend/api/indicators.py`, `signals.py`, `trend.py`
   - [ ] `backend/api/portfolio.py` — POST /api/portfolio
   - [ ] `backend/api/ai.py` — POST /api/ai/explain
   - [ ] `backend/api/backtest.py` — POST /api/backtest
   - [ ] `backend/api/market.py` — GET /api/market/snapshot (TopBar용, `core.market_snapshot.fetch_snapshot` 호출)
   - [ ] `backend/tests/test_api/*` — FastAPI TestClient 통합 테스트
   - [ ] OpenAPI docs 자동 생성 확인 (http://localhost:8000/docs)

6. **Backend 검증 (20분)**
   - [ ] `uvicorn backend.main:app --reload` 실행
   - [ ] curl/Postman으로 각 엔드포인트 1회 호출 검증
   - [ ] BTCUSDT, 005930 실데이터 fetch 동작 확인

#### Frontend (단계 7~9, 약 1.5시간)

7. **api.js 작성 + OpenAPI 동기화 (30분)** ✨ NEW
   - [ ] `Tradingmode/api.js` — fetch 래퍼 (§4.5.5 참조, AbortController/timeout 포함)
   - [ ] `Tradingmode/index.html`에 `<script>window.API_BASE_URL = 'http://localhost:8000'</script>` 추가 + `<script src="api.js?v=5"></script>` (data.js보다 먼저 로드)
   - [ ] 브라우저 콘솔에서 `await api.health()` → `{status:"ok"}` 확인 (백엔드 가용성)
   - [ ] **OpenAPI 동기화**: 백엔드 기동 후 `curl http://localhost:8000/openapi.json > Tradingmode/types.openapi.json` 으로 스냅샷 저장 → 프론트는 JSDoc `@typedef`로 수동 동기화 (v0.4 정책, v2에서 openapi-typescript 도입)

8. **data.js → api.js 교체 (50분)**
   - [ ] `charts.jsx`: `instrument.candles` 출처를 합성 → `await api.ohlcv()` 결과로 교체
   - [ ] `charts.jsx`: 지표는 `await api.indicators()` 결과 사용
   - [ ] `charts.jsx`: 신호 마커는 `await api.signals()`, 추세는 `await api.trend()`
   - [ ] `signals-page.jsx`: AI 해설을 `window.claude` → `await api.aiExplain()` 교체
   - [ ] `portfolio-page.jsx`: MOCK_HOLDINGS는 그대로 시연용으로 유지하되, `await api.portfolio()` 결과 표시 옵션 추가
   - [ ] `app.jsx`: TopBar 시세를 `await api.marketSnapshot()` 폴링(30초 간격, visibility 기반 일시정지 — §4.5.6 패턴)
   - [ ] DataStatusBar: 실제 fetch 상태 반영 (loading/error/rate_limit) — 매핑 표는 §6.3 참조
   - [ ] **data.js 운명**: 합성 OHLCV/지표 함수는 `Tradingmode/demo-data.js`로 rename, `?demo=1` 쿼리 파라미터 시에만 로드 (백엔드 미가용 시 데모 모드). 실제 운영 모드는 api.js만 사용.

9. **Frontend 검증 (20분)**
   - [ ] BTC/USDT 차트 + 지표 + 신호 실데이터 표시
   - [ ] 005930 동일
   - [ ] AI 해설 expander 클릭 → Groq 호출 → 결과 표시
   - [ ] 포트폴리오 페이지에서 holdings_sample.csv 업로드 → 결과 표시
   - [ ] DataStatusBar: 잘못된 심볼 입력 시 `error` 상태 + 메시지 정상 표시
   - [ ] AbortController: 종목 빠르게 전환 시 race condition 없이 마지막 요청만 반영 확인

> **예상 총 시간**: ~5.5시간 (검증·디버깅 포함 ~7시간)
> 백엔드 단계 4(Application)는 5(API) 작업과 병렬 가능 (테스트와 엔드포인트 동시 진행).

#### 정적 호스팅 (개발/프로덕션)

| 환경 | 호스팅 방식 | CORS_ORIGINS |
|------|------------|--------------|
| 개발 (v0.4) | `python -m http.server 5500 --directory Tradingmode` 또는 VS Code Live Server (5500) | `http://localhost:5500,http://127.0.0.1:5500` |
| 개발 (대안) | FastAPI `StaticFiles`로 통합 서빙: `app.mount('/', StaticFiles(directory='../Tradingmode', html=True))` | `http://localhost:8000` (single-origin) |
| 프로덕션 (v2) | Vite build → 정적 파일 → nginx/Caddy 또는 FastAPI StaticFiles | 도메인 화이트리스트 |

### 11.3 의존성 (`requirements.txt` 초안)

**Backend (`backend/requirements.txt`)**

```
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.5
pandas>=2.1
pandas-ta>=0.3.14b
python-binance>=1.0.19
pykrx>=1.0.45
finance-datareader>=0.9.50
backtesting>=0.3.3
pyarrow>=15.0
python-dotenv>=1.0
groq>=0.4
httpx>=0.26              # FastAPI TestClient 의존
# dev
pytest>=8.0
pytest-mock>=3.12
pytest-asyncio>=0.23
ruff>=0.3
black>=24.0
mypy>=1.9
```

**Frontend** — v0.4는 외부 빌드 도구 없이 CDN 사용:
- React 18.3.1 (UMD)
- React-DOM 18.3.1 (UMD)
- @babel/standalone 7.29.0
- Google Fonts (Inter, JetBrains Mono)

> **v2 전환**: `package.json` + Vite로 번들링, `lightweight-charts` 도입 검토.

---

## 12. Future Extensions (v2 / v3)

> 본 사이클에서는 인터페이스/확장 지점만 명시. 구현은 향후 별도 PDCA 사이클.

### 12.1 v2 — 포트폴리오 백테스팅 & 고급 분석

| 기능 | 추가 모듈 | 영향 |
|------|----------|------|
| 포트폴리오 백테스팅 (리밸런싱·포지션 사이징) | `core/portfolio_backtest.py` | 신규 |
| 종목 간 상관관계 매트릭스 | `core/correlation.py` | 신규 |
| 최적 비중 계산 (Markowitz) | `core/optimizer.py` | 신규 |
| 뉴스/공시 sentiment | `core/sentiment.py` + 어댑터 | 신규 |
| 실시간 알림 (Slack/Telegram) | `core/notifier.py` | 신규 |
| KR 시장 특화 지표 (외인/기관 수급, 공매도) | `core/indicators.py` 확장 | 기존 확장 |

### 12.2 v3 — 자동매매

본 사이클에서 정의한 `BrokerProtocol`을 다음과 같이 구현:

```
core/brokers/
├── base.py              # BrokerProtocol (✅ 본 사이클 정의 완료)
├── kis_adapter.py       # 한국투자증권 (v3)
├── kiwoom_adapter.py    # 키움증권 OpenAPI (v3)
└── binance_trade.py     # Binance 실주문 (v3)
```

**v3 추가 안전장치 (필수)**
- 거래액 일일 한도 환경변수 (`MAX_DAILY_TRADE_KRW`)
- 신호 발생 → 실행 사이 사용자 확인 모드 (기본값) vs 자동 실행 모드
- Dry-run 모드 (실제 주문 X, 로그만)
- Kill switch (전체 자동매매 즉시 중단)
- 주문 감사 로그 (모든 시도/성공/실패 영구 보관)

### 12.3 확장 시 본 사이클에 미치는 영향

| 변경 | 본 사이클 코드 |
|------|--------------|
| v2 추가 | 신규 모듈만 추가. 기존 core.* 변경 없음 |
| v3 추가 | `BrokerProtocol` 구현체만 추가. 기존 분석 로직 변경 없음 |
| AI 프로바이더 변경 (Groq → OpenAI 등) | `core.ai_interpreter` 어댑터 패턴으로 분리 가능 (v2) |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | 초안 작성 (Plan 기반 모듈/타입/알고리즘 설계) | 900033@interojo.com |
| 0.2 | 2026-04-29 | AI 신호 해석(Groq), 포트폴리오 분석(MVP), Broker 인터페이스(v3 placeholder) 추가. §12 Future Extensions 신설. | 900033@interojo.com |
| 0.3 | 2026-04-29 | design-validator 후속 수정: 사이드바 4페이지 다이어그램, app.py 의존 정정, FxQuote/HoldingAnalysis FX 메타데이터, errors.py를 core/types/로 이동, IndicatorConfig EMA 정정, Stochastic 제거, SignalKind/SignalAction Enum 통일, bbands std=2.0, Strategy/BrokerProtocol 위치 명시, interpret_signals_batch sync 래퍼 명시, Signal.strength v0.2=1.0 고정 + v2 공식 명세, Phase 5 N/A 추가. | 900033@interojo.com |
| 0.4 | 2026-04-30 | **아키텍처 피벗**: Streamlit → React SPA(`Tradingmode/`) + FastAPI 백엔드(`backend/`) 분리. §4.5 REST API 명세 신설(엔드포인트 9개 + Pydantic 스키마 + CORS + 에러 코드 + 프론트 fetch 패턴). §5 UI를 React 프로토타입 매핑으로 재작성. §9 Layer Structure에 API Boundary 추가. §11.1 폴더 구조 backend/ + Tradingmode/ 분리. §11.2 구현 순서를 백엔드 → API → 프론트 통합 9단계로 재편. | 900033@interojo.com |
| 0.4.1 | 2026-04-30 | design-validator 재검증(78%) 후속 수정: §5.1 React TopBar/Watchlist/Tabs 와이어프레임 재작성, §5.2 User Flow를 uvicorn+http.server 기준 재작성, §9.4 죽은 Streamlit 매핑(app.py/pages/*) 제거, §10.5 Streamlit 잔존 정리, §10.3 BACKEND_/CORS_/API_BASE_URL 추가, §6.3 사용자 메시지를 FastAPI exception_handler + 프론트 ApiError 패턴으로 재작성, §4.5.4 에러 코드 ↔ 도메인 예외 매핑 표 추가, §4.5.5 api.js에 AbortController/timeout/race 처리, §4.5.6 폴링·캐싱 정책 신설, §4.5.2 응답 Pydantic 스키마 + dataclass 변환 매핑 표, §11.2 OpenAPI 동기화·정적 호스팅·data.js 운명·core.market_snapshot 추가, §5.3 백테스팅 위치(`charts.jsx` 내 패널) 명시. Plan §4.1 DoD를 백엔드/프론트 두 명령으로 분리, Plan §6.3 폴더 구조 끝 중복 제거, Plan §7.4 Pipeline note 갱신. 목표 90%+. | 900033@interojo.com |
