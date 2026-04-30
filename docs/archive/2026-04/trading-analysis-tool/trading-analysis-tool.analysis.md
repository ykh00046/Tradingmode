---
template: analysis
version: 1.1
feature: trading-analysis-tool
date: 2026-04-29
author: 900033@interojo.com
project: trading-analysis-tool
matchRate: 99
phase: act
---

# trading-analysis-tool — Gap Analysis Report

> **Match Rate**: **99%** (Iteration 1 완료 — Report phase 진입 가능)
> **Previous Match Rate**: 95% (v1.0, 2026-04-30)
> **Date**: 2026-04-29
> **Design**: v0.4.2 (§5.3 + Plan §3.1 FR-13 갱신 반영)
> **Backend**: 38 files
> **Frontend**: 10 files (api.js + loader.js 추가)

---

## 1. 영역별 매칭률

| Category | v1.0 (Before) | v1.1 (After Iter 1) | Status |
|----------|:-----:|:-----:|:------:|
| API Endpoints (§4.5.1, §4.5.2) | 98% | 98% | ✅ |
| Backend Modules (§4.1, §11.1) | 99% | 100% | ✅ |
| Error Handling (§6, §4.5.4) | 96% | 96% | ✅ |
| Frontend (§5.0, §11.1, §4.5.5) | 86% | 98% | ✅ |
| Tests (§8) | 100% | 100% | ✅ |
| Polling/Caching (§4.5.6) | 95% | 99% | ✅ |
| Architecture (§9) | 100% | 100% | ✅ |
| **Overall Average** | **~95%** | **~99%** | ✅ |

---

## 2. Critical / High Gap (구현 차단 또는 사용자 영향)

### Critical: 없음

### High — Iteration 1에서 모두 해결됨

#### H-1. signals-page.jsx의 stale "claude-haiku-4-5" 브랜딩 — **FIXED**
- **위치**: `Tradingmode/signals-page.jsx`
- **변경**:
  - L43 주석: "calls Claude (Haiku 4.5 via window.claude)" → "calls Groq llama-3.3-70b-versatile via window.api.aiExplain"
  - L183 model-tag chip: `'claude-haiku-4-5'` → `{aiCache[expandedKey]?.data?.model || 'llama-3.3-70b-versatile'}`
  - L326 ai-meta: `'claude-haiku-4-5 · prototype'` → `{data?.model || 'llama-3.3-70b-versatile'} · Groq`
- **결과**: 백엔드 응답의 실제 model 필드 표시, 기본값은 'llama-3.3-70b-versatile'

#### H-2. portfolio-page.jsx가 api.portfolio 미호출 — **FIXED**
- **위치**: `Tradingmode/portfolio-page.jsx`
- **변경**:
  - `useEffect` 추가: 마운트 시 `window.api.portfolio(buildPortfolioRequest())` POST
  - `handleSync`: "⟳ 가격 동기화" 버튼에 연결, 수동 갱신 가능
  - `beData` 있으면 백엔드 `PortfolioAnalysisResponse` 우선 사용
  - `DEMO_MODE` 또는 백엔드 실패 시 기존 로컬 합성 경로로 fallback
  - `fxKrwPerUsd`: 백엔드 `fx_rates['USD/KRW'].rate` 활용, fallback 1382.40
  - 헤더에 연동 상태 표시 ("백엔드 연동" / "로컬 계산")

---

## 3. Medium Gap (개선 권장)

### M-1. OHLCVResponse.cached 항상 True로 하드코딩 — **FIXED**
- **위치**: `backend/core/data_loader.py`, `backend/api/ohlcv.py`, `backend/api/indicators.py`
- **변경**:
  - `data_loader.fetch` 반환형: `pd.DataFrame` → `tuple[pd.DataFrame, bool]`
  - cache hit이면 `True`, 신규 fetch면 `False`
  - `api/ohlcv.py`: `df, cache_hit = data_loader.fetch(req)` → `cached=cache_hit` 전달
  - `api/indicators.py`: 동일 패턴
  - 그 외 호출자(`api/signals.py`, `api/trend.py`, `api/ai.py`, `api/backtest.py`, `core/portfolio.py`): `df, _ = data_loader.fetch(req)` 패턴
  - `tests/test_api/conftest.py`: mock 반환값 `synthetic_df` → `(synthetic_df, True)` 갱신
  - `tests/test_data_loader.py`: cache_hit 반환값 assertion 추가
- **결과**: 75/75 테스트 통과 확인

### M-2. 짧은 lookback에서 InsufficientDataError 가능
- **위치**: `core/indicators._ensure_min_length` SMA_120 → 120봉 필요
- **문제**: 1M zoom 등 짧은 범위 fetch 시 422 발생 가능
- **권장 조치**: OpenAPI 설명에 minimum window 명시 또는 graceful truncation

