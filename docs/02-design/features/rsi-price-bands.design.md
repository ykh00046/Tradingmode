---
template: design
version: 1.2
feature: rsi-price-bands
date: 2026-05-02
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.6.0
---

# rsi-price-bands Design Document

> **Summary**: Wilder RMA 역산으로 "다음 봉이 가격 X로 마감하면 RSI=N" 을 계산해 캔들 위 가격 라인으로 표시. 12 신규 컬럼(가격 6 + ATR 단위 임박도 6) + Strategy DSL 통합 + React 차트 오버레이.
>
> **Project**: trading-analysis-tool
> **Version**: 0.6.0
> **Author**: 900033@interojo.com
> **Date**: 2026-05-02
> **Status**: Draft
> **Planning Doc**: [rsi-price-bands.plan.md](../../01-plan/features/rsi-price-bands.plan.md)
> **Origin**: 사용자 제공 Pine Script v5

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | Schema | 본 문서 §3 + IndicatorConfig 확장 |
| Phase 2 | Convention | v0.5.0 그대로 + 본 문서 §10 보강 |
| Phase 4 | API Spec | 변경 없음 (`/api/indicators` 응답에 자동 포함) |

---

## 1. Overview

### 1.1 Design Goals

- **Pine Script 알고리즘 그대로 채택** — 검증된 수학, 사용자 익숙
- **양방향 항상 계산** — 백엔드 12 컬럼, UI 단방향 토글
- **단일 함수**: `add_rpb()` 하나로 12 컬럼 모두 계산, `compute()` 자동 통합
- **순수 함수성**: 동일 OHLCV 입력 → 동일 12 컬럼 출력
- **시각 노이즈 억제**: ATR×N 필터로 "도달 불가 가격" 자동 NaN
- **선행 시그널성**: Strategy DSL에서 진입/청산 *목표가* 룰 작성 가능

### 1.2 Design Principles

- **Pine 알고리즘 충실 재현 + 명시적 보완 2가지** (양방·BARS)
- **결정론적**: NaN 처리 일관, 부동소수 비교 X
- **방어적**: `avg_loss==0`, `avg_gain==0`, 음수가, 0봉 등 모두 graceful (raise 안 함, NaN 반환)
- **재사용**: 기존 Wilder RMA 헬퍼(`_wilder_ewm`) 활용

---

## 2. Architecture

### 2.1 데이터 흐름 (변경 없는 부분 굵게 표시)

```
사용자 백테스트 / 차트 요청
       │
       ▼
**data_loader.fetch(req)** → df (OHLCV)
       │
       ▼
**indicators.compute(df, config)**
       ├─→ add_sma, add_rsi, add_macd, add_bbands, add_adx (기존)
       └─→ ✨ add_rpb(df, ...) (신규)
                │
                ├─ Wilder RMA (재사용 _wilder_ewm)
                ├─ avg_gain, avg_loss 계산
                ├─ ATR(14) 계산
                ├─ RS Cap 적용 (하단만)
                ├─ 임계값별 가격 역산 (×6)
                └─ ATR 필터 적용
       │
       ▼
df + 12 RPB 컬럼
       │
       ├─→ /api/indicators → JSON (RPB_ prefix 자동 인식)
       │
       └─→ strategy_engine.evaluate_rules(df, ...)
              사용자 DSL이 RPB_DN_30 등 컬럼 직접 참조 가능
```

### 2.2 의존성

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `indicators.add_rpb` | pandas, `_wilder_ewm` | RSI 역산 + ATR 필터 |
| `indicators.compute` | `add_rpb` | 자동 통합 |
| `strategy_engine.BUILTIN_INDICATORS` | (메타데이터만) | UI 자동완성 + AI 코치 풀 |
| `api/converters._INDICATOR_PREFIXES` | (튜플 추가) | RPB_ 프리픽스 자동 인식 |
| `Tradingmode/charts.jsx` | api.indicators 응답 | 차트 라인 오버레이 |
| `Tradingmode/strategy-coach-page.jsx` | (변경 없음) | 빌트인 자동완성에 자동 노출 |

