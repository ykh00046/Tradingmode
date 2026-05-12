---
template: plan
version: 1.0
feature: longer-intervals
date: 2026-05-05
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.8.0
---

# longer-intervals Planning Document

> **Summary**: 주봉(`1w`) + 월봉(`1M`) 인터벌 추가. v1 MVP 스코프(분~일봉)에서 빠져있던 장기 시점. Crypto 는 Binance 네이티브 지원 활용, KR 주식은 일봉 → pandas resample('W'/'M') 로 집계. 인터벌 헤더 4번째 그룹 또는 `day` 그룹에 통합 표시.
>
> **Project**: trading-analysis-tool · **Version**: 0.8.0  
> **Author**: 900033@interojo.com · **Date**: 2026-05-05  
> **Status**: Draft  
> **Builds on**: v0.4 base + v0.5 strategy coach + v0.6 RPB + v0.7 UX

---

## 1. Overview

### 1.1 Purpose

차트 분석에서 장기 추세(주봉 6개월~1년치, 월봉 5~10년치) 확인이 빠져 있어, 단타~스윙 분석은 가능해도 **포지션 트레이딩 / 장기 투자 관점** 이 결여됨. 백엔드 두 어댑터(Binance/KRX) + frontend 인터벌 칩에 `1w`/`1M` 두 인터벌 추가.

### 1.2 Background

- v0.4 MVP 스코프: "Binance 분/시간/일봉 + KRX 일봉" 으로 한정. 단기 분석 우선.
- v0.7 UX 개선 사이클에서 인터벌 한국어화 완료 → `1m vs 1M` 케이스 충돌 시각 문제는 이미 해결됨.
- 사용자가 "주, 월봉이 왜 없냐" 직접 지적 (2026-05-05). 명백한 기능 갭.
- Binance ccxt: `1w`, `1M` 네이티브 지원 (`_INTERVAL_MAP` 확장만으로 즉시 동작).
- pykrx: 일봉만 제공 — 주/월봉은 일봉을 받아서 pandas `resample('W-FRI'/'M').agg(...)` 로 집계 필요.

### 1.3 Related Documents

- 이전 사이클 종료: `docs/archive/2026-05/ux-improvements/` (v0.7.0, 96%)
- 첫 사이클 archive (Interval enum 정의 위치): `docs/archive/2026-04/trading-analysis-tool/`
- 영향 코드: `backend/{core/types/schemas.py, api/schemas.py, core/adapters/{binance_adapter,krx_adapter}.py, api/{ohlcv,indicators,signals,backtest}.py}`, `Tradingmode/{app.jsx, loader.js}`

---

## 2. Scope

### 2.1 In Scope (v0.8)

#### 우선순위 1 — Critical (기능 갭 해소)
- [ ] **Backend Interval enum 확장**: `Interval.W1 = "1w"`, `Interval.M1_LONG = "1M"` (M1 가 분봉이라 별도 이름)
- [ ] **`IntervalLiteral` Pydantic literal 확장**: `Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]`
- [ ] **Binance 어댑터** `_INTERVAL_MAP` 에 `"1w": "1w", "1M": "1M"` 추가
- [ ] **KRX 어댑터** 에 일봉 fetch 후 pandas resample 로 주/월봉 집계 로직
- [ ] **Frontend `INTERVAL_LABELS`** 에 `1w: '주', 1M: '월'` 추가 (그룹: 신규 `'longer'`)
- [ ] **Frontend `INTERVAL_GROUP_ORDER`** 에 `'longer'` 4번째 그룹 추가 + 구분선 + 그룹 배경
- [ ] **Frontend `LOOKBACK_BY_INTERVAL`** 에 `1w: 365*2 (2년)`, `1M: 365*10 (10년)` 추가

#### 우선순위 2 — High (안정성)
- [ ] **pytest** — KRX resample 결과 검증 (open=첫날, close=마지막날, high=max, low=min, volume=sum)
- [ ] **에러 처리** — 데이터 부족 시(예: 신규 상장 종목으로 주/월봉 1개도 못 만들 때) 백엔드 명확한 메시지
- [ ] **캐시 키 분리** — 기존 `data/{market}/{symbol}/{interval}` 패턴이 자동으로 분리됨 확인