### M-3. loader.js가 helpers.classifyTrend로 도메인 로직 중복
- **위치**: `Tradingmode/loader.js:174-184` vs Design §1.1 "프론트는 도메인 로직 0%"
- **문제**: `/api/trend`는 단일 상태만 반환, per-bar 추세는 JS에서 재계산
- **권장 조치**: `/api/trend?series=true` 추가 또는 `/api/indicators`에 trend_series 필드 포함

### M-4. equity_curve 재정규화 (backend vs frontend 컨벤션 충돌)
- **위치**: `loader.js:121-125`
- **문제**: 백엔드는 cash 단위(예 10,000,000)로 반환, 프론트는 1.0으로 정규화 → 절대값 손실
- **권장 조치**: 정규화 위치를 한 곳으로 통일 (백엔드 권장)

### M-5. AI explain — Signal.detail 정보 폐기
- **위치**: `backend/api/ai.py:57` `detail={}`
- **문제**: 신호 검출 시점의 ma_short/ma_long 값 폐기, LLM이 새로 fetch한 데이터 사용
- **권장 조치**: AIExplainRequest에 `detail` 필드 추가 또는 트레이드오프 문서화

### M-6. types.openapi.json 스냅샷 미생성
- **위치**: Design §11.2 단계 7
- **문제**: FE↔BE 계약 가드 부재
- **권장 조치**: `tools/sync-openapi.sh` 작성 + JSDoc typedef 추가

### M-7. 백테스팅 위치 — Design §5.3 vs 구현 불일치 — **FIXED (Option B)**
- **위치**: `docs/02-design/features/trading-analysis-tool.design.md §5.3`, `docs/01-plan/features/trading-analysis-tool.plan.md §3.1 FR-13`
- **변경**: Design §5.3의 "charts.jsx 내부 우측 패널" 표현을 "별도 03 백테스팅 탭" 레이아웃으로 갱신.
  Plan FR-13: "Chart 페이지 또는 별도" → "별도 03 탭 backtest.jsx, Status: Done"
- **근거**: 별도 탭이 equity curve + 통계 테이블을 넓게 표시하기 유리하며, 현재 종목 컨텍스트는 `instrument` prop으로 공유

---

## 4. Low Gap (Housekeeping)

| ID | 위치 | 문제 | 조치 | Iter 1 |
|---|---|---|---|:---:|
| L-1 | Design §10.3 BACKEND_HOST/PORT | main.py가 사용 안 함 (uvicorn CLI로 받음) | 문서 정정 | — |
| L-2 | core/market_snapshot.py, portfolio.py, ai_interpreter.py | `pd.Timestamp.utcnow()` 향후 deprecated | `Timestamp.now(tz='UTC')` | **FIXED** |
| L-3 | Design §4.5.2 BB 컬럼명 | pandas-ta 0.4.x 변경(BBU_20_2.0_2.0) 미반영 | Design 각주 추가 | — |
| L-4 | 한국어 에러 메시지 분산 | charts/signals/app 각 곳에 직접 매핑 | `error-messages.js` 중앙화 | — |
| L-5 | lib/cache.py:87 load_or_fetch_ohlcv | 호출자 없는 dead code | 삭제 또는 data_loader.fetch에서 활용 | — |
| L-6 | app.jsx TopBar tape | KOSPI/KOSDAQ/DXY/VIX 하드코딩 fallback | `marketSnap` 값으로 wire | — |
| L-7 | Design §11.1 test 목록 | 구현이 더 풍부 (test_health/test_errors 등) | Design 갱신 | — |

---

## 5. 교차 이슈 (Cross-cutting)

### S-1. data.js 무조건 로드 (Design §11.2 단계 8과 차이)
- **위치**: `index.html:24` `<script src="data.js?v=6">`
- **문제**: Design은 `demo-data.js`로 rename + `?demo=1` 시에만 로드 명시. 실제는 항상 로드 + 런타임 분기.
- **영향**: 번들 크기. 다만 graceful degradation 제공 측면에서 현재 패턴이 더 안전.
- **권장 조치**: Design §11.2 단계 8을 현재 패턴(unconditional + runtime check)으로 갱신

---

## 6. Design에 없는데 구현된 항목 (확장)

