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
- **재현성**: 동일 입력에 대해 동일 신호·백테스트 결과가 나오도록 결정론적 로직 작성 (LLM 호출 제외, LLM은 별도 캐시)
- **성능**: parquet 캐시로 동일 요청 재호출 방지, 단일 종목·1년치 분석 < 2초 (캐시 hit 기준)
- **검증가능성**: 모든 결정론적 로직(지표·신호·추세·포트폴리오 집계)은 단위 테스트 가능
- **확장성**: 백테스팅 전략, AI 프로바이더, broker를 모두 인터페이스/Protocol로 정의해 교체 가능
- **AI 보조성**: AI는 *보조 해설*만, 최종 매매 판단은 사용자 — 환각 방지를 위해 지표 수치 명시 + low temperature
- **포트폴리오 일괄성**: 단일 종목 분석을 그대로 N개로 확장하여 보유 자산 전체를 한 화면에서 파악

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
┌──────────────────────────────────────────────────────────────┐
│                Presentation (Streamlit)                      │
│  app.py  / pages/1_차트분석.py  / 2_매매신호.py               │
│           / 3_백테스팅.py        / 4_포트폴리오.py             │
└────────────────────────┬─────────────────────────────────────┘
                         │ uses
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  Application (core/)                         │
│  data_loader.py  backtest.py  portfolio.py  ai_interpreter.py│
└──┬───────────────┬─────────────────────────────────┬─────────┘
   │ uses          │ uses                            │ uses
   ▼               ▼                                 ▼
