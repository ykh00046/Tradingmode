---
template: plan
version: 1.2
feature: rsi-price-bands
date: 2026-05-02
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.6.0
---

# rsi-price-bands Planning Document

> **Summary**: RSI 공식을 역산하여 *"RSI=N에 도달하려면 가격이 얼마여야 하는가"* 를 가격 축에 직접 표시하는 선행 지표 RPB(RSI Price Band)를 빌트인 지표에 추가하고, Strategy DSL에서 활용 가능하게 하며, 차트에 다단계 가격 라인으로 오버레이.
>
> **Project**: trading-analysis-tool
> **Version**: 0.6.0 (이전 사이클 v0.5.0 위에 누적)
> **Author**: 900033@interojo.com
> **Date**: 2026-05-02
> **Status**: Draft
> **Origin**: 사용자 제공 Pine Script "RSI Price Band" v5

---

## 1. Overview

### 1.1 Purpose

기존 `RSI_14` 컬럼은 0~100 값으로 *후행*. 본 사이클은 RSI 공식을 역산하여 *선행* 정보를 제공:

- **"다음 봉이 가격 X로 마감하면 RSI가 N이 된다"** — 진입/청산 *목표가* 계산
- 6개 가격대(상단 70/75/80, 하단 30/25/20)를 캔들 위 가격 라인으로 표시
- ATR × N 필터로 비현실적 거리 자동 숨김
- RS Cap(RSI 70 기준)으로 추세 잔류 시 하단 밴드 폭주 방지
- Strategy Coach DSL에서 `close > RPB_UP_70` 같은 *선행* 룰 작성 가능

### 1.2 Background

- 사용자가 직접 사용하던 Pine Script 지표 (TradingView v5)
- 이전 사이클 v0.5.0의 Strategy Coach에서 *빌트인 외 추천*이 자주 발생 — 더 풍부한 빌트인 풀 필요
- RSI 역산 컨셉은 시중 OSS 지표 라이브러리에 거의 없음 (차별화 강화)
- pandas-only 기반 v0.5 indicator 구현과 호환 (외부 의존 X)

### 1.3 Pine Script 검토 결과

**채택 (그대로)**: RSI 역산 알고리즘, ATR×5 필터, RS Cap(RSI 70 기준) — 기본값 그대로 따름.

**보완 (Pine 대비 개선)**:
1. **양방향 항상 계산** — Pine은 RSI≥50일 때 상단만 표시(시각적 깔끔). 백엔드는 6 컬럼 항상 계산해야 백테스팅 가능. UI 단방향 토글은 별도.
2. **`RPB_*_BARS` 컬럼 6개 추가** — `(price - close) / ATR(14)` = 도달까지 ATR 단위 거리. AI 코치/DSL이 "임박도" 활용 가능 (예: `RPB_UP_70_BARS < 1.5` = 1.5 ATR 안에 RSI 70 도달).
3. **임계값 사용자 정의** — `IndicatorConfig.rpb_upper / rpb_lower` (기본 [70,75,80] / [30,25,20]).

**보류 (v0.7 이후)**:
- 멀티 타임프레임 (MTF) — 일봉 시스템에 충분
- 시각 라벨 + 정보 테이블 (Pine UI 요소) — Frontend 차트 오버레이로 대체

### 1.4 Related Documents

- 이전 사이클: `docs/archive/2026-04/{trading-analysis-tool, ai-strategy-coach}/`
- 기존 코드 활용: `backend/core/indicators.py` (Wilder RMA 헬퍼 재사용), `backend/core/strategy_engine.py` (BUILTIN_INDICATORS 카탈로그)

---

## 2. Scope

### 2.1 In Scope

- [ ] **`add_rpb()` 백엔드 함수**: OHLCV → 12 신규 컬럼 (가격 6 + bars 6)
- [ ] **`compute()` 통합**: 기본값으로 자동 계산, `IndicatorConfig.rpb_*` 로 비활성/조정 가능
- [ ] **`BUILTIN_INDICATORS` 메타 등록**: Strategy Coach UI 자동완성 + AI 프롬프트 자동 노출
- [ ] **`/api/indicators` 응답에 자동 포함** — converters 변경 불필요 (prefix 'RPB_' 추가)
- [ ] **단위 테스트**: 알고리즘 정확성 (역산 검증), ATR 필터, RS Cap, 결정성, 음수가/0 분모 가드
- [ ] **Strategy Coach 사용 예시 템플릿 추가**: "RSI 임박 매수" 1개 (5번째 템플릿)
- [ ] **차트 오버레이 (Frontend)**: 캔들 위 6개 가격 라인 + 우측 끝 라벨 (Pine UI 모방), 토글 ON/OFF
- [ ] **README/Builtins 응답 description**: 한국어로 컨셉 설명 (사용자 외 협업자 이해 위해)