---

## 3. Data Model

### 3.1 신규 컬럼 (df, 12개)

| 컬럼명 | 타입 | 의미 | NaN 조건 |
|--------|------|------|---------|
| `RPB_UP_70` | float64 | 다음 봉이 이 가격으로 마감하면 RSI=70 | `(price-close) > ATR×N` 또는 `avg_loss==0` |
| `RPB_UP_75` | float64 | RSI=75 도달가 | 동일 |
| `RPB_UP_80` | float64 | RSI=80 도달가 | 동일 |
| `RPB_DN_30` | float64 | RSI=30 도달가 (하락 시) | `(close-price) > ATR×N` 또는 `avg_gain_cap==0` 또는 `price ≤ 0` |
| `RPB_DN_25` | float64 | RSI=25 도달가 | 동일 |
| `RPB_DN_20` | float64 | RSI=20 도달가 | 동일 |
| `RPB_UP_70_BARS` | float64 | `(RPB_UP_70 - close) / ATR_14` — ATR 단위 거리, 양수 | 가격이 NaN이면 NaN |
| `RPB_UP_75_BARS` | float64 | 동일 | |
| `RPB_UP_80_BARS` | float64 | 동일 | |
| `RPB_DN_30_BARS` | float64 | `(RPB_DN_30 - close) / ATR_14` — **음수** (현재가가 위에 있음). 0에 가까울수록 도달 임박 | |
| `RPB_DN_25_BARS` | float64 | 동일 | |
| `RPB_DN_20_BARS` | float64 | 동일 | |

**음수 BARS 정책**: 컬럼 결정대로 `_BARS = (price - close) / ATR_14`. 하단 밴드는 항상 음수, 상단은 항상 양수. 클립 안 함 — "이미 도달했다" 정보 보존.

### 3.2 IndicatorConfig 확장

```python
# core/types/schemas.py — 기존 IndicatorConfig 확장
class IndicatorConfig(TypedDict, total=False):
    sma_periods: list[int]
    rsi_period: int
    macd: tuple[int, int, int]
    bbands: tuple[int, float]
    adx_length: int
    # ✨ 신규
    rpb_upper: list[int]            # default [70, 75, 80]
    rpb_lower: list[int]            # default [30, 25, 20]
    rpb_atr_mult: float             # default 5.0
    rpb_rs_cap_rsi: float           # default 70.0
    rpb_atr_length: int             # default 14
```

비활성화: `{"rpb_upper": [], "rpb_lower": []}` 전달 시 12 컬럼 모두 생략.

### 3.3 BUILTIN_INDICATORS 확장 (1개 추가)

```python
# core/strategy_engine.py
BuiltinIndicator(
    name="RSI Price Band",
    columns=[
        "RPB_UP_70", "RPB_UP_75", "RPB_UP_80",
        "RPB_DN_30", "RPB_DN_25", "RPB_DN_20",
        "RPB_UP_70_BARS", "RPB_UP_75_BARS", "RPB_UP_80_BARS",
        "RPB_DN_30_BARS", "RPB_DN_25_BARS", "RPB_DN_20_BARS",
    ],
    params={
        "upper": [70, 75, 80],
        "lower": [30, 25, 20],
        "atr_mult": 5.0,
        "rs_cap_rsi": 70.0,
    },
    description="RSI 역산 가격 밴드 — '다음 봉이 X로 마감하면 RSI=N'. _BARS = ATR 단위 거리(음수=이미 통과)",
    category="momentum",
),
```

---

## 4. Algorithm Specification

### 4.1 핵심 수식 (Pine 검증)

**RSI 역산 (Wilder RMA 가정)**

`length = 14`, `n = length` (Wilder RMA). 다음 봉이 `close + x` 로 마감 시:

