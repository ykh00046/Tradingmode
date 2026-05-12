# Archive — 2026-05

> 본 디렉토리는 2026년 5월에 PDCA 사이클이 완료된 feature를 보관합니다.

---

## 📦 Archived Features

### 3. longer-intervals (v0.8.0)

| 항목 | 값 |
|---|---|
| **종료일** | 2026-05-07 |
| **최종 Match Rate** | **99%** (Critical/High 0건, cleanup 후 v0.4.1 와 동급) |
| **Iterations** | 1 (수동 cleanup, gap-detector 97% → 99%) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |
| **사이클 크기** | 작은 사이클 (~3.5시간 = 3h Phase A/B/C + 30min cleanup) |

**한 줄 요약**: 주봉(`1w`) + 월봉(`1M`) OHLCV 인터벌 추가. v1 MVP 스코프(분~일봉)에서 빠진 장기 시점 보강. **Crypto = Binance 네이티브** `_INTERVAL_MAP` 두 줄 확장, **KR = pykrx 일봉 → pandas resample** (`'W-FRI'` 한국 거래일 종료, `'ME'` pandas 2.x month-end). Backend Interval enum +`W1`/`MN1` (M1 분봉과 명시 구분), IntervalLiteral 한 곳 수정으로 10 endpoint 자동 반영, Frontend `INTERVAL_LABELS` +`'주'/'월'` + `'longer'` 4번째 그룹.

