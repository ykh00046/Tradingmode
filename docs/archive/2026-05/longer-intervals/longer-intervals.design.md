---
template: design
version: 0.1
feature: longer-intervals
date: 2026-05-05
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.8.0
---

# longer-intervals Design Document

> **Summary**: Plan v1.0 의 10 FRs를 백엔드 enum/literal/어댑터/테스트 + 프론트엔드 상수/CSS 단위까지 구체화. Crypto 는 Binance `_INTERVAL_MAP` 두 줄, KR 은 일봉 fetch 후 pandas `resample('W-FRI'/'ME').agg()` 집계. Cache 경로는 기존 `{market}/{symbol}/{interval}/{start}_{end}.parquet` 패턴이 자동 분리. Frontend 4번째 그룹 `'longer'` 추가, 한국어 라벨 `주/월`.
>
> **Project**: trading-analysis-tool · **Version**: 0.8.0 · **Date**: 2026-05-05  
> **Builds on**: v0.4 base + v0.5 strategy coach + v0.6 RPB + v0.7 UX

---

## 1. Overview

### 1.1 Goal

v1 MVP 스코프(분~일봉)에서 빠진 장기 시점(주/월봉) 보강. 양 시장(Crypto/KR) 처리 방식이 다르나 외부 인터페이스(`/api/{ohlcv,indicators,signals,backtest}` query `interval`)는 단일.

### 1.2 Design Principles

1. **Endpoint stable** — 신규 endpoint 0건. 기존 query parameter `interval` 만 enum 확장.
2. **Cache-friendly** — `lib/cache.py:60` 의 경로 패턴 `{market}/{symbol}/{interval}/...` 가 자동 분리. 변경 0건.
3. **Frontend re-use v0.7** — INTERVAL_LABELS / INTERVAL_GROUP_ORDER / .tf-group--* CSS / refetch 흐름 그대로 확장.
4. **Backend test 회귀 0** — 기존 147 테스트 무영향. 신규 4건 추가 (총 151).
5. **Korean-first labels** — `1w` → `주`, `1M` → `월` (v0.7 컨벤션 일치).

---

## 2. Architecture

### 2.1 변경 영역 매핑

```
backend/
├── core/
│   ├── types/
│   │   └── schemas.py                  (line 26 Interval enum: +W1, +MN1)
│   └── adapters/
│       ├── binance_adapter.py          (line 25-32 _INTERVAL_MAP: +2 entries)
│       └── krx_adapter.py              (line 36-41 _ensure_daily 제거 또는 분기,
│                                        + _resample_ohlcv() helper,
│                                        line 79-109 download() 분기)
├── api/
│   └── schemas.py                      (line 36 IntervalLiteral: +"1w", "1M")
└── tests/
    ├── test_data_loader.py             (확장: KR resample 테스트 4건)
    └── conftest.py                     (변경 없음 — 기존 fixture 재사용)

Tradingmode/
├── app.jsx                             (line 237-244 INTERVAL_LABELS: +2,
│                                        line 245 INTERVAL_GROUP_ORDER: +'longer')
├── loader.js                           (line 188-195 LOOKBACK_BY_INTERVAL: +2)
├── styles.css                          (line 397-399 .tf-group--*: +.tf-group--longer 1줄)
└── index.html                          (캐시 버스트 v11 → v12)
```

### 2.2 Component / Function 변경 요약