```
new_avg_gain = ((n-1) × avg_gain + max(x, 0)) / n
new_avg_loss = ((n-1) × avg_loss + max(-x, 0)) / n
```

**Case 1 — 상승봉 (x > 0)**: `max(-x,0)=0` → `new_avg_loss = (n-1)/n × avg_loss`. 하지만 Pine은 단순화: `new_avg_loss ≈ avg_loss` 사용 (1봉 가정 시 손실 이동평균은 거의 불변). 본 구현도 동일.

```
RSI_target = 100 - 100/(1+RS_target)
RS_target = RSI_target / (100 - RSI_target)
RS_target = new_avg_gain / avg_loss
new_avg_gain = RS_target × avg_loss
((n-1) × avg_gain + x) / n = RS_target × avg_loss
x = n × RS_target × avg_loss - (n-1) × avg_gain
```

**Pine 코드 단순화**: `x = n × (RS × avg_loss − avg_gain)` — 분자 계수 `(n-1)` 대신 `n` 사용. ε 차이 발생 (n=14 기준 약 7% 오차 in `avg_gain` 계수). 본 구현은 **Pine과 동일 단순화**를 채택해 사용자 익숙한 출력 유지.

**상단 가격**: `RPB_UP = close + x` (단, `x > 0` AND `avg_loss > 0`)

**Case 2 — 하락봉 (y > 0, 가격이 close-y로 마감)**:

```
new_avg_loss = ((n-1) × avg_loss + y) / n
new_avg_gain ≈ avg_gain  (대칭 단순화)
RS_target = avg_gain / new_avg_loss
y = n × (avg_gain / RS_target - avg_loss)
```

**RS Cap 적용 (하단만)**: 강한 상승 추세에서 `avg_gain` 폭주 → `y` 가 비현실적 큼 → `price = close - y` 가 음수 또는 0 근처. 방지:

```
rs_cap = rs_cap_rsi / (100 - rs_cap_rsi)   # default 70/30 = 2.333
avg_gain_cap = min(avg_gain, rs_cap × avg_loss)
y = n × (avg_gain_cap / RS_target - avg_loss)  if avg_gain_cap > 0 else NaN
```

**하단 가격**: `RPB_DN = close - y` (단, `y > 0` AND `price > 0`)

### 4.2 ATR 필터

```
atr_limit = ATR(14) × atr_mult   # default 14, 5.0

상단: RPB_UP > close + atr_limit  → NaN
하단: RPB_DN < close - atr_limit  → NaN
```

### 4.3 BARS 컬럼

```
RPB_UP_<rsi>_BARS = (RPB_UP_<rsi> - close) / ATR_14   # 양수 (가격이 위)
RPB_DN_<rsi>_BARS = (RPB_DN_<rsi> - close) / ATR_14   # 음수 (가격이 아래)
```

NaN 처리: 가격 컬럼이 NaN이면 BARS도 NaN.

### 4.4 함수 시그니처

```python
def add_rpb(
    df: pd.DataFrame,
    upper: list[int] | None = None,           # [70, 75, 80]
    lower: list[int] | None = None,           # [30, 25, 20]
    atr_mult: float = 5.0,
    rs_cap_rsi: float = 70.0,
    rsi_length: int = 14,
    atr_length: int = 14,
) -> pd.DataFrame:
    """Append RSI Price Band columns (6 prices + 6 BARS = 12 columns).

    Wilder RMA 기반 역산. ATR 필터로 비현실적 거리 필터링. RS Cap으로 추세
    잔류 시 하단 밴드 폭주 방지.

    Defaults match the user's original Pine Script v5.

    Empty `upper=[]` or `lower=[]` skips the corresponding side.
    """
```

### 4.5 의사코드

