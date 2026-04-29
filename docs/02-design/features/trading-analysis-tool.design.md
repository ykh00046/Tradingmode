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

> **Note**: 단일 사용자 데스크톱 분석 툴이므로 Pipeline 일부 단계는 생략. UI는 Streamlit 기본 테마 사용(브랜드 디자인 적용 안 함).

---

## 1. Overview

### 1.1 Design Goals

- **모듈성**: 데이터 소스(거래소/주식)를 어댑터 패턴으로 추상화 → 신규 소스 추가가 코어 변경 없이 가능
- **재현성**: 동일 입력에 대해 동일 신호·백테스트 결과가 나오도록 결정론적 로직 작성 (랜덤 시드 고정)
- **성능**: parquet 캐시로 동일 요청 재호출 방지, 단일 종목·1년치 분석 < 2초 (캐시 hit 기준)
- **검증가능성**: 모든 핵심 로직(지표·신호·추세)은 결정론적이며 단위 테스트 가능
- **확장성**: 백테스팅 전략을 클래스 단위로 추가 가능하도록 인터페이스 정의

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
┌──────────────────────────────────────────────────────────┐
│                Presentation (Streamlit)                  │
│  app.py  /  pages/1_차트분석.py  / 2_매매신호.py / 3_백테스팅.py│
└────────────────────────┬─────────────────────────────────┘
                         │ uses
                         ▼
┌──────────────────────────────────────────────────────────┐
│                  Application (core/)                     │
│  data_loader.py  indicators.py  signals.py               │
│  trend.py        backtest.py                             │
└──┬─────────────────────────┬─────────────────────────────┘
   │ uses                    │ uses
   ▼                         ▼
┌─────────────────────┐   ┌──────────────────────────────┐
│  Infrastructure     │   │ Domain (types/)              │
│  adapters/          │   │ schemas.py: OHLCV, Signal,   │
│   binance_adapter   │   │ TrendState, BacktestResult   │
│   krx_adapter       │   └──────────────────────────────┘
│  lib/cache.py       │
│  lib/logger.py      │
└─────────────────────┘
         │
         ▼
   ┌──────────────────────┐
   │ External APIs        │
   │ Binance / KRX (pykrx)│
   └──────────────────────┘