| 영역 | 위치 (verified) | 변경 |
|---|---|---|
| `Interval` enum | `core/types/schemas.py:26-32` | 멤버 +2: `W1 = "1w"`, `MN1 = "1M"` (월봉 = MN1, M1 분봉과 명시 구분) |
| `IntervalLiteral` | `api/schemas.py:36` | `Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]` |
| `binance_adapter._INTERVAL_MAP` | `core/adapters/binance_adapter.py:25-32` | +2 entries: `"1w": "1w", "1M": "1M"` |
| `krx_adapter._ensure_daily` | `core/adapters/krx_adapter.py:36-41` | 삭제 또는 `_ensure_supported_interval` 로 변경 (1d/1w/1M 허용) |
| `krx_adapter._resample_ohlcv` | NEW (krx_adapter.py 내부 private) | 일봉 → 주/월봉 집계. `agg(open=first, high=max, low=min, close=last, volume=sum)` |
| `krx_adapter.download` | `core/adapters/krx_adapter.py:79-109` | interval 분기 — 1d 면 기존 흐름, 1w/1M 면 일봉 lookback 자동 확장 후 resample |
| `data_loader.fetch` | `core/data_loader.py:25-60` | **변경 없음** — 캐시 키에 interval 포함, 어댑터 위임 |
| `cache.ohlcv_cache_path` | `lib/cache.py:60` | **변경 없음** — `{market}/{symbol}/{interval}/...` 자동 분리 |
| Frontend `INTERVAL_LABELS` | `app.jsx:237` | +2: `'1w': { label: '주', group: 'longer' }`, `'1M': { label: '월', group: 'longer' }` |
| Frontend `INTERVAL_GROUP_ORDER` | `app.jsx:245` | `['minute', 'hour', 'day', 'longer']` |
| Frontend `LOOKBACK_BY_INTERVAL` | `loader.js:188` | +2: `'1w': 730`, `'1M': 3650` |
| CSS `.tf-group--longer` | `styles.css:397` 영역 | 신규 1줄 — `background: oklch(0.16 0.005 240 / 0.6)` (day 보다 약간 더 어둡게, "장기" 강조) |

---

## 3. Data Model

### 3.1 Backend `Interval` enum 확장

```python
# core/types/schemas.py (현재 → 확장)
class Interval(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"      # ✨ NEW: 주봉
    MN1 = "1M"     # ✨ NEW: 월봉 (MoNth — M1 와 구분)
```

**명명 규칙**: 분봉은 `M1` (Minute), 월봉은 `MN1` (MoNth). 시간 단위 약어가 일관성 있게 분리됨.

### 3.2 Backend `IntervalLiteral` Pydantic literal

```python
# api/schemas.py:36 (현재 → 확장)
IntervalLiteral = Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
```

이 type 은 6 위치에서 사용됨 (line 36, 51, 64, 122, 212, 296). 단일 정의 한 곳만 수정하면 모든 endpoint 가 자동 반영.

### 3.3 Binance `_INTERVAL_MAP` 확장

```python
# core/adapters/binance_adapter.py:25-32 (현재 → 확장)
_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",      # ✨ NEW
    "1M": "1M",      # ✨ NEW
}
```

ccxt python-binance `get_historical_klines()` 가 `1w`/`1M` 네이티브 지원 — 호출 시 그대로 전달.

### 3.4 Frontend `INTERVAL_LABELS` 확장

```js
// Tradingmode/app.jsx:237 (현재 → 확장)
const INTERVAL_LABELS = {
  '1m':  { label: '1분',   group: 'minute' },
  '5m':  { label: '5분',   group: 'minute' },
  '15m': { label: '15분',  group: 'minute' },
  '1h':  { label: '1시간', group: 'hour'   },
  '4h':  { label: '4시간', group: 'hour'   },
  '1d':  { label: '일',    group: 'day'    },
  '1w':  { label: '주',    group: 'longer' },   // ✨ NEW
  '1M':  { label: '월',    group: 'longer' },   // ✨ NEW
};
const INTERVAL_GROUP_ORDER = ['minute', 'hour', 'day', 'longer'];   // ← +1
```

**JS Object key 케이스 검증** — `INTERVAL_LABELS['1m'] !== INTERVAL_LABELS['1M']` (case-sensitive). `Object.keys(INTERVAL_LABELS).length === 8`. 자동완성 시 IDE 가 헷갈리지 않도록 위 코드에 인라인 주석 (`// 분 / 월`) 권장.

### 3.5 Frontend `LOOKBACK_BY_INTERVAL` 확장

```js
// Tradingmode/loader.js:188-195 (현재 → 확장)
var LOOKBACK_BY_INTERVAL = {
  '1m':  3,         // ~4320 candles
  '5m':  14,        // ~4032
  '15m': 30,        // ~2880
  '1h':  60,        // ~1440
  '4h':  180,       // ~1080
  '1d':  365,       // ~365
  '1w':  730,       // ~104 weeks (~2년)        ← ✨ NEW
  '1M':  3650,      // ~120 months (~10년)      ← ✨ NEW
};
```

### 3.6 Cache 경로 (변경 없음, 자동 분리)