┌──────────────┐  ┌─────────────────────────┐  ┌───────────────────┐
│ Domain       │  │ Infrastructure          │  │ External APIs     │
│ indicators   │  │ adapters/binance, krx   │  │ Binance / pykrx   │
│ signals      │  │ brokers/base (v3 IF만)  │  │ Groq LLM API      │
│ trend        │  │ lib/cache, logger,errors│  │                   │
│ types/schemas│  │                         │  │                   │
└──────────────┘  └─────────────────────────┘  └───────────────────┘
```

**범례**: `ai_interpreter`는 Application 레이어(외부 LLM 호출 + 도메인 데이터 가공),
`portfolio`는 Application 레이어(여러 단일 종목 분석을 집계),
`brokers/base`는 자동매매 v3을 위한 Protocol/Interface 정의만 (구현 X).

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

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `app.py` | (없음) | 랜딩 페이지 — `st.title` + 안내, core 모듈 직접 호출 X |
| `pages/*.py` | core.* | 각 분석 페이지 |
| `core.data_loader` | core.adapters.*, lib.cache | 데이터 통합 진입점 |
| `core.indicators` | pandas-ta, pandas | 지표 계산 |
| `core.signals` | core.indicators | 신호는 지표 위에서 동작 |
| `core.trend` | core.indicators | 추세는 지표(ADX, MA) 기반 |
| `core.backtest` | backtesting.py, core.signals | 신호 입력으로 백테스트 |
| `core.adapters.binance_adapter` | python-binance | Binance Spot API |
| `core.adapters.krx_adapter` | pykrx, FinanceDataReader | KR 주식 데이터 |
| `core.ai_interpreter` | groq, core.types | LLM 신호 해석 |
| `core.portfolio` | core.data_loader, core.signals, core.trend, core.indicators | 보유 종목 일괄 분석 |
| `core.brokers.base` | core.types (인터페이스만) | v3 자동매매 확장 지점 (구현 X) |
| `lib.cache` | pyarrow, pathlib | parquet 캐시 (OHLCV + AI 응답 둘 다) |

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

## 5. UI/UX Design

> **방침**: Streamlit 기본 테마 사용. 별도 브랜드 디자인 적용 안 함. 기능 우선.

### 5.1 화면 구조

```
┌──────────────────────────────────────────────────┐
│ Streamlit 사이드바                               │
│  [📈 차트분석] [🎯 매매신호] [📊 백테스팅]       │
│  [💼 포트폴리오]                                  │
├──────────────────────────────────────────────────┤
│ 메인 영역 (선택 페이지에 따라 변경)              │
│                                                  │
│ ┌─ 차트분석 페이지 ────────────────────────────┐│
│ │ Market: [crypto ▼]  Symbol: [BTCUSDT ▼]      ││
│ │ Interval: [1d ▼]    Period: [1년 ▼]          ││
│ │ ─────────────────────────────────────────── ││
│ │ [현재 추세] 🟢 상승  ADX=32  MA정배열       ││
│ │ ─────────────────────────────────────────── ││
│ │ [plotly 캔들차트 + SMA/EMA 오버레이]         ││
│ │ [plotly RSI 서브차트]                        ││
│ │ [plotly MACD 서브차트]                       ││
│ └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

### 5.2 User Flow

```
앱 실행 (streamlit run app.py)
    │
    ▼
사이드바에서 페이지 선택
    │
    ├─→ [차트분석]  → Market/Symbol 선택 → 데이터 로드 → 차트+추세 표시
    │
    ├─→ [매매신호]  → 동일 입력 → 신호 리스트 + 차트 마커 + AI 해설 expander
    │
    ├─→ [백테스팅]  → 동일 입력 + 전략 선택 → 결과 통계 + 자산곡선
    │
    └─→ [포트폴리오] → CSV 업로드/수동 입력 → 보유 종목 일괄 분석 + 추세 분포
```

### 5.3 Streamlit 페이지 컴포넌트

| Page | 핵심 위젯 | core 모듈 호출 |
|------|----------|---------------|
| `app.py` | `st.title`, 안내 메시지, 사이드바 자동 생성 | 없음 |
| `pages/1_차트분석.py` | selectbox(market/symbol/interval/period), plotly Candlestick, 추세 metric | `data_loader.fetch`, `indicators.compute`, `trend.classify` |
| `pages/2_매매신호.py` | 위 입력 + signal 마커 + DataFrame 테이블 + **AI 해설 expander** (각 신호 하단에 LLM 생성 해설) | `signals.detect_all`, `ai_interpreter.interpret_signals_batch` |
| `pages/3_백테스팅.py` | 전략 selectbox, slider(cash/commission), equity curve, trade log | `backtest.run` |
| `pages/4_포트폴리오.py` | CSV 업로드 + 수동 입력 폼, 보유 종목 테이블(추세/신호/손익/비중), 추세 분포 도넛 차트, 종목 클릭 시 상세 | `portfolio.load_holdings_from_csv`, `portfolio.analyze` |

### 5.4 포트폴리오 페이지 레이아웃

```
┌────────────────────────────────────────────────────────────┐
│ 4. 포트폴리오                                              │
├────────────────────────────────────────────────────────────┤
│ [📁 CSV 업로드] [+ 수동 추가]   기준통화: [KRW ▼]          │
├────────────────────────────────────────────────────────────┤
│ 평가금액: ₩12,340,000   손익: +₩340,000 (+2.83%)          │
│ 추세 분포: 🟢 상승 3 / 🔴 하락 1 / ⚪ 횡보 2              │
├────────────────────────────────────────────────────────────┤
│ 종목   │ 추세 │ 평가금액 │ 손익(%)  │ 비중 │ 최근신호      │
│ BTCUSDT│ 🟢   │ ₩4.5M   │ +5.2%   │ 36% │ 골든크로스    │
│ 005930 │ ⚪   │ ₩3.2M   │ -1.1%   │ 26% │ -            │
│ ...                                                        │
├────────────────────────────────────────────────────────────┤
│ [선택 종목 상세 차트 - 페이지1과 동일]                     │
└────────────────────────────────────────────────────────────┘
```

### 5.5 AI 해설 UI (매매신호 페이지 내)

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

```python
# Streamlit 페이지에서:
try:
    df = data_loader.fetch(req)
except InvalidSymbolError as e:
    st.error(f"❌ 종목 코드를 확인해주세요: {e}")
    st.stop()
except DataSourceError as e:
    st.error(f"⚠️ 데이터 수집 실패: {e}")
    st.info("💡 잠시 후 다시 시도하거나 다른 거래소를 선택하세요.")
    st.stop()
```

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
| **Presentation** | Streamlit 페이지, plotly 차트 렌더 | `app.py`, `pages/` |
| **Application** | 분석 오케스트레이션, 비즈니스 로직 | `core/data_loader.py`, `core/backtest.py` |
| **Domain** | 순수 도메인 함수, 타입 정의 | `core/indicators.py`, `core/signals.py`, `core/trend.py`, `core/types/schemas.py` |
| **Infrastructure** | 외부 API, 캐시, 로깅 | `core/adapters/`, `lib/cache.py`, `lib/logger.py` |

### 9.2 Dependency Rules

```
Presentation → Application → Domain ← Infrastructure
                    │
                    └→ Infrastructure
```

- Streamlit 페이지는 core/* 만 import (lib/* 직접 import 금지)
- core.indicators / core.signals / core.trend는 외부 의존성 없음 (pandas-ta는 Domain에 허용 — pandas 확장)
- core.adapters는 core.types만 import 가능

### 9.3 File Import Rules

| From | Can Import | Cannot Import |
|------|-----------|---------------|
| `pages/*` | `core.*` | `lib.*` 직접 |
| `core.data_loader` (Application) | `core.adapters.*`, `core.types.*`, `lib.cache` | `pages.*` |
| `core.indicators/signals/trend` (Domain) | `pandas`, `pandas-ta`, `core.types.*` | `core.adapters.*`, `lib.*`, `pages.*` |
| `core.adapters.*` (Infra) | `core.types.*`, 외부 라이브러리 | `core.indicators`, `pages.*` |

### 9.4 모듈별 레이어 매핑

| Module | Layer | Path |
|--------|-------|------|
| `app.py` | Presentation | `C:/X/new/app.py` |
| `pages/1_차트분석.py` | Presentation | `C:/X/new/pages/` |
| `pages/2_매매신호.py` | Presentation | `C:/X/new/pages/` |
| `pages/3_백테스팅.py` | Presentation | `C:/X/new/pages/` |
| `core/data_loader.py` | Application | `C:/X/new/core/` |
| `core/backtest.py` | Application | `C:/X/new/core/` |
| `core/portfolio.py` | Application | `C:/X/new/core/` |
| `core/ai_interpreter.py` | Application | `C:/X/new/core/` |
| `core/indicators.py` | Domain | `C:/X/new/core/` |
| `core/signals.py` | Domain | `C:/X/new/core/` |
| `core/trend.py` | Domain | `C:/X/new/core/` |
| `core/types/schemas.py` | Domain | `C:/X/new/core/types/` |
| `core/adapters/binance_adapter.py` | Infrastructure | `C:/X/new/core/adapters/` |
| `core/adapters/krx_adapter.py` | Infrastructure | `C:/X/new/core/adapters/` |
| `core/brokers/base.py` | Infrastructure (인터페이스만) | `C:/X/new/core/brokers/` |
| `lib/cache.py` | Infrastructure | `C:/X/new/lib/` |
| `lib/logger.py` | Infrastructure | `C:/X/new/lib/` |
| `core/types/errors.py` | Domain (cross-cut, pages도 직접 import 허용) | `C:/X/new/core/types/` |
| `pages/4_포트폴리오.py` | Presentation | `C:/X/new/pages/` |

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

| Prefix | Purpose | Example |
|--------|---------|---------|
| `BINANCE_` | Binance 인증 (선택) | `BINANCE_API_KEY`, `BINANCE_API_SECRET` |
| `GROQ_` | Groq API 키 | `GROQ_API_KEY`, `GROQ_MODEL=llama-3.3-70b-versatile` |
| `CACHE_` | 캐시 설정 | `CACHE_DIR=./data` |
| `LOG_` | 로깅 설정 | `LOG_LEVEL=INFO` |

`.env` 파일 사용, `python-dotenv`로 로드, `.gitignore`에 등록.

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
| Component naming | snake_case 모듈, PascalCase 클래스 (예: `BinanceAdapter`) |
| File organization | core/lib/pages 3계층 분리 |
| State management | Streamlit `st.session_state` 최소 사용, 가능하면 stateless |
| Error handling | `lib.errors` 커스텀 예외 + Streamlit `st.error()` 사용자 메시지 |
| Type hints | 모든 public 함수 시그니처 필수 |

---

## 11. Implementation Guide

### 11.1 File Structure (실제 생성 대상)

```
C:/X/new/
├── app.py
├── pages/
│   ├── 1_차트분석.py
│   ├── 2_매매신호.py
│   ├── 3_백테스팅.py
│   └── 4_포트폴리오.py
├── core/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── indicators.py
│   ├── signals.py
│   ├── trend.py
│   ├── backtest.py
│   ├── ai_interpreter.py       # ✨ Groq LLM 신호 해석
│   ├── portfolio.py            # ✨ 포트폴리오 일괄 분석
│   ├── types/
│   │   ├── __init__.py
│   │   ├── schemas.py          # dataclass/Enum/Protocol
│   │   └── errors.py           # 커스텀 예외 (Domain cross-cut)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── binance_adapter.py
│   │   └── krx_adapter.py
│   └── brokers/                # ✨ v3 placeholder
│       ├── __init__.py
│       └── base.py             # BrokerProtocol (인터페이스만)
├── lib/
│   ├── __init__.py
│   ├── cache.py                # OHLCV + AI 응답 캐시
│   └── logger.py
├── tests/
│   ├── __init__.py
│   ├── test_indicators.py
│   ├── test_signals.py
│   ├── test_trend.py
│   ├── test_backtest.py
│   ├── test_data_loader.py
│   ├── test_ai_interpreter.py  # ✨ Mock Groq 클라이언트
│   └── test_portfolio.py       # ✨
├── data/                       # parquet 캐시 (gitignore)
├── examples/
│   └── holdings_sample.csv     # ✨ 포트폴리오 입력 샘플
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 11.2 Implementation Order

> **원칙**: Domain → Infrastructure → Application → Presentation 순서. 안쪽 레이어부터 테스트 가능 단위로 빌드.
> AI/포트폴리오/broker는 단일 종목 분석이 동작한 후 추가하여 의존성 사이클 방지.

1. **Setup (10분)**
   - [ ] `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore` 작성
   - [ ] uv 또는 venv로 가상환경 생성, 의존성 설치

2. **Domain Layer (50분)**
   - [ ] `core/types/schemas.py` — 모든 dataclass/Enum/Protocol 정의 (Holding, Portfolio, AICommentary, BrokerProtocol, Strategy 포함)
   - [ ] `core/types/errors.py` — 커스텀 예외 (AIServiceError, PortfolioError 포함)
   - [ ] `core/indicators.py` — pandas-ta 래퍼, `compute()` 일괄 함수
   - [ ] `tests/test_indicators.py`
   - [ ] `core/signals.py` — 4종 신호 감지 + `detect_all()`
   - [ ] `tests/test_signals.py`
   - [ ] `core/trend.py` — `classify()`
   - [ ] `tests/test_trend.py`

3. **Infrastructure Layer (50분)**
   - [ ] `lib/logger.py`
   - [ ] `lib/cache.py` — OHLCV용 parquet + AI 응답용 JSON 캐시 (둘 다)
   - [ ] `core/adapters/binance_adapter.py`
   - [ ] `core/adapters/krx_adapter.py`
   - [ ] `core/brokers/base.py` — `BrokerProtocol` Protocol 정의 (구현 X)

4. **Application Layer — 단일 종목 (40분)**
   - [ ] `core/data_loader.py` — 캐시 hit/miss + 어댑터 라우팅
   - [ ] `tests/test_data_loader.py` (mock 어댑터)
   - [ ] `core/backtest.py` + `MaCrossStrategy`
   - [ ] `tests/test_backtest.py`

5. **Application Layer — AI 해석 (30분)** ✨
   - [ ] `core/ai_interpreter.py` — Groq client + 프롬프트 + 캐시 + 면책
   - [ ] `tests/test_ai_interpreter.py` — Mock Groq 클라이언트로 결정론적 검증
   - [ ] 환경변수 미설정 시 graceful skip (앱 동작은 유지)

6. **Application Layer — 포트폴리오 (40분)** ✨
   - [ ] `core/portfolio.py` — `load_holdings_from_csv`, `analyze`, 환율 변환
   - [ ] `examples/holdings_sample.csv` — 데모용 샘플
   - [ ] `tests/test_portfolio.py`

7. **Presentation Layer (50분)**
   - [ ] `app.py` — 메인 + 안내
   - [ ] `pages/1_차트분석.py`
   - [ ] `pages/2_매매신호.py` (AI 해설 expander 포함 — 단계 5 완료 후)
   - [ ] `pages/3_백테스팅.py`
   - [ ] `pages/4_포트폴리오.py` ✨ (단계 6 완료 후)

8. **Validation (20분)**
   - [ ] BTC/USDT 1d 시연 (지표 + 신호 + AI 해설)
   - [ ] 005930 1d 시연
   - [ ] 샘플 CSV로 포트폴리오 페이지 시연
   - [ ] README.md 작성 (Groq API 키 발급 안내 포함)

> **예상 총 시간**: ~5시간 (검증·디버깅 포함 ~6시간)
> 단계 5(AI)와 6(포트폴리오)은 독립적이므로 둘 중 하나 먼저 진행 가능.

### 11.3 의존성 (`requirements.txt` 초안)

```
streamlit>=1.30
pandas>=2.1
pandas-ta>=0.3.14b
plotly>=5.18
python-binance>=1.0.19
pykrx>=1.0.45
finance-datareader>=0.9.50
backtesting>=0.3.3
pyarrow>=15.0
python-dotenv>=1.0
groq>=0.4              # ✨ AI 신호 해석
# dev
pytest>=8.0
pytest-mock>=3.12
pytest-asyncio>=0.23   # ✨ ai_interpreter 비동기 테스트
ruff>=0.3
black>=24.0
mypy>=1.9
```

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