### 2.2 Out of Scope (v0.9+)

- 분기봉(`3M` quarterly), 연봉(`1Y`) — 수요 미확인
- KR 주식 주말/공휴일 보정 (한국 거래일 캘린더 사용 — 현재는 단순 calendar week 기준)
- 주/월봉 전용 지표 튜닝 (예: MA 파라미터 조정 — RSI/MA 는 그대로 사용)
- 주/월봉 Backtesting 별도 검증 (기존 strategy 가 그대로 동작 — slippage 등 가정만 다를 뿐)
- Watchlist mini-spark 주/월봉 전환 (일봉 고정 유지)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Backend `Interval` enum 에 `W1="1w"`, `MN1="1M"` (월봉 alias 명) 추가 | High | Pending |
| FR-02 | Backend `IntervalLiteral` Literal 에 `"1w", "1M"` 추가 | High | Pending |
| FR-03 | Binance 어댑터 `_INTERVAL_MAP` 에 `"1w", "1M"` 매핑 추가 (네이티브 kline 지원) | High | Pending |
| FR-04 | KRX 어댑터 — 일봉 fetch 후 pandas resample 로 주/월봉 OHLCV 집계 (open=first, high=max, low=min, close=last, volume=sum) | High | Pending |
| FR-05 | Frontend `INTERVAL_LABELS` 에 `'1w': { label: '주', group: 'longer' }`, `'1M': { label: '월', group: 'longer' }` 추가 | High | Pending |
| FR-06 | Frontend `INTERVAL_GROUP_ORDER` 에 `'longer'` 4번째 그룹 + `.tf-group--longer` CSS modifier + `.tf-divider` 자동 삽입 | High | Pending |
| FR-07 | Frontend `LOOKBACK_BY_INTERVAL` 에 `'1w': 730 (2년)`, `'1M': 3650 (10년)` 자동 lookback | Medium | Pending |
| FR-08 | KRX 종목에서 신규 상장 등으로 데이터 부족 시 명확한 에러 메시지 (`DataSourceError("주봉 1개 미만, 일봉 N일치 필요")`) | Medium | Pending |
| FR-09 | 모든 변경 후 기존 백엔드 pytest 무영향 + 신규 resample 테스트 4건 추가. **환경 caveat**: 절대 PASS 카운트는 backtesting 모듈 (선택 의존성) 설치 여부에 따라 변동. 핵심 검증은 "기존 PASSED 보존 + 신규 T-B1~T-B4 4건 PASSED" | High | Pending |
| FR-10 | Frontend v0.7 UX 무영향 (CSS 회귀 0, localStorage 키 추가 없음, 기존 6 인터벌 동작 그대로) | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| Performance | 주/월봉 첫 fetch 후 parquet 캐시 적중 시 < 100ms (일봉과 동일) | 수동 측정 |
| Correctness | KRX resample 결과 OHLCV 무결성 (open=Mon, close=Fri, high=주중 max) | pytest |
| Backward Compat | 기존 6 인터벌 응답 시그니처/캐시 경로 무변경 | 수동 검증 |
| Cache | 캐시 경로 자동 분리 — `data/kr_stock/005930.KS/1w.parquet` 신규 생성, `1d.parquet` 무영향 | 파일시스템 점검 |
| Visual | v0.7 인터벌 그룹 시각 (분/시간/일) 그대로, 신규 'longer' 그룹은 같은 컨벤션 | 수동 점검 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 High FR 구현 완료
- [ ] e2e 시나리오:
  - BTC/USDT 1w 클릭 → 약 100주(약 2년치) 봉 로딩, 정상 차트 렌더
  - BTC/USDT 1M 클릭 → 약 120월(10년치) 봉 로딩
  - 005930.KS(삼성전자) 1w 클릭 → 일봉 resample 결과로 주봉 100개 생성
  - 005930.KS 1M 클릭 → 월봉 약 120개
  - 인터벌 헤더에 `1분 5분 15분 | 1시간 4시간 | 일 | 주 월` 4 그룹으로 시각 분리
  - 신규 상장 종목(예: 1주일 미만 데이터) 으로 주봉 → 적절한 에러 메시지