```python
def add_rpb(df, upper=None, lower=None, atr_mult=5.0, rs_cap_rsi=70.0,
            rsi_length=14, atr_length=14):
    upper = upper or [70, 75, 80]
    lower = lower or [30, 25, 20]
    out = df.copy()

    # --- 빈 리스트면 비활성 (early return) ---
    if not upper and not lower:
        return out

    _ensure_min_length(out, max(rsi_length + 1, atr_length + 1), "RPB")
    n = rsi_length

    # --- avg_gain / avg_loss (RSI와 동일한 계산, 재사용 가능하면 사용) ---
    delta = out["close"].diff()
    avg_gain = _wilder_ewm(delta.clip(lower=0), n)
    avg_loss = _wilder_ewm((-delta).clip(lower=0), n)

    # --- ATR ---
    high, low, close = out["high"], out["low"], out["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = _wilder_ewm(tr, atr_length)
    atr_limit = atr * atr_mult

    # --- RS Cap (하단만) ---
    rs_cap = rs_cap_rsi / (100.0 - rs_cap_rsi)
    avg_gain_cap = pd.concat([avg_gain, rs_cap * avg_loss], axis=1).min(axis=1)

    # --- 상단 밴드 ---
    for rsi_t in upper:
        rs = rsi_t / (100.0 - rsi_t)
        x = n * (rs * avg_loss - avg_gain)
        price = close + x
        # x > 0 AND avg_loss > 0 AND (price - close) <= atr_limit
        valid = (x > 0) & (avg_loss > 0) & ((price - close) <= atr_limit)
        out[f"RPB_UP_{rsi_t}"] = price.where(valid, np.nan)

    # --- 하단 밴드 ---
    for rsi_t in lower:
        rs = rsi_t / (100.0 - rsi_t)
        # y = n * (avg_gain_cap / rs - avg_loss)  단, rs > 0
        y = n * (avg_gain_cap / rs - avg_loss)
        price = close - y
        valid = (
            (avg_gain_cap > 0)
            & (y > 0)
            & (price > 0)
            & ((close - price) <= atr_limit)
        )
        out[f"RPB_DN_{rsi_t}"] = price.where(valid, np.nan)

    # --- BARS 컬럼 ---
    for rsi_t in upper:
        col = f"RPB_UP_{rsi_t}"
        out[f"{col}_BARS"] = (out[col] - close) / atr  # 양수
    for rsi_t in lower:
        col = f"RPB_DN_{rsi_t}"
        out[f"{col}_BARS"] = (out[col] - close) / atr  # 음수

    return out
```

### 4.6 compute() 통합

```python
# indicators.compute() 끝부분에 추가
rpb_upper = cfg.get("rpb_upper", [70, 75, 80])
rpb_lower = cfg.get("rpb_lower", [30, 25, 20])
if rpb_upper or rpb_lower:
    out = add_rpb(
        out,
        upper=rpb_upper,
        lower=rpb_lower,
        atr_mult=cfg.get("rpb_atr_mult", 5.0),
        rs_cap_rsi=cfg.get("rpb_rs_cap_rsi", 70.0),
        rsi_length=cfg.get("rsi_period", DEFAULT_RSI_PERIOD),
        atr_length=cfg.get("rpb_atr_length", 14),
    )
```

---

## 5. UI/UX Design

### 5.1 Strategy Coach Editor — 빌트인 자동완성

기존 `details/summary` 풀이 자동 갱신 — `BUILTIN_INDICATORS` 등록만으로 동작:
- 새 항목: **RSI Price Band** — `RPB_UP_70, RPB_UP_75, RPB_UP_80, RPB_DN_30, RPB_DN_25, RPB_DN_20, RPB_UP_70_BARS, RPB_UP_75_BARS, RPB_UP_80_BARS, RPB_DN_30_BARS, RPB_DN_25_BARS, RPB_DN_20_BARS`

### 5.2 신규 템플릿 — "RSI Imminent" (5번째)

```javascript
// strategy-coach-page.jsx — TEMPLATES 배열 추가
{
  name: 'RSI Imminent',
  buy_when: 'close < RPB_DN_30 and RPB_DN_30_BARS > -1.5',
  sell_when: 'close > RPB_UP_70',
}
```