```
data/
├── crypto/BTCUSDT/1d/2025-05-04_2026-05-04.parquet   (기존)
├── crypto/BTCUSDT/1w/2024-05-04_2026-05-04.parquet   ✨ 자동 신규
├── crypto/BTCUSDT/1M/2016-05-04_2026-05-04.parquet   ✨ 자동 신규
├── kr_stock/005930/1d/...                            (기존)
├── kr_stock/005930/1w/...                            ✨ 자동 신규
└── kr_stock/005930/1M/...                            ✨ 자동 신규
```

`lib/cache.py:60` `_safe_resolve(f"{market}/{symbol}/{interval}/{start}_{end}.parquet")` 가 interval 포함 경로 생성 — 변경 0건.

**캐시 의미 (중요)**: parquet 은 **resample 결과 (주/월봉)** 만 캐시함. KR 의 1w/1M 요청 처리 흐름은:
1. `data_loader.fetch(req=FetchRequest(interval=W1, range))` → 캐시 미스
2. `krx_adapter.download(symbol, '1w', range)` 호출 → 내부에서 daily +70d buffer 로 pykrx fetch (이 daily 결과는 **별도로 캐시되지 않음**)
3. `_resample_ohlcv(daily, 'W-FRI')` 적용
4. `data_loader.fetch` 가 resampled DataFrame 을 `data/kr_stock/<sym>/1w/<start>_<end>.parquet` 에 저장
5. 동일 (sym, '1w', start, end) 재요청 시 parquet 적중

따라서 daily fetch 는 매 cache miss 마다 재실행됨. 만약 동일 사용자가 005930 의 1d / 1w / 1M 모두 보면 pykrx daily fetch 가 3번 일어남 (각 인터벌별 별도 buffer 적용된 daily). pykrx rate limit 우려 시 v0.9 에서 별도 daily-cache 레이어 도입 검토.

---

## 4. KRX Resample 명세 (핵심)

### 4.1 함수 시그니처

```python
# core/adapters/krx_adapter.py 신규 private helper
def _resample_ohlcv(daily_df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """일봉 OHLCV DataFrame 을 주/월봉으로 집계.

    Parameters
    ----------
    daily_df : pd.DataFrame
        DatetimeIndex + columns ['open', 'high', 'low', 'close', 'volume'].
    freq : str
        pandas resample frequency string. 'W-FRI' (한국 주식 주봉, 금요일 마감)
        또는 'ME' (Month-End, pandas 2.x).

    Returns
    -------
    pd.DataFrame
        Resampled DataFrame. open/high/low/close/volume 모두 단일 행.
        빈 주/월(데이터 없음) 은 dropna() 로 제거.
    """
    if daily_df.empty:
        return daily_df

    agg = daily_df.resample(freq).agg({
        'open':   'first',
        'high':   'max',
        'low':    'min',
        'close':  'last',
        'volume': 'sum',
    })
    # 데이터 없는 주/월은 NaN-only row 가 됨 → 제거
    return agg.dropna(subset=['close'])
```

### 4.2 `download()` 분기 로직

```python
# core/adapters/krx_adapter.py:79-109 → 확장

_INTERVAL_TO_FREQ = {
    "1w": "W-FRI",   # 한국 주식 거래일 종료 = 금요일
    "1M": "ME",      # pandas 2.x Month-End (구 'M' deprecated)
}
_SUPPORTED_INTERVALS = {"1d", "1w", "1M"}


def _ensure_supported_interval(interval: str) -> None:
    if interval not in _SUPPORTED_INTERVALS:
        raise DataSourceError(
            f"KR stock adapter does not support '{interval}' (supported: {sorted(_SUPPORTED_INTERVALS)})",
            details={"interval": interval},
        )


def download(symbol, interval, start, end):
    _ensure_supported_interval(interval)
    log.info("krx fetch: %s %s %s..%s", symbol, interval, start, end)

    # 주/월봉이면 일봉 lookback 을 자동 확장하여 충분한 raw 데이터 확보
    if interval == "1d":
        daily_start = start
    else:
        # 주봉 730일 → 일봉 800일치 (주말 buffer), 월봉 3650 → 4000일
        buffer_days = {"1w": 70, "1M": 350}[interval]
        daily_start = start - pd.Timedelta(days=buffer_days)

    try:
        df = _try_pykrx(symbol, daily_start, end)
        if df.empty:
            df = _try_fdr(symbol, daily_start, end)
        if df.empty:
            raise InvalidSymbolError(f"no data for KR symbol: {symbol}")

        if interval == "1d":
            return df

        resampled = _resample_ohlcv(df, _INTERVAL_TO_FREQ[interval])
        # 데이터 부족 (resample 결과 0 행) → 명확한 에러
        if resampled.empty:
            raise DataSourceError(
                f"insufficient daily data for {interval} resample: {symbol} ({len(df)} daily rows)",
                details={"symbol": symbol, "interval": interval, "daily_rows": len(df)},
            )
        # start 이후만 반환 (buffer 영역 제거)
        return resampled[resampled.index >= start]

    except (InvalidSymbolError, DataSourceError):
        raise
    except Exception as e:
        raise DataSourceError(
            f"KR adapter failed: {e}",
            details={"symbol": symbol, "type": type(e).__name__, "interval": interval},
        ) from e
```