### 2.2 Out of Scope

- 멀티 타임프레임(MTF) — v0.7
- TradingView 라벨/테이블 1:1 복제 (Pine 고유 UI) — 우리 React 차트로 대체
- RSI 길이 동적 변경 (`length=14` 고정) — RSI 자체 파라미터는 IndicatorConfig.rsi_period 사용
- ATR 길이 변경 UI — `IndicatorConfig.rpb_atr_length` 키는 expose하되 UI 입력 X (default 14 고정, Pine 기본 따름)
- 정보 테이블 (Pine `var table info_tbl`) — 우리 차트 UI에 자연스럽게 녹임

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | `add_rpb(df, upper=[70,75,80], lower=[30,25,20], atr_mult=5.0, rs_cap_rsi=70.0, atr_length=14)` 구현 | High | Pending |
| FR-02 | RSI 역산 공식 정확도 — 합성 데이터 검증으로 ε < 0.5% 오차 | High | Pending |
| FR-03 | ATR×N 필터 — `(price - close) > atr_limit` 인 경우 NaN 반환 | High | Pending |
| FR-04 | RS Cap — 상승 추세에서 `avg_gain_cap = min(avg_gain, rs_cap × avg_loss)` 적용 (하단 밴드만) | High | Pending |
| FR-05 | 12 신규 컬럼 — `RPB_UP_70/75/80`, `RPB_DN_30/25/20`, `RPB_UP_70_BARS/.../`, `RPB_DN_30_BARS/...` | High | Pending |
| FR-06 | `compute()` 자동 통합 — 기본값으로 RPB 자동 계산, `rpb_upper=[]` 빈 리스트로 비활성화 가능 | High | Pending |
| FR-07 | `BUILTIN_INDICATORS`에 "RSI Price Band" 1개 등록, `category="momentum"` | Medium | Pending |
| FR-08 | Strategy Coach UI 빌트인 자동완성에 자동 노출 (별도 작업 불필요) | Medium | Pending |
| FR-09 | "RSI Imminent" 5번째 템플릿 — `buy_when: close < RPB_DN_30 and RPB_DN_30_BARS > -1.5`, `sell_when: close > RPB_UP_70` | Low | Pending |
| FR-10 | Frontend 차트 오버레이 — `charts.jsx`에 RPB 6 라인 + 우측 라벨, 토글 ON/OFF | Medium | Pending |
| FR-11 | RPB 컬럼이 `df_indicator_columns()` 응답에 자동 포함 (prefix `RPB_` 추가) | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| Performance | `add_rpb()` 1년치 365봉 < 50ms | `time.perf_counter` |
| Correctness | RSI 역산 → forward simulate → 원하는 RSI 도달 (오차 < 0.5%) | 단위 테스트 |
| Robustness | `avg_loss == 0`, `avg_gain == 0`, 음수가, 매우 짧은 series 모두 NaN 반환, raise 안 함 | 단위 테스트 |
| Backward Compat | 기존 12 RPB 컬럼 추가 외에 다른 컬럼 변경 X — 기존 75+57=132 테스트 통과 유지 | pytest |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 High 우선순위 FR 구현
- [ ] BTC/USDT 1년치 일봉 데이터로 RPB 12 컬럼 정상 계산 (NaN 비율 < 30%, 워밍업 후 모두 valid)
- [ ] `start.bat` 기동 → Strategy Coach 5번째 탭에서 "사용 가능 컬럼" 목록에 RPB 12개 노출
- [ ] DSL 룰 `close < RPB_DN_30` 으로 백테스트 실행 가능
- [ ] Frontend ChartPage 토글로 RPB 라인 표시/숨김
- [ ] 백엔드 132 + 신규 ~15 = 147 테스트 통과

### 4.2 Quality Criteria

- [ ] Gap Analysis 매치율 ≥ 90%
- [ ] 신규 코드 단위 테스트 90% 이상 커버
- [ ] 빌드/실행 시 에러 0건
- [ ] Pine Script 원본과 수치 비교 시 알려진 데이터(BTC 2025-01) 오차 < 1%

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 알고리즘 역산 미세 오차 — Wilder RMA 분모 계수 단순화 | Medium | Medium | 단위 테스트로 forward simulate 검증, 오차 < 0.5% 보장 |
| 매우 짧은 series에서 NaN 폭증 → 백테스트 실패 | Medium | High | min_periods 보장 + IS/OOS split 시 전체 df에 compute (이미 v0.5에서 정책) |
| `avg_loss = 0` 인 케이스에서 0 나누기 | High | Low | `where(avg_loss != 0, ...)` 패턴 (기존 RSI 처리와 동일) |
| 사용자 정의 임계값이 잘못 (예: lower=[80, 90]) | Low | Low | 입력 검증 — upper > 50, lower < 50, 정렬 후 사용 |
| 차트 오버레이가 12 라인 모두 표시 시 시각 혼잡 | Medium | High | 토글로 전체 ON/OFF + Pine처럼 RSI≥50/<50 단방향 표시 옵션 |
| BUILTIN_INDICATORS 등록 후 AI가 기존 RSI 대신 RPB만 추천 → 학습 편향 | Low | Medium | description에 "RSI 보완 지표" 명시, AI 프롬프트 변경 X |
| `RPB_*_BARS` 컬럼이 음수 가능 (현재가가 이미 도달) | Low | Medium | 음수도 의미 있음 ("이미 N ATR 만큼 지났다") — 명세 명확화 |
| ATR 14 고정 — RSI 길이와 다른 종목엔 부적합 | Low | Low | v0.7에서 입력화, v0.6은 Pine 기본 따름 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Selected |
|-------|:--------:|
| Starter | ☐ |
| **Dynamic** | ☑ |
| Enterprise | ☐ |