해석:
- 매수: 가격이 RSI=30 도달가 이하 + 1.5 ATR 이내 (선행 진입)
- 매도: 가격이 RSI=70 도달가 초과 (조기 익절)

### 5.3 ChartPage 오버레이

```
┌──────────────────── Chart ──────────────────────┐
│       ─ ─ ─ ─ ─ ─ ─ ─ RPB_UP_80 (red 30%) ───  │
│       ─────────────── RPB_UP_75 (red 50%) ──── │
│       ─────────────── RPB_UP_70 (red 70%) ──── │
│  ███ ████ ███ █ █ ██ █ █████  ← 캔들 (close)   │
│       ─────────────── RPB_DN_30 (green 70%) ── │
│       ─────────────── RPB_DN_25 (green 50%) ── │
│       ─ ─ ─ ─ ─ ─ ─ ─ RPB_DN_20 (green 30%) ─  │
└─────────────────────────────────────────────────┘
       [RPB ON/OFF] [단방향 표시: ON]   ← 토글
```

**표시 정책**:
- 우측 끝 라벨: `RPB_UP_70` 가격 + `(+5.2%)` (Pine 모방)
- inner(70/30) 진하고, outer(80/20) 50% 투명도, mid(75/25) 두꺼움 (Pine 그대로)
- 단방향 토글 ON: `current_rsi >= 50` → 상단만, `< 50` → 하단만
- 단방향 토글 OFF (기본): 양방향 모두 (백테스트는 양방향 데이터 사용)

### 5.4 Frontend 데이터 흐름

```javascript
// loader.js (확장)
function buildInd(indDict, candleCount, closes) {
  // ... 기존 ind 객체 ...
  ind.rpb = {
    up: {
      70: getColumn(indDict, 'RPB_UP_70', candleCount),
      75: getColumn(indDict, 'RPB_UP_75', candleCount),
      80: getColumn(indDict, 'RPB_UP_80', candleCount),
    },
    dn: {
      30: getColumn(indDict, 'RPB_DN_30', candleCount),
      25: getColumn(indDict, 'RPB_DN_25', candleCount),
      20: getColumn(indDict, 'RPB_DN_20', candleCount),
    },
    bars: {  // 음수 가능
      up: { 70: get('_BARS'), 75: ..., 80: ... },
      dn: { 30: ..., 25: ..., 20: ... },
    },
  };
  return ind;
}

// charts.jsx (오버레이 SVG)
// indicators 토글 객체에 'rpb' 키 추가, ON 시 라인 6개 + 라벨 6개 렌더
```

---

## 6. Error Handling

### 6.1 입력 검증

| 케이스 | 동작 |
|--------|------|
| `upper` 값이 ≤ 50 | InvalidStrategyError? **아니오, 단순 클립**: 50 ≤ x ≤ 99 만 사용. 잘못된 입력은 silently ignore (사용자 정의 임계값이라 유연) |
| `lower` 값이 ≥ 50 | 동일 — 1 ≤ x ≤ 49 만 사용 |
| `upper=[]`, `lower=[]` | 12 컬럼 모두 생략 (early return) |
| `df` 길이 < `max(rsi_length+1, atr_length+1)` | `InsufficientDataError` raise |
| `avg_loss == 0` (초기) | 해당 행은 NaN (where 패턴) |
| `atr == 0` 또는 NaN | BARS 컬럼이 NaN — 그대로 전파 |

### 6.2 부동소수 가드

- `pd.eval(0/0)` 또는 `inf` 가 나올 수 있는 모든 곳에 `where` + `np.nan` 패턴
- `np.errstate(divide='ignore', invalid='ignore')` 컨텍스트로 RuntimeWarning 억제

---

## 7. Security Considerations

신규 보안 이슈 없음. 기존 시스템에 컬럼 추가만 — 사용자 입력 경로 변경 없음.