**Buffer 일수 산정**:
- 주봉 70일 = 약 50 거래일 = 10주 buffer (주말/공휴일 포함 안전)
- 월봉 350일 = 약 11 개월 buffer (재시작 자르기 충분)

### 4.3 한국 주식 주봉 마감 요일 결정

| 옵션 | freq | 한국 거래소 (KRX) 호환성 |
|---|---|---|
| `'W'` (default = SUN) | 일요일 마감 | 거래 없는 날 마감 → 의미 없음 |
| `'W-FRI'` | 금요일 마감 | ✅ KRX 정규장 종료일 일치 |
| `'W-MON'` | 월요일 마감 | 다음 주에 걸침, KR 컨벤션 X |

선택: **`W-FRI`** — 한국 주식 거래일 종료가 금요일이라 정합.

### 4.4 월봉 마감 시점 결정

| 옵션 | freq | pandas 2.x 호환 | ccxt 1M 시작 시점 |
|---|---|---|---|
| `'M'` | 월말 | ⚠ deprecated → FutureWarning | 매월 1일 0시 UTC |
| `'ME'` | Month-End | ✅ 권장 | 매월 1일 0시 UTC |
| `'MS'` | Month-Start | ✅ | 매월 1일 0시 UTC |

선택: **`ME`** — pandas 2.x 권장 + ccxt 의 1M 캔들 종가 시점과 일치 (월의 마지막 거래일 종가).

---

## 5. API / Schema Specifications

### 5.1 모든 endpoint 자동 반영

`IntervalLiteral` 단일 정의 (`api/schemas.py:36`) 가 두 군데서 사용됨:

**(a) Pydantic body model 필드 5건** (`api/schemas.py` 내부):
- line 51 `OHLCVResponse.interval`
- line 64 `IndicatorsResponse.interval`
- line 122 `AIExplainRequest.interval`
- line 212 `BacktestRequest.interval`
- line 296 `StrategyBacktestRequest.interval`

**(b) FastAPI Query annotation 5건** (각 라우터 파일):
- `api/indicators.py:18` `Query("1d")`
- `api/ohlcv.py:19` `Query("1d")`
- `api/signals.py:18` `Query("1d")`
- `api/strategy.py:168` `Query("1d")`
- `api/trend.py:22` `Query("1d")`

→ `IntervalLiteral` 한 곳만 수정 → 위 10 위치 모두 자동으로 `1w`/`1M` 받음 (Pydantic body validation + FastAPI query validation 양쪽).

### 5.2 Endpoint 동작 명세 (변경 없음)

```
GET /api/ohlcv?market=crypto&symbol=BTCUSDT&interval=1w&start=2024-01-01&end=2026-01-01
GET /api/indicators?...&interval=1w&...
GET /api/signals?...&interval=1M&...
POST /api/backtest    body.interval = "1M"
POST /api/strategy-backtest  body.interval = "1w"
```

응답 시그니처 무변경. candles 배열의 t 필드는 주봉 = 금요일 timestamp, 월봉 = 월말 timestamp (UTC).

---

## 6. Frontend UI

### 6.1 인터벌 헤더 (현재 → 변경)

```
현재 (v0.7):
[1분] [5분] [15분] | [1시간] [4시간] | [일]

v0.8 (target):
[1분] [5분] [15분] | [1시간] [4시간] | [일] | [주] [월]
                                         ↑    ↑
                                        기존  신규 'longer' 그룹 (구분선 1개 추가)
```

CSS `.tf-group--longer` 배경:
```css
.tf-group--longer { background: oklch(0.16 0.005 240 / 0.6); }
```