- [ ] 백엔드 147 + 신규 resample 4건 = **151 PASSED**
- [ ] 프론트엔드 v0.7 정상 동작 (collapsible / ★ / ws-right toggle / signals limit / interval refetch)

### 4.2 Quality Criteria

- [ ] Gap Analysis 매치율 ≥ 90% (목표 95%+)
- [ ] 빌드/실행 시 에러 0건
- [ ] resample 결과가 ccxt 의 네이티브 1w/1M 결과와 비교했을 때 캔들 개수 ±2 이내 (주말/공휴일 차이)
- [ ] Frontend `1m` (분) ↔ `1M` (월) JS object key case-sensitive 명시적 검증 (`INTERVAL_LABELS['1m'].group === 'minute'` && `INTERVAL_LABELS['1M'].group === 'longer'`)

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| pandas `resample('M')` deprecated → `'ME'` (month end) 사용 권장 (pandas 2.x) | Medium | High | `'W-FRI'` (한국 주식 금요일 마감) + `'ME'` (month end) 사용. pandas 1.x 호환 별도 처리 |
| KR 종목 lookback 10년치 fetch 가 pykrx API rate limit 초과 | Medium | Medium | 일봉 단위로 chunked fetch, 백엔드 cache 적중 후 resample (재호출 시 캐시 사용) |
| `1m`(분) vs `1M`(월) JS object 키 충돌 의심 | Low | Low | JS 는 case-sensitive. 단, dict 자동완성 시 IDE 가 헷갈릴 수 있음 → 주석 명시 |
| Binance 의 `1M` 캔들 시작점이 매월 1일 vs ccxt timestamp UTC | Medium | Low | UTC 기준 통일 (기존 인트라데이도 UTC) — 한국 시간 표시는 frontend `toLocaleString('ko-KR')` 사용중 |
| 주/월봉 데이터로 기존 RSI/MA/MACD 지표가 의미있는 신호 생성하나? | Medium | Medium | 동일 공식 적용. 사용자가 RSI 14 (주봉 14주 = 약 3.5개월) 의미 직접 판단. 추후 v0.9에서 지표별 권장 인터벌 가이드 |
| KR 신규 상장 종목 데이터 부족으로 주/월봉 빈 응답 | Medium | Medium | DataSourceError 명확한 한국어 메시지, frontend dataState=error 표시 |
| pytest 신규 4건 추가 시 conftest fixture 호환성 | Low | Low | 기존 test_data_loader.py 패턴 재사용 |
| Frontend INTERVAL_GROUP_ORDER 'longer' 추가가 v0.7 wireframe 와 어긋남 | Low | High | 시각만 4 그룹 (`분 | 시간 | 일 | 주·월`) — 컴포넌트 구조 동일 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Selected |
|-------|:--------:|
| Starter | ☐ |
| **Dynamic** | ☑ |
| Enterprise | ☐ |

기존 사이클 동일.

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| KR 주/월봉 구현 방식 | 어댑터에서 일봉 → resample / DB 별도 저장 / 백엔드 resample 캐시 별도 | **어댑터 내 일봉 → resample, parquet 캐시 별도 키** | 기존 일봉 캐시 재사용, 추가 인프라 없음 |
| 주봉 마감 요일 | Sun-end / Mon-start / Fri-end | **Fri-end (`W-FRI`)** | 한국 주식 거래일 종료 = 금요일, KR 컨텍스트 일치 |
| 월봉 시작 시점 | 1일 시작 / 마지막 거래일 / Month-end | **Month-end (`ME`)** | pandas 권장, ccxt 와 timestamp 일치 |
| Crypto 주/월봉 | resample / Binance 네이티브 | **Binance 네이티브** | 정확도 + 단순성, ccxt 가 이미 지원 |
| 인터벌 그룹 4번째 | `longer` 신규 / `day` 그룹에 합치기 / `week+month` 별도 그룹 | **`longer` 신규** | 분/시간/일 시각 분리 컨벤션 유지, 그룹 4개 = `분, 시간, 일, 주·월` |
| Lookback 기본값 | 일봉 365 동일 / 인터벌별 자동 | **인터벌별 자동** | 주봉 365봉 = 7년, 월봉 120봉 = 10년 적정 |
| 신규 Frontend localStorage 키 | 추가 / 미추가 | **미추가** | 기존 4 키 그대로, 인터벌 자체는 차트 state 만 |
| 백엔드 신규 endpoint | 추가 / 기존 endpoint 확장 | **기존 endpoint 확장** | `/api/ohlcv` 등 query parameter 만 확장, 시그니처 무변경 |