- DSL evaluator는 `RPB_*` 컬럼명을 다른 컬럼과 동일하게 처리 (기존 AST 화이트리스트는 컬럼명 자체에 제한 없음, `df.columns` 기반)
- IndicatorConfig 입력은 Pydantic 검증 (TypedDict) 통과 — 타입 보장

---

## 8. Test Plan

| 영역 | 테스트 | 도구 |
|------|-------|------|
| `add_rpb` 기본 동작 — 12 컬럼 생성 | trending_up_df → 컬럼 모두 존재, dtype float64 | pytest |
| 알고리즘 정확도 — forward simulate | 합성 데이터에서 `close + x_predicted` 로 1봉 더하면 실제 RSI ≈ target | pytest |
| ATR 필터 — 너무 먼 가격은 NaN | atr_mult=0.1 로 매우 작게 설정 → 거의 모든 가격 NaN | pytest |
| RS Cap — 강한 상승 trend에서 하단 가격 > 0 | trending_up_df 에서 `RPB_DN_30 > 0` 인 비율 검증 | pytest |
| BARS 컬럼 — 상단 양수, 하단 음수 | 모든 valid 행 검증 | pytest |
| upper/lower 빈 리스트 → 12 컬럼 모두 생략 | 컬럼 확인 | pytest |
| compute() 통합 — 자동 포함 + IndicatorConfig 비활성화 | `compute(df, {"rpb_upper": []})` → 컬럼 X | pytest |
| 결정성 — 동일 입력 동일 출력 | 두 번 호출 비교 | pytest |
| `avg_loss==0` 케이스 — 초기 row NaN | 데이터 첫 N봉 검증 | pytest |
| 음수가 가드 — 하단 price > 0 보장 | 결과에서 음수 없음 | pytest |
| BUILTIN_INDICATORS 등록 — `RPB_*` 12개 모두 catalog에 | test_strategy_engine 확장 | pytest |
| `df_indicator_columns` — RPB_ prefix 자동 인식 | API 응답에 모든 RPB 컬럼 포함 | pytest |
| API endpoint — `/api/indicators` BTC 1년치 → RPB 컬럼 포함 | TestClient | pytest |
| Strategy DSL — `close < RPB_DN_30` 룰 백테스트 성공 | TestClient | pytest |

목표: **신규 ~15 테스트**, 기존 132 + 15 = **147 통과**.

---

## 9. Clean Architecture

기존 v0.5 레이어 그대로:
- Domain: `indicators.py` (확장), `strategy_engine.BUILTIN_INDICATORS` (확장)
- API Boundary: `converters._INDICATOR_PREFIXES` (튜플에 'RPB_' 추가)
- Frontend: `loader.js` (ind.rpb 구조 추가), `charts.jsx` (오버레이), `strategy-coach-page.jsx` (템플릿)

새 모듈/파일 없음 — 모두 기존 위치에 추가.

---

## 10. Coding Convention (v0.5 그대로 + 보강)

| Item | 적용 |
|------|------|
| 컬럼명 prefix | `RPB_UP_<rsi>` / `RPB_DN_<rsi>` / `*_BARS` (예: `RPB_UP_70`, `RPB_DN_30_BARS`) |
| BARS 음수 의미 | "이미 통과 — N ATR 만큼 지남". 클립 안 함. |
| RS Cap 기본값 | RSI 70 (Pine 그대로) — 사용자 입력 가능 |
| ATR 기본값 | 14 (Pine 그대로) — v0.6에서는 입력화 안 함 |
| 임계값 기본값 | upper=[70,75,80], lower=[30,25,20] (Pine 그대로) |
| 빈 리스트 정책 | `upper=[]`, `lower=[]` 시 해당 측 12 컬럼 모두 생략 |
| 잘못된 임계값 | silently filter (50 경계 외 무시) — 사용자 친화 |
| 결정성 | `np.errstate(...)` 로 NaN/inf 방어, 모든 비교는 pandas-vectorized |

---

## 11. Implementation Guide