day(`var(--surface)` = `oklch(0.20 0.005 240)`) 보다 약간 어둡게 → "장기 시점" 시각 강조.

### 6.2 Refetch 흐름 (v0.7 그대로 재사용)

`changeInterval('1w')` 클릭 시:
1. `setIntervalTf('1w')` → 시각 즉시 active 표시
2. `dataState = loading` 표시
3. `window.loader.loadInstrument(meta, { interval: '1w' })` 호출
4. `LOOKBACK_BY_INTERVAL['1w'] = 730` 자동 적용 → 730일치 백엔드 요청
5. backend 가 binance(crypto) or krx_adapter+resample(KR) 분기 처리
6. parquet 캐시 적중 시 < 100ms, 첫 fetch 시 1-3초
7. `setLocalInstrument(fresh)` + `setView` 리셋
8. `dataState = ok '캐시 적중'` 또는 error 시 한국어 에러

→ `intervalReqRef` race-guard (`app.jsx:312` `useRef(0)`, `:340` `++intervalReqRef.current` 증가, `:344/:350` 비교 검사 — 라인 번호는 v0.8 cleanup 후 기준) 도 그대로 동작 — 신규 1w/1M 인터벌이라고 별도 처리 불필요. 사용자가 1w → 1M → 1w 빠르게 클릭 시 stale 응답 무시.

### 6.3 Watchlist mini-spark (변경 없음)

`MiniSpark` (`charts.jsx:491`) 는 일봉 30봉 표시 — 주/월봉 추가해도 watchlist 미니 차트는 일봉 그대로 (Out of Scope §2.2).

---

## 7. Error Handling

| 시나리오 | 처리 | UI 노출 |
|---|---|---|
| KR 신규 상장 종목 (일봉 < 7일) → 주봉 0개 | `DataSourceError("insufficient daily data for 1w resample: {symbol} ({N} daily rows)")` | `dataState=error`, 메시지: "1w 데이터 로드 실패" + 콘솔 상세 |
| KR 종목 + 1M, 일봉 < 30일 | 동일 패턴, "insufficient daily data for 1M resample" | 동일 |
| Binance 의 1M 캔들이 거래 시작 전 → 빈 응답 | InvalidSymbolError 가 아닌 그냥 빈 candles[] (resample N/A) | dataState=ok 이지만 차트 빈 상태, 사용자가 1d 로 fallback |
| pykrx fetch 실패 → fdr fallback 도 실패 | 기존 InvalidSymbolError 흐름 유지 | 변경 없음 |
| pykrx rate limit (10년치 일봉 fetch) | 캐시 적중 후 resample 만 → 두 번째부터 빠름. 첫 호출은 timeout 가능 → frontend 30s timeout (기존) | `dataState=error`, "TIMEOUT" |
| `interval='1w'` 인 종목을 타 종목으로 전환 (Watchlist 클릭) | 기존 `useEffect([instrumentProp.meta.symbol])` 가 `setIntervalTf('1d')` 리셋 → 새 종목은 일봉으로 시작 | 정상 |

---

## 8. Test Plan

### 8.1 Backend pytest 신규 4건 (모두 `tests/test_data_loader.py` 추가)

| # | Test | 검증 |
|---|---|---|
| T-B1 | `test_kr_resample_weekly_ohlcv_correct` | 일봉 14일 mock → resample('W-FRI') → 결과 2-3 주봉, OHLCV 정확 (open=Mon, high=주중max, close=Fri) |
| T-B2 | `test_kr_resample_monthly_ohlcv_correct` | 일봉 60일 mock → resample('ME') → 결과 2-3 월봉, OHLCV 정확 |
| T-B3 | `test_kr_insufficient_data_raises_data_source_error` | 일봉 3일 mock → 1w resample → `DataSourceError("insufficient daily data...")` raise |
| T-B4 | `test_binance_weekly_monthly_routed_natively` | mocker 로 binance_adapter.download 검증 — `interval='1w'` 또는 `'1M'` 일 때 `_INTERVAL_MAP` 통과, KR 어댑터 안 불림 |

### 8.2 Backend 회귀