### 6.3 폴더 구조 (변경분만)

```
backend/
├── core/
│   ├── types/
│   │   └── schemas.py          (확장: Interval enum + W1/MN1 2개)
│   └── adapters/
│       ├── binance_adapter.py  (확장: _INTERVAL_MAP +2)
│       └── krx_adapter.py      (확장: resample 로직 + _ensure_daily 제거 또는 분기)
├── api/
│   └── schemas.py              (확장: IntervalLiteral)
└── tests/
    └── test_data_loader.py     (확장: KR resample 테스트 4건)

Tradingmode/
├── app.jsx                     (확장: INTERVAL_LABELS +2, INTERVAL_GROUP_ORDER +1 그룹)
├── loader.js                   (확장: LOOKBACK_BY_INTERVAL +2)
└── styles.css                  (확장: .tf-group--longer 1줄)
```

---

## 7. Convention Prerequisites

### 7.1 Existing Conventions (재사용)

- [x] React 18 (CDN), Babel standalone
- [x] FastAPI + Pydantic v2
- [x] pandas-only 지표 (`_wilder_ewm` 등)
- [x] parquet 캐시 (경로 자동 분리)
- [x] OKLCH 다크 테마 + `.tf-group--*` 컨벤션 (v0.7)
- [x] Korean 라벨 우선 (v0.7)

### 7.2 Conventions to Define

| Category | New | Priority |
|----------|-----|:--------:|
| 백엔드 Interval enum 신규 멤버 | `W1 = "1w"`, `MN1 = "1M"` (월봉 = MN1, 분봉 = M1 와 구분) | High |
| KR resample 함수 위치 | `krx_adapter.py` 내부 `_resample_ohlcv(daily_df, freq)` private helper | Medium |
| pandas resample frequency string | 주봉 `'W-FRI'`, 월봉 `'ME'` (pandas 2.x) | Medium |
| Frontend group ID | `'longer'` (4번째 INTERVAL_GROUP_ORDER) | High |

### 7.3 Environment Variables (변경 없음)

기존 그대로. pykrx / ccxt 도 신규 환경변수 X.

### 7.4 Pipeline Integration

기존 v0.7 그대로.

---

## 8. Next Steps

1. [ ] 사용자 검토 및 Plan 승인
2. [ ] Design 문서 작성 (`/pdca design longer-intervals`)
   - 핵심: KR resample 정확한 pandas 코드, Interval enum 명명, frontend group 시각 와이어프레임, 에러 메시지 정확한 문구
3. [ ] 구현 (`/pdca do longer-intervals`)
4. [ ] Gap Analysis (`/pdca analyze longer-intervals`)

**예상 작업량**: ~3시간 (작은~중간 사이클)
- Phase A: 백엔드 enum + IntervalLiteral + Binance 어댑터 (30분)
- Phase B: KR 어댑터 resample + pytest 4건 (1.5시간)
- Phase C: Frontend INTERVAL_LABELS + INTERVAL_GROUP_ORDER + LOOKBACK + CSS (45분)
- 문서/검증 마진: 15분

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-05-05 | 초안 — 사용자 직접 지적("주/월봉 왜 없냐") 후 v0.8 사이클 시작. Crypto 네이티브 + KR resample 양 시장 대응. | 900033@interojo.com |