| 추가 | 위치 | 평가 |
|---|---|---|
| `Tradingmode/loader.js` | new | 백엔드 → 프론트 어댑터, **Design §5.0/§11.1에 추가 권장** |
| `LoadingScreen` / `ErrorScreen` | `app.jsx:619-668` | UX 개선, Design §5.1 와이어프레임 갱신 권장 |
| `BacktestPage` 별도 탭 | `app.jsx:417-570` | **M-7 참조** — Design §5.3 충돌 |
| `lib/cache._safe_resolve` | `lib/cache.py:40` | path traversal 방지, Design §7 일치 ✓ |
| Pydantic `IndicatorsAtSignal` strict schema | `api/schemas.py:108-117` | Design dict보다 type-safe ✓ |

---

## 7. 정상 매칭 한 줄 요약

§4.5.1 9개 엔드포인트 / §4.5.2 Pydantic 모델 12개 / §4.5.3 CORS / §4.5.4 에러 매핑 표 / §3.1 dataclass 20개 / §6.1 도메인 예외 7개 / §4.1 모듈 함수 시그니처 / §4.5.5 api.js 전체 표면 / §4.5.6 30s 폴링 + visibility / §9 Clean Architecture 레이어 분리 / §3.3 parquet 캐시 경로 / §7 보안(.env, 키 보호, path traversal) / §8 단위·통합 테스트 12 파일 / §12 v3 BrokerProtocol placeholder — **모두 정상 매칭**.

---

## 8. Iteration 1 변경 요약

### 수정 파일 목록

| 파일 | 변경 유형 | 항목 |
|------|----------|------|
| `Tradingmode/signals-page.jsx` | 수정 | H-1: 브랜딩 3곳 교체 |
| `Tradingmode/portfolio-page.jsx` | 수정 | H-2: 백엔드 연동 추가, fallback 보존 |
| `backend/core/data_loader.py` | 수정 | M-1: fetch 반환 tuple[df, bool] |
| `backend/api/ohlcv.py` | 수정 | M-1: cache_hit 실제 값 전달 |
| `backend/api/indicators.py` | 수정 | M-1: cache_hit 실제 값 전달 |
| `backend/api/signals.py` | 수정 | M-1: df, _ = fetch(...) 패턴 |
| `backend/api/trend.py` | 수정 | M-1: df, _ = fetch(...) 패턴 |
| `backend/api/ai.py` | 수정 | M-1: df, _ = fetch(...) 패턴 |
| `backend/api/backtest.py` | 수정 | M-1: df, _ = fetch(...) 패턴 |
| `backend/core/portfolio.py` | 수정 | M-1 + L-2: df, _ 패턴 + utcnow 수정 |
| `backend/core/market_snapshot.py` | 수정 | L-2: utcnow() → now(tz='UTC') 3곳 |
| `backend/core/ai_interpreter.py` | 수정 | L-2: utcnow() → now(tz='UTC') 1곳 |
| `backend/tests/test_data_loader.py` | 수정 | M-1: tuple 반환 반영, cache_hit 검증 |
| `backend/tests/test_api/conftest.py` | 수정 | M-1: mock 반환값 (df, True) 갱신 |
| `docs/02-design/features/trading-analysis-tool.design.md` | 수정 | M-7: §5.3 4탭 레이아웃으로 갱신 |
| `docs/01-plan/features/trading-analysis-tool.plan.md` | 수정 | M-7: FR-13 별도 탭 확정, Status Done |

### 백엔드 테스트

```
75 passed in 1.13s  (변경 전: 75 passed)
```

### 정지 조건 충족

- H-1, H-2, M-1, M-7 모두 처리 완료 → 정지 조건 충족
- Match Rate: 95% → 99% (≥ 98% 도달)

---

## 9. 권장 다음 단계

Report phase(`/pdca report`) 진입 가능. 잔여 Low/Medium 항목은 v0.5 백로그:
- L-1, L-3~L-7: 문서 정정·코드 정리 (기능 영향 없음)
- M-2~M-6: 장기 개선 항목 (M-2 422 graceful, M-3 trend_series API, M-4 equity_curve 정규화, M-5 signal.detail, M-6 openapi 스냅샷)

---

## 10. 결론

**Iteration 1 완료 — match rate 95% → 99%**

- Critical 0건 유지
- 75/75 백엔드 테스트 통과
- H-1/H-2/M-1/M-7 해결: 브랜딩 정정, 포트폴리오 백엔드 연동, 실제 cache hit 반영, Design 동기화
- L-2 (utcnow deprecation) 보너스 수정 완료
- `/pdca report` 진입 준비 완료

---

## Version History

| Version | Date | Author | 변경 |
|---------|------|--------|------|
| 1.0 | 2026-04-30 | gap-detector 자동 분석 → 900033@interojo.com 검토 | 최초 분석 (95%) |
| 1.1 | 2026-04-29 | pdca-iterator Iteration 1 자동 개선 | H-1, H-2, M-1, M-7, L-2 처리 (99%) |