- `pytest backend/tests/test_data_loader.py` → 기존 4 + 신규 5 = **9 PASSED** (v0.8 cleanup 후 T-B3 분리로 5건)
- 핵심 검증 기준: "기존 PASSED 보존 + 신규 T-B1~T-B4 4건 PASSED" (절대 카운트는 환경 의존)
- 환경 caveat: `backtesting` 모듈 (v0.4 strategy/backtest 테스트 의존성) 미설치 시 10 pre-existing failures 발생 가능. **v0.8 변경과 무관**.
- 기존 `test_data_loader.py` 의 `test_routes_kr_market_to_krx_adapter` 는 D1 사용 — 무영향
- `test_invalid_symbol_does_not_create_cache_entry` 도 무영향

### 8.3 Frontend Manual / Playwright (T-F1 ~ T-F5)

| # | 시나리오 | 검증 |
|---|---|---|
| T-F1 | BTC/USDT, 헤더에서 `주` 클릭 | dataState=loading → ok, 차트 약 100주 봉 표시, x축 timestamp 가 7일 단위 |
| T-F2 | BTC/USDT, `월` 클릭 | 차트 약 120월 봉 표시, x축 timestamp 가 ~30일 단위 |
| T-F3 | 005930.KS (삼성전자), `주` 클릭 | resample 결과 표시, RSI/MA 도 주봉 기준 재계산 |
| T-F4 | 인터벌 헤더 시각 | `1분 5분 15분 \| 1시간 4시간 \| 일 \| 주 월` — divider 3개, 그룹 4개 |
| T-F5 | 빠른 연속 클릭 (1w → 1M → 1w) | `intervalReqRef` race-guard 로 stale 응답 무시, 마지막 클릭만 적용 |

### 8.4 통합

- v0.7 모든 기능 정상 (`★`/collapsible/ws-right toggle/signals limit 무영향)
- localStorage 키 4개 그대로 (신규 키 0건)

---

## 9. Clean Architecture / Convention

### 9.1 계층 구조 (변경 영역만)

```
[Browser DOM]
  → React ChartPage.changeInterval('1w')
  → window.loader.loadInstrument(meta, { interval: '1w' })
  → window.api.indicators({ interval: '1w', ... })
  → fetch /api/indicators?interval=1w
  → FastAPI router (api/indicators.py)
  → core.data_loader.fetch(FetchRequest(interval=Interval.W1, ...))
  → cache.ohlcv_cache_path → check parquet
  → [miss] → core.adapters.krx_adapter.download(symbol, '1w', ...) [KR]
                        OR binance_adapter.download(symbol, '1w', ...) [crypto]
  → KR: _try_pykrx (일봉 fetch) → _resample_ohlcv(df, 'W-FRI')
  → return DataFrame → cache.save_ohlcv → return to API → JSON response
```

### 9.2 Naming

| Category | Convention | 예 |
|---|---|---|
| Backend Interval enum 멤버 | 시간 단위 약어 + 숫자 | `M1, M5, M15, H1, H4, D1, W1, MN1` (월봉은 MN 으로 분봉 M 과 구분) |
| pandas resample freq | string 그대로 | `'W-FRI'`, `'ME'` |
| Backend private helper | underscore prefix | `_resample_ohlcv`, `_INTERVAL_TO_FREQ` |
| Frontend group ID | 단일 단어 | `minute`, `hour`, `day`, `longer` |
| Frontend interval key | 백엔드 string 일치 | `'1m', ..., '1w', '1M'` |

### 9.3 Coding Convention

- pandas 2.x freq: `'ME'` 권장 (구 `'M'` deprecated, FutureWarning 발생)
- DataFrame DatetimeIndex 보존 (resample 후도 인덱스 유지)
- `dropna(subset=['close'])` 로 빈 주/월 제거
- `_INTERVAL_TO_FREQ` dict 는 module-level 상수 (테스트 가능)

---

## 10. Implementation Guide

### 10.1 Phase A — Backend enum + IntervalLiteral + Binance (30분)

1. `core/types/schemas.py:26` `Interval` enum 에 `W1 = "1w"`, `MN1 = "1M"` 추가
2. `api/schemas.py:36` `IntervalLiteral` Literal 에 `"1w", "1M"` 추가
3. `core/adapters/binance_adapter.py:25-32` `_INTERVAL_MAP` 에 2 entries 추가
4. pytest 실행 — 기존 147 PASSED 확인 (이 단계까지는 KR 호출 시 에러 — 정상)

### 10.2 Phase B — KR resample + pytest (1.5h)