```

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
| `app.py` | core.data_loader, core.indicators | 메인 페이지 구성 |
| `pages/*.py` | core.* | 각 분석 페이지 |
| `core.data_loader` | core.adapters.*, lib.cache | 데이터 통합 진입점 |
| `core.indicators` | pandas-ta, pandas | 지표 계산 |
| `core.signals` | core.indicators | 신호는 지표 위에서 동작 |
| `core.trend` | core.indicators | 추세는 지표(ADX, MA) 기반 |
| `core.backtest` | backtesting.py, core.signals | 신호 입력으로 백테스트 |
| `core.adapters.binance_adapter` | python-binance | Binance Spot API |
| `core.adapters.krx_adapter` | pykrx, FinanceDataReader | KR 주식 데이터 |
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


SignalKind = Literal[
    "golden_cross",      # MA20 ↑ MA60
    "death_cross",       # MA20 ↓ MA60
    "rsi_overbought",    # RSI 70 상향 진입
    "rsi_oversold",      # RSI 30 하향 진입
    "rsi_bull_div",      # 가격 신저점 + RSI 신저점 미경신
    "rsi_bear_div",      # 가격 신고점 + RSI 신고점 미경신
    "macd_bull_cross",   # MACD ↑ Signal
    "macd_bear_cross",   # MACD ↓ Signal
]

SignalAction = Literal["buy", "sell", "neutral"]


@dataclass(frozen=True)
class Signal:
    timestamp: pd.Timestamp
    kind: SignalKind
    action: SignalAction
    price: float          # close at signal time
    strength: float       # 0.0 ~ 1.0 (선택적 점수)
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
| `core.indicators` | `add_ema(df, periods)` | EMA 컬럼 추가 |
| `core.indicators` | `add_rsi(df, period=14)` | RSI 컬럼 추가 |
| `core.indicators` | `add_macd(df, fast=12, slow=26, signal=9)` | MACD 컬럼 추가 |
| `core.indicators` | `add_bbands(df, length=20, std=2)` | 볼린저밴드 추가 |
| `core.indicators` | `add_adx(df, length=14)` | ADX 컬럼 추가 |
| `core.signals` | `detect_all(df) -> list[Signal]` | 모든 신호 종합 감지 |
| `core.signals` | `detect_ma_cross(df, short=20, long=60)` | MA 교차 신호 |
| `core.signals` | `detect_rsi_signals(df)` | RSI 과매수/과매도 |
| `core.signals` | `detect_rsi_divergence(df, lookback=20)` | RSI 다이버전스 |
| `core.signals` | `detect_macd_cross(df)` | MACD 교차 신호 |
| `core.trend` | `classify(df, adx_threshold=25) -> TrendState` | 현재 시점 추세 분류 |
| `core.trend` | `classify_series(df) -> pd.Series` | 시계열 전체 추세 분류 |
| `core.backtest` | `run(df, strategy, cash=10_000_000) -> BacktestResult` | 백테스팅 실행 |

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
    sma_periods: list[int]      # default [5, 20, 60, 120]
    ema_periods: list[int]      # default [12, 26]
    rsi_period: int             # default 14
    macd: tuple[int, int, int]  # default (12, 26, 9)
    bbands: tuple[int, float]   # default (20, 2.0)
    adx_length: int             # default 14


def compute(df: pd.DataFrame, config: IndicatorConfig | None = None) -> pd.DataFrame:
    """
    OHLCV DataFrame에 모든 지표 컬럼을 추가하여 반환.

    Returns DataFrame with additional columns:
        SMA_5, SMA_20, SMA_60, SMA_120
        EMA_12, EMA_26
        RSI_14
        MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
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

### 4.3 신호 알고리즘 의사코드

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
│  [📈 차트분석] [🎯 매매신호] [📊 백테스팅]      │
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
    ├─→ [매매신호]  → 동일 입력 → 신호 리스트 + 차트 마커
    │
    └─→ [백테스팅]  → 동일 입력 + 전략 선택 → 결과 통계 + 자산곡선
```

### 5.3 Streamlit 페이지 컴포넌트

| Page | 핵심 위젯 | core 모듈 호출 |
|------|----------|---------------|
| `app.py` | `st.title`, 안내 메시지, 사이드바 자동 생성 | 없음 |
| `pages/1_차트분석.py` | selectbox(market/symbol/interval/period), plotly Candlestick, 추세 metric | `data_loader.fetch`, `indicators.compute`, `trend.classify` |
| `pages/2_매매신호.py` | 위와 동일 입력 + signal 마커 + DataFrame 테이블 | `signals.detect_all` |
| `pages/3_백테스팅.py` | 전략 selectbox, slider(cash/commission), equity curve, trade log | `backtest.run` |

---

## 6. Error Handling

### 6.1 Error Class 정의

```python
# lib/errors.py
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
```

### 6.2 에러 처리 정책

| Error | 발생 위치 | 처리 |
|-------|----------|------|
| `DataSourceError` | adapters/* | 3회 지수 백오프 재시도 후 사용자에 메시지 표시 |
| `InvalidSymbolError` | data_loader, adapters | 즉시 `st.error()`로 표시, 입력 재요청 |
| `InsufficientDataError` | indicators | 사용자에게 기간 확장 안내 |
| `CacheError` | lib.cache | 경고 후 캐시 우회하여 직접 호출 (degraded) |
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
- [x] API 키 보호: `.env` + `python-dotenv`, `.gitignore`에 등록
- [x] 캐시 디렉토리 권한: 사용자 홈 또는 프로젝트 내, 절대 경로 검증으로 path traversal 방지
- [x] Rate Limit 준수: Binance 1200 req/min, 호출 간격 자동 throttle
- [ ] HTTPS 강제: 외부 라이브러리에서 자동 처리 (별도 작업 없음)
- [ ] 인증/인가: N/A (단일 사용자)

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
| `core/indicators.py` | Domain | `C:/X/new/core/` |
| `core/signals.py` | Domain | `C:/X/new/core/` |
| `core/trend.py` | Domain | `C:/X/new/core/` |
| `core/types/schemas.py` | Domain | `C:/X/new/core/types/` |
| `core/adapters/binance_adapter.py` | Infrastructure | `C:/X/new/core/adapters/` |
| `core/adapters/krx_adapter.py` | Infrastructure | `C:/X/new/core/adapters/` |
| `lib/cache.py` | Infrastructure | `C:/X/new/lib/` |
| `lib/logger.py` | Infrastructure | `C:/X/new/lib/` |
| `lib/errors.py` | Domain (cross-cut) | `C:/X/new/lib/` |

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
│   └── 3_백테스팅.py
├── core/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── indicators.py
│   ├── signals.py
│   ├── trend.py
│   ├── backtest.py
│   ├── types/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── adapters/
│       ├── __init__.py
│       ├── binance_adapter.py
│       └── krx_adapter.py
├── lib/
│   ├── __init__.py
│   ├── cache.py
│   ├── logger.py
│   └── errors.py
├── tests/
│   ├── __init__.py
│   ├── test_indicators.py
│   ├── test_signals.py
│   ├── test_trend.py
│   ├── test_backtest.py
│   └── test_data_loader.py
├── data/                       # parquet 캐시 (gitignore)
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 11.2 Implementation Order

> **원칙**: Domain → Infrastructure → Application → Presentation 순서. 안쪽 레이어부터 테스트 가능 단위로 빌드.

1. **Setup (10분)**
   - [ ] `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore` 작성
   - [ ] uv 또는 venv로 가상환경 생성, 의존성 설치

2. **Domain Layer (40분)**
   - [ ] `core/types/schemas.py` — 모든 dataclass/Enum 정의
   - [ ] `lib/errors.py` — 커스텀 예외 클래스
   - [ ] `core/indicators.py` — pandas-ta 래퍼, `compute()` 일괄 함수
   - [ ] `tests/test_indicators.py` — 단위 테스트 (수치 검증 포함)
   - [ ] `core/signals.py` — 4종 신호 감지 함수 + `detect_all()`
   - [ ] `tests/test_signals.py` — 합성 데이터로 신호 검증
   - [ ] `core/trend.py` — `classify()` 함수
   - [ ] `tests/test_trend.py` — 케이스별 추세 분류 검증

3. **Infrastructure Layer (40분)**
   - [ ] `lib/logger.py` — 로깅 설정
   - [ ] `lib/cache.py` — parquet load/save, 키 생성 함수
   - [ ] `core/adapters/binance_adapter.py` — `download()` 구현, Rate limit 처리
   - [ ] `core/adapters/krx_adapter.py` — pykrx + FinanceDataReader 통합

4. **Application Layer (30분)**
   - [ ] `core/data_loader.py` — 캐시 hit/miss 분기 + 어댑터 라우팅
   - [ ] `tests/test_data_loader.py` — mock 어댑터로 통합 테스트
   - [ ] `core/backtest.py` — backtesting.py 래핑, 표준화된 BacktestResult 반환
   - [ ] 기본 전략 클래스 1개 (예: `MaCrossStrategy`)
   - [ ] `tests/test_backtest.py`

5. **Presentation Layer (40분)**
   - [ ] `app.py` — 메인 페이지 (소개, 안내)
   - [ ] `pages/1_차트분석.py` — 캔들 + 지표 + 추세 표시
   - [ ] `pages/2_매매신호.py` — 신호 리스트 + 차트 마커
   - [ ] `pages/3_백테스팅.py` — 전략 선택 + 결과 시각화

6. **Validation (15분)**
   - [ ] BTC/USDT 1d로 end-to-end 시연
   - [ ] 005930 (삼성전자) 1d로 end-to-end 시연
   - [ ] README.md 작성

> **예상 총 시간**: ~3시간 (검증·디버깅 포함 ~4시간)

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
# dev
pytest>=8.0
pytest-mock>=3.12
ruff>=0.3
black>=24.0
mypy>=1.9
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-29 | 초안 작성 (Plan 기반 모듈/타입/알고리즘 설계) | 900033@interojo.com |