**보관 문서** (`./longer-intervals/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [longer-intervals.plan.md](longer-intervals/longer-intervals.plan.md) | 230 | Plan v1.0 — 10 FRs (Crypto 네이티브 + KR resample 양 시장) + FR-09 env caveat |
| [longer-intervals.design.md](longer-intervals/longer-intervals.design.md) | ~520 | Design v0.3 — design-validator 92%→96% 보강 (v0.7 78% 대비 +14pt 회복) + post-cleanup line drift 갱신 |
| [longer-intervals.analysis.md](longer-intervals/longer-intervals.analysis.md) | ~150 | Gap v1.1 — 99% match (97% baseline + cleanup +2pt) |
| [longer-intervals.report.md](longer-intervals/longer-intervals.report.md) | 367 | 통합 보고서 + 8 Architecture Decisions + 5 Process Lessons + v0.9 로드맵 |

**핵심 결과**

- 백엔드 pytest 9/9 PASSED in `test_data_loader.py` (기존 4 + 신규 5: T-B1 weekly, T-B2 monthly, T-B3 minimum-bars guard, T-B3b NaN closes 방어, T-B4 Binance routing)
- `core/data_loader.py` (61줄) + `lib/cache.py` (137줄) 변경 0 — 캐시 경로 `{interval}` 슬롯 자동 분리 활용
- `krx_adapter.py` 대규모 리팩 — `_INTERVAL_TO_FREQ`, `_SUPPORTED_INTERVALS`, `_RESAMPLE_BUFFER_DAYS`, `_MIN_DAILY_FOR_INTERVAL` (cleanup), `_ensure_supported_interval`, `_resample_ohlcv`, `download()` 분기
- Binance 네이티브 — `_INTERVAL_MAP` 두 줄 추가만으로 ccxt `1w`/`1M` 그대로 통과
- Frontend — `INTERVAL_LABELS` 8 entries + `INTERVAL_GROUP_ORDER` 4 그룹 + `LOOKBACK_BY_INTERVAL` (`1w:730일, 1M:3650일`) + `.tf-group--longer` CSS + cleanup 보강 2건
- 캐시 버스트 v11 → v13 (cleanup 단계 v12→v13)

**Architecture Decisions worth remembering** (8)

1. **Crypto vs KR 비대칭** — Binance 네이티브 (2줄) + KR resample (full helper) 분리 의도적. 데이터 소스 능력 차이 반영.
2. **`'W-FRI'` (한국 금요일 마감) + `'ME'` (pandas 2.x month-end)** — locale + 라이브러리 버전 인식.
3. **`MN1` enum 명명** — `M1` (분봉) 충돌 회피. JS object key 는 case-sensitive 라 자연 보장이지만 가독성 hedge.
4. **Cache 레이어 무변경** — `lib/cache.py:60` 의 `{market}/{symbol}/{interval}/` 경로 패턴이 1w/1M parquet 자동 분리. 추가 코드 0.
5. **Buffer trim `resampled[index >= start]`** — lookback 확장으로 생긴 partial period 정리.
6. **Minimum-bars guard with details dict** — backend `e.details = {daily_rows, min_required, interval}` 가 frontend `localizeIntervalError` 깔끔한 한국어 매핑 가능케 함.
7. **`localizeIntervalError` 패턴 매칭** — 백엔드 영문 5 패턴 → 한국어. v0.9 watchlist/signals/backtest 로 확장 가능한 reusable 인프라.
8. **Runtime IIFE assertion** — `_assertIntervalKeysDistinct` 가 미래 회귀 (key collapse 등) 즉시 catch.

**Process Lessons** (5)

1. **사전 그라운딩 효과 입증** — v0.7 lesson #1 ("design 작성 전 grep") 적용으로 첫 검증 92% (v0.7 78% 대비 **+14pt**). 영구 룰로 codify 권장.
2. **Resample fixture 는 explicit date 검사 필수** — T-B1 첫 시도가 W-FRI weekend 버킷 inclusion 미인지로 fail. fixture 14→10일 조정으로 해소.
3. **Backend test count 는 environment-dependent** — "151 PASSED" 예측이 backtesting 모듈 미설치 환경에서 어긋남. 향후 Plan FR 는 절대 카운트 대신 "신규 N PASSED + 기존 보존" 표현 권장.
4. **Backend → Frontend 에러 매핑은 reusable 인프라** — `localizeIntervalError` 를 v0.9 다른 영역으로 확장 (watchlist load fail, signal fetch error 등).
5. **Manual cleanup 이 auto-iterate 보다 architectural depth 높음** — 30분 만에 97%→99% + minimum-bars guard 같은 깊은 개선.

---

### 2. ux-improvements (v0.7.0)

| 항목 | 값 |
|---|---|
| **종료일** | 2026-05-04 |
| **최종 Match Rate** | **96%** (Critical/High 0건) |
| **Iterations** | 0 (96% ≥ 90%, iterate 불필요) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |
| **사이클 크기** | 작은 사이클 (~4시간) |

**한 줄 요약**: 차트 페이지 사용 편의성 전반 개선. 인터벌 한국어 라벨(1분/5분/15분/1시간/4시간/일) + 분/시간/일 그룹 시각 구분, Zoom 차트 우상단 floating 칩 분리, 우측 패널 3섹션 collapsible(localStorage 영속), 지표 4그룹 헤더(추세/변동성/선행 RPB/표시), TopBar 1280/1024 반응형(essential 3/compact/full), Watchlist ★ 즐겨찾기 + 상단 고정 + stale 자동 정리, 신호 limit slider [10/20/50/100]. **첫 100% 순수 Frontend 사이클** — 백엔드 0건 변경.

**보관 문서** (`./ux-improvements/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [ux-improvements.plan.md](ux-improvements/ux-improvements.plan.md) | 230 | Plan v1.2 — 7 UX 이슈 → 10 FRs (우선순위 1+2) |
| [ux-improvements.design.md](ux-improvements/ux-improvements.design.md) | ~480 | Design v0.3 — validator 78% → 91% → 96% 보강 (3 라운드) |
| [ux-improvements.analysis.md](ux-improvements/ux-improvements.analysis.md) | ~150 | Gap v1.0 — 96% match, Critical/High 0, FR 10/10, T 13/13 feasibility |
| [ux-improvements.report.md](ux-improvements/ux-improvements.report.md) | 368 | 통합 보고서 + Architecture Decisions 6 + Process Lessons 5 + v0.8 로드맵 |

**핵심 결과**

- 백엔드 147/147 무영향 (FR-10, grep 0건 empirically verified)
- 신규 파일 1개: `Tradingmode/lib/storage.js` (~30 lines, `window.tmStorage` IIFE, prefix `tradingmode-`)
- 수정 파일 3개: `Tradingmode/{app.jsx +200 lines, styles.css +80 lines, index.html (script slot + v8→v9)}`
- 신규 React 컴포넌트: `<CollapsibleSection>` (sectionId, ARIA expanded, Enter/Space, lazy storage init)
- 신규 헬퍼: `formatPriceCompact()`, `useViewportWidth()`, `INTERVAL_LABELS`, `INDICATOR_GROUPS`
- localStorage 키 3개 사용: `ws-right-collapsed` / `wl-favs` / `signals-limit` (4번째 `ind-groups-collapsed` 는 design 잔여, 미사용)

**Architecture Decisions worth remembering** (6)

1. **`<span role="button">` for ★** — `<button>` 안 `<button>` 중첩 회피, ARIA + 키보드 보존
2. **CSS scope `.right-panel .panel-section`** — BacktestPage 동일 클래스 사용 → 회귀 사전 차단
3. **`tmStorage` IIFE plain JS** — Babel 외부 로드, 첫 `.jsx` 전 보장 → load-order safety
4. **Compound-class state** (`.collapsed`, `.is-fav`) — BEM `--modifier` 대신 기존 컨벤션 (`.wl-row.active`, `.ind-toggle.on`) 일치
5. **`useState(() => ...)` lazy init for storage reads** — 마운트 flash 방지 (T-05 새로고침 후 상태 유지 구조적 보장)
6. **CSS `@media` + JS 분기 이중 방어** — TopBar `1279/1023` gap 축소 + `useViewportWidth` essential filter

**Process Lessons** (5)

1. Design validator 첫 검증 78%는 코드 사실관계 오류 — `.cp-*` 클래스/ `charts.jsx` 위치 잘못 가정. 후속 사이클은 design 작성 전 grep 선행 필요.
2. **순수 Frontend 사이클** = backend regression cost 0 (~10분 절약). 가치 입증.
3. Compound-class CSS 컨벤션 (`.section.collapsed`)을 Design §9.2에 codify — 향후 사이클 자동 상속.
4. `tmStorage` IIFE는 feature-specific X, **재사용 가능 인프라**. 향후 client state 작업은 raw `localStorage.setItem` 금지.
5. **CSS scope leak이 frontend 최고 blast-radius 버그**. 다중 사용 클래스 수정 전 1회 grep 의무화.

---

### 1. rsi-price-bands (v0.6.0)

| 항목 | 값 |
|---|---|
| **종료일** | 2026-05-02 |
| **최종 Match Rate** | **98%** (Critical/High 0건, 전체 사이클 중 최고) |
| **Iterations** | 0 (98% ≥ 90%, iterate 불필요) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |
| **사이클 크기** | 작은 사이클 (3시간) |

**한 줄 요약**: 사용자 제공 Pine Script v5 "RSI Price Band" 알고리즘 채택. RSI 공식을 역산해 "다음 봉이 X로 마감하면 RSI=N" 가격 12개 컬럼(가격 6 + ATR 단위 거리 6)을 빌트인 지표에 추가. Strategy DSL에서 선행 신호 룰 작성 가능.

**보관 문서** (`./rsi-price-bands/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [rsi-price-bands.plan.md](rsi-price-bands/rsi-price-bands.plan.md) | 256 | Plan v0.1 — 11 FRs, Pine 컨셉 + 양방향+BARS 보완 |
| [rsi-price-bands.design.md](rsi-price-bands/rsi-price-bands.design.md) | ~600 | Design v0.2 — design-validator 91% → 95% 보강 |
| [rsi-price-bands.analysis.md](rsi-price-bands/rsi-price-bands.analysis.md) | ~150 | Gap v1.0 — 98% match, Critical/High 0 |
| [rsi-price-bands.report.md](rsi-price-bands/rsi-price-bands.report.md) | 450 | 통합 보고서 + Design v0.3 권장 + v0.7+ 로드맵 |

**핵심 결과**

- 백엔드 147/147 PASSED (이전 132 + 신규 15)
- 13 REST endpoint 변경 없음 (`RPB_` prefix 자동 인식 → `/api/indicators` 12 컬럼 추가)
- BUILTIN_INDICATORS 5 → 6 (Strategy Coach AI 코치 자동 노출)
- e2e Playwright (BTC/USDT 1년):
  - RPB_UP_70 = $80,047 (현재가 $76,330 +5.0%)
  - 6 라인 + 6 라벨 차트 오버레이 (Pine 모방)
  - 단방향(RSI≥50→상단)/양방향 토글 동작
  - "RSI Imminent" 5번째 템플릿 등록

**Pine Script 검토 시 채택한 보완 2가지**
1. **양방향 항상 계산** — 백엔드 12 컬럼 모두, UI 단방향 토글
2. **`_BARS` 컬럼 6개 추가** — `(price - close) / ATR` (음수 OK = 이미 통과). AI 코치 룰 활용

---

## 📊 학습 효과 정량화 (전체 5 사이클 누적)

| 사이클 | Design 첫 검증 | Design 보강 후 | 구현 매치율 | Iterate | 비고 |
|--------|---------------:|---------------:|------------:|:-------:|------|
| v0.4.1 trading-analysis-tool | 78% | 95% | 95% | 1회 → 99% | 백엔드+프론트 풀스택 |
| v0.5.0 ai-strategy-coach | 84% | 92% | 97% | 0회 | DSL + AI 코치 |
| v0.6.0 rsi-price-bands | 91% | 95% | 98% | 0회 | Pine Script 채택 |
| v0.7.0 ux-improvements | 78% | 96% | 96% | 0회 | 첫 100% Frontend |
| **v0.8.0 longer-intervals** | **92%** | **96%** | **99%** | **1회 (manual)** | **주/월봉 + KR resample** |

**관찰**:
- v0.8 첫 검증 92% — v0.7 78% 대비 **+14pt 회복**. v0.7 lesson #1 ("design 작성 전 grep") 효과 입증. 5 사이클 중 두 번째로 높은 첫 검증 점수 (v0.6 91% 다음).
- 보강 폭 (+4pt) 가장 작아 사실관계 정확도 향상 누적.
- 구현 매치율 **99%** — v0.4.1 와 동급, 사이클 최고치.
- Critical/High 0건 **5 사이클 연속** — 패턴 견고.
- Iterate 통산: 2회 (v0.4.1 자동 1, v0.8 수동 1). 자동 vs 수동 비교: **수동이 architectural depth 높음**.
- 누적 영향: backend pytest 147 → 151+ (v0.8 신규 5건), frontend localStorage 키 4개 → 4개 그대로 유지 (v0.8 신규 0).

**핵심 잠언 누적** (각 사이클의 best practice)
- **v0.4**: PDCA loop 자체가 quality engine
- **v0.5**: 70/30 holdout 으로 overfitting 방지
- **v0.6**: Pine Script 같은 검증된 외부 알고리즘 채택은 raw 알고리즘 작성보다 안전
- **v0.7**: Design 작성 전 코드 grep 필수 (`.cp-*` 같은 가공 클래스 0건)
- **v0.8**: Backend → Frontend 에러 매핑은 feature 가 아닌 reusable 인프라

---

## 📁 Archive 정책

- 각 feature는 `{feature_name}/` 하위 폴더에 plan/design/analysis/report 4종 보관
- _INDEX.md에 종료일·매칭률·요약·다음 사이클 후보 기록
- 코드는 GitHub에 그대로 유지

## 🗓️ 이전 월 archive

- [`../2026-04/`](../2026-04/_INDEX.md) — trading-analysis-tool (99%) + ai-strategy-coach (97%)