기존 사이클 그대로 — 단일 지표 추가는 Dynamic 충분.

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 알고리즘 | Pine 그대로 / 컨셉만 + 보완 | **컨셉+보완** (양방 + BARS) | 백테스트엔 양방 필수, BARS는 AI 코치에 유용 |
| 컬럼 prefix | `RPB_` / `RSIPB_` / `RPRB_` | **`RPB_`** | 짧고 RSI Price Band 약자 직관 |
| 활성화 정책 | opt-in / opt-out | **opt-out** (기본 활성) | 빌트인 추가가 목적, 명시적 비활성 가능 |
| 임계값 | 하드코딩 / IndicatorConfig | **IndicatorConfig** | 사용자 정의 가능 |
| ATR 길이 | 입력화 / 14 고정 | **14 고정** | Pine 기본 따름, 향후 입력화 |
| 음수 BARS | 0으로 클립 / 그대로 | **그대로** | "이미 도달" 정보 보존 |
| Frontend 토글 | 항상 표시 / 토글 / RSI 50 단방향 | **토글 + 단방향 옵션** | 시각 혼잡 제어 |

### 6.3 폴더 구조 (변경분만)

```
backend/
├── core/
│   ├── indicators.py            (확장: add_rpb + compute 통합)
│   └── strategy_engine.py       (확장: BUILTIN_INDICATORS에 RPB 추가)
├── api/
│   └── converters.py            (확장: _INDICATOR_PREFIXES에 'RPB_' 추가)
└── tests/
    └── test_indicators.py       (확장: ~15 RPB 테스트 추가)

Tradingmode/
├── strategy-coach-page.jsx      (확장: 5번째 템플릿 "RSI Imminent" + 라벨 표시)
├── charts.jsx                   (확장: RPB 오버레이 + 우측 라벨)
└── styles.css                   (확장: .rpb-line, .rpb-label 등)
```

---

## 7. Convention Prerequisites

### 7.1 Existing Conventions (재사용)

- [x] Python 3.11+, pandas-only indicators
- [x] FastAPI + Pydantic v2
- [x] React 18 (CDN), Babel standalone
- [x] pytest 132 baseline (이전 사이클 기준)
- [x] JetBrains Mono / OKLCH 색상 토큰

### 7.2 Conventions to Define/Verify

| Category | New | Priority |
|----------|-----|:--------:|
| RPB 컬럼 명명 | `RPB_UP_<rsi>` / `RPB_DN_<rsi>` / `RPB_UP_<rsi>_BARS` / `RPB_DN_<rsi>_BARS` | High |
| 음수 BARS 의미 | "이미 RSI N 가격 통과 — N ATR 만큼 지남" | Medium |
| IndicatorConfig 키 | `rpb_upper: list[int]`, `rpb_lower: list[int]`, `rpb_atr_mult: float`, `rpb_rs_cap_rsi: float` | High |

### 7.3 Environment Variables (변경 없음)

기존 그대로. 신규 추가 X.

### 7.4 Pipeline Integration

기존 v0.5.0 그대로.

---

## 8. Next Steps

1. [ ] 사용자 검토 및 Plan 승인
2. [ ] Design 문서 작성 (`/pdca design rsi-price-bands`)
   - 핵심: RSI 역산 의사코드 + ATR/RS Cap 적용 순서 + 12 컬럼 명세 + 차트 오버레이 SVG 명세
3. [ ] 구현 (`/pdca do rsi-price-bands`)
4. [ ] Gap Analysis (`/pdca analyze rsi-price-bands`)

**예상 작업량**: ~3시간 (작은 사이클)
- Phase A 백엔드 (indicators + 테스트): 1.5시간
- Phase B API + BUILTIN 등록: 30분
- Phase C 프론트 차트 오버레이 + 템플릿: 1시간

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-02 | 초안 — Pine Script 컨셉 채택 + 양방향+BARS 보완 결정 | 900033@interojo.com |