1. `core/adapters/krx_adapter.py` 에 `_INTERVAL_TO_FREQ` + `_SUPPORTED_INTERVALS` + `_ensure_supported_interval()` + `_resample_ohlcv()` 추가
2. `download()` 함수 분기 로직 적용 (interval==1d 면 기존, 1w/1M 면 lookback 확장 + resample)
3. `_ensure_daily()` 함수 제거 (또는 `_ensure_supported_interval()` 로 대체된 상태)
4. `tests/test_data_loader.py` 에 T-B1~T-B4 4건 추가:
   - `_make_request(market=KR_STOCK, interval=Interval.W1)` 같은 helper 활용
   - mocker 로 `_try_pykrx` 패치하여 일봉 14/60/3 row 케이스 테스트
5. `pytest backend/tests/` → 151 PASSED 확인

### 10.3 Phase C — Frontend (45분)

1. `Tradingmode/app.jsx:237-244` `INTERVAL_LABELS` 에 `'1w'/'1M'` 2 entries
2. `Tradingmode/app.jsx:245` `INTERVAL_GROUP_ORDER` 에 `'longer'` 4번째
3. `Tradingmode/loader.js:188-195` `LOOKBACK_BY_INTERVAL` 에 `'1w': 730, '1M': 3650`
4. `Tradingmode/styles.css:397` 영역에 `.tf-group--longer { background: oklch(0.16 0.005 240 / 0.6); }`
5. `Tradingmode/index.html` 캐시 버스트 v11 → v12
6. 수동 검증 (T-F1~T-F5)

### 10.4 마무리

- 백엔드 pytest 151/151 PASSED
- Frontend 6 인터벌 (v0.7) + 2 인터벌 (v0.8) 총 8개 모두 동작

**총 예상 시간**: ~3시간

---

## 11. Future Extensions (v0.9+)

- 분기봉(`3M`), 반기봉(`6M`), 연봉(`1Y`) — 수요 확인 후
- 한국 거래일 캘린더 (공휴일 보정) — `pandas_market_calendars` 라이브러리 도입
- 주/월봉 전용 지표 파라미터 가이드 (RSI 14주봉 = 약 3.5개월 의미 설명)
- Watchlist mini-spark 인터벌 선택
- 사용자 커스텀 lookback (slider UI)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-05 | 초안 — Plan v1.0 의 10 FRs를 백엔드 enum/literal/어댑터/pytest + 프론트엔드 상수/CSS 단위로 구체화. 코드 사실관계 사전 검증 완료(line 번호 모두 verified). | 900033@interojo.com |
| 0.2 | 2026-05-05 | design-validator 92% → 보강. **H-1** §5.1 Pydantic body 5건 + FastAPI Query annotation 5건 (api/{indicators,ohlcv,signals,strategy,trend}.py) 분리 enum 정정. **M-1** 클래스명 정정 (line 51=OHLCVResponse, 64=IndicatorsResponse, 122=AIExplainRequest). **M-2** §3.6 cache 의미 명시 — parquet 은 resampled 결과만 캐시, daily fetch 는 매 cache miss 재실행 (v0.9 daily-cache 레이어 future). **L-1** §6.2 intervalReqRef race-guard line citation (app.jsx:260/288/292/298). 목표 95%+. | 900033@interojo.com |
| 0.3 | 2026-05-06 | 구현 후 cleanup (gap-detector 97%→ 후속). **M-1** krx_adapter 에 `_MIN_DAILY_FOR_INTERVAL` minimum-bars guard 추가 (1w≥5, 1M≥15) — 신규상장 종목 partial bucket 누출 차단. **L-1** race-guard line citation 312/340/344/350 으로 갱신 (cleanup 후 코드 line drift). **L-2** frontend `localizeIntervalError` 헬퍼 추가 — 백엔드 영문 에러 → 한국어 사용자 메시지 매핑 (`{symbol} {iv}봉 데이터 부족 — 일봉 N일 (최소 M일 필요)` 등). **L-4** `_assertIntervalKeysDistinct` IIFE — INTERVAL_LABELS 8 키 + 1m/1M case-sensitive 런타임 검증. **C-3** T-B1/T-B2 정확 count 검증 + T-B3 진짜 minimum-bars 검증 + T-B3b 분리 (all-NaN closes). 9/9 pytest PASSED. v11→v13 캐시 버스트. | 900033@interojo.com |