### 11.1 폴더 구조 (변경분만)

```
backend/
├── core/
│   ├── indicators.py            (확장: add_rpb 추가, compute 끝부분)
│   ├── strategy_engine.py       (확장: BUILTIN_INDICATORS에 RPB 1개 추가)
│   └── types/schemas.py         (확장: IndicatorConfig 5 신규 키)
├── api/
│   └── converters.py            (확장: _INDICATOR_PREFIXES 튜플에 'RPB_' 추가)
└── tests/
    └── test_indicators.py       (확장: 약 15 테스트 추가)

Tradingmode/
├── strategy-coach-page.jsx      (확장: TEMPLATES에 "RSI Imminent" 추가)
├── charts.jsx                   (확장: RPB 오버레이 SVG + 라벨)
├── loader.js                    (확장: ind.rpb 객체 구성)
└── styles.css                   (확장: .rpb-line, .rpb-label 약간)
```

### 11.2 Implementation Order (~3시간)

#### Phase A: Backend 도메인 (1시간)
1. [ ] `core/types/schemas.py` IndicatorConfig 5 신규 키 추가
2. [ ] `core/indicators.py` `add_rpb()` 작성 (의사코드 §4.5 기반)
3. [ ] `core/indicators.compute()` 끝부분에 RPB 통합 분기 추가
4. [ ] `tests/test_indicators.py` ~15 테스트 추가
5. [ ] `pytest -q` → 132 + 15 = 147 통과 확인

#### Phase B: API + 빌트인 등록 (30분)
6. [ ] `api/converters.py` `_INDICATOR_PREFIXES` 튜플에 `'RPB_'` 추가
7. [ ] `core/strategy_engine.py` `BUILTIN_INDICATORS` 리스트에 RPB 1개 추가
8. [ ] `tests/test_api/test_ohlcv_routes.py` 또는 신규 테스트로 `/api/indicators` 응답에 RPB 컬럼 포함 확인 (1~2 테스트)
9. [ ] `pytest -q` 재확인

#### Phase C: Frontend (1.5시간)
10. [ ] `Tradingmode/loader.js` `buildInd` 확장 — `ind.rpb` 객체 추가
11. [ ] `Tradingmode/charts.jsx` — RPB 6 라인 오버레이 + 우측 끝 라벨
    - `indicators` 토글 state에 `rpb: false` 기본 추가
    - 토글 ON 시 SVG `<line>` 6개 + `<text>` 6개 + 단방향 옵션 분기
12. [ ] `Tradingmode/styles.css` — `.rpb-line`, `.rpb-label` 약간 (Pine 색감 모방)
13. [ ] `Tradingmode/strategy-coach-page.jsx` — `TEMPLATES`에 5번째 "RSI Imminent" 추가
14. [ ] e2e Playwright — Chart 토글 ON 후 RPB 라인 6개 확인 + Strategy Coach 템플릿 동작

#### 검증 (~30분)
15. [ ] `start.bat` → BTC/USDT 1년치 차트 → RPB ON → 6 라인 표시 확인
16. [ ] Strategy Coach → "RSI Imminent" 템플릿 → 백테스트 → IS/OOS 결과
17. [ ] 사용자 정의 룰 `close < RPB_DN_30` 직접 작성 → 백테스트 동작 확인

---

## 12. Future Extensions (v0.7+)

- v0.7: ATR 길이 입력화, RSI 길이 다양화, MTF 지원
- v0.8: Pine `info_tbl` 같은 시각 정보 패널 (캔들 위 hover 시 RPB 가격/% 표시)
- v2: RPB 기반 자동 신호 (예: "close가 RPB_DN_30 터치 + RSI > 35" → BUY signal로 `signals.detect_all`에 추가)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-02 | 초안 — Pine 알고리즘 채택 + 양방·BARS 보완. 12 컬럼 명세, IndicatorConfig 확장, BUILTIN 등록, 차트 오버레이 설계 | 900033@interojo.com |
