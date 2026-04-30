---
template: analysis
version: 1.0
feature: trading-analysis-tool
date: 2026-04-30
author: 900033@interojo.com
project: trading-analysis-tool
matchRate: 95
phase: check
---

# trading-analysis-tool — Gap Analysis Report

> **Match Rate**: **95%** (≥ 90% — Report phase 진입 가능)
> **Date**: 2026-04-30
> **Design**: v0.4.1 (1,761 lines)
> **Backend**: 38 files
> **Frontend**: 10 files (api.js + loader.js 추가)

---

## 1. 영역별 매칭률

| Category | Match Rate | Status |
|----------|:-----:|:------:|
| API Endpoints (§4.5.1, §4.5.2) | 98% | ✅ |
| Backend Modules (§4.1, §11.1) | 99% | ✅ |
| Error Handling (§6, §4.5.4) | 96% | ✅ |
| Frontend (§5.0, §11.1, §4.5.5) | 86% | ⚠️ |
| Tests (§8) | 100% | ✅ |
| Polling/Caching (§4.5.6) | 95% | ✅ |
| Architecture (§9) | 100% | ✅ |
| **Overall Average** | **~95%** | ✅ |

---

## 2. Critical / High Gap (구현 차단 또는 사용자 영향)

### Critical: 없음

### High

#### H-1. signals-page.jsx의 stale "claude-haiku-4-5" 브랜딩
- **위치**: `Tradingmode/signals-page.jsx:43` (주석), `:183` (model-tag chip), `:326` (ai-meta)
- **문제**: 실제 호출은 `window.api.aiExplain`(Groq llama-3.3-70b)를 거치지만 UI는 "claude-haiku-4-5" 표시. Design §5.5는 `llama-3.3-70b-versatile` 명시.
- **영향**: 사용자에게 잘못된 LLM 정보 노출
- **권장 조치**: hard-coded 문자열을 `resp.model` 또는 `llama-3.3-70b-versatile`로 교체

#### H-2. portfolio-page.jsx가 api.portfolio 미호출
- **위치**: `Tradingmode/portfolio-page.jsx:1-160` vs Design §11.2 단계 8, §5.0 매핑 표
- **문제**: 모든 포트폴리오 계산이 클라이언트에서 수행. `FX_KRW_PER_USD = 1382.40` 하드코딩, FxQuote 감사 로그 없음. 백엔드 endpoint는 완성·테스트 됐으나 호출 지점 부재.
- **영향**: 백엔드의 정확한 환율/추세/신호 집계 로직 미사용. CSV 업로드 미구현.
- **권장 조치**: `useEffect`에서 `MOCK_HOLDINGS`(또는 CSV 입력)을 `api.portfolio()`로 POST 후 응답 렌더, 합성 경로는 `DEMO_MODE`로 격리

---

## 3. Medium Gap (개선 권장)

### M-1. OHLCVResponse.cached 항상 True로 하드코딩
- **위치**: `backend/api/ohlcv.py:36`, `backend/api/indicators.py:37`
- **문제**: cache hit/miss 정보 손실. DataStatusBar의 "캐시 적중" 라벨이 신규 fetch에도 표시.
- **권장 조치**: `data_loader.fetch`가 `(df, cache_hit: bool)` 반환하도록 수정

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

### M-7. 백테스팅 위치 — Design §5.3 vs 구현 불일치 ⚠️
- **위치**: `app.jsx:819-822` (별도 탭) vs Design §5.3 ("charts.jsx 내부 우측 패널로 배치")
- **문제**: Design은 차트 컨텍스트 공유를 위해 통합 권장. 실제로는 별도 4번째 탭으로 분리.
- **권장 조치**: 두 옵션 중 선택 — (a) charts.jsx에 backtest 패널 통합, (b) Design §5.3 갱신하여 4탭 레이아웃 채택 명시

---

## 4. Low Gap (Housekeeping)

| ID | 위치 | 문제 | 조치 |
|---|---|---|---|
| L-1 | Design §10.3 BACKEND_HOST/PORT | main.py가 사용 안 함 (uvicorn CLI로 받음) | 문서 정정 |
| L-2 | core/market_snapshot.py:96 등 | `pd.Timestamp.utcnow()` 향후 deprecated | `Timestamp.now(tz='UTC')` |
| L-3 | Design §4.5.2 BB 컬럼명 | pandas-ta 0.4.x 변경(BBU_20_2.0_2.0) 미반영 | Design 각주 추가 |
| L-4 | 한국어 에러 메시지 분산 | charts/signals/app 각 곳에 직접 매핑 | `error-messages.js` 중앙화 |
| L-5 | lib/cache.py:87 load_or_fetch_ohlcv | 호출자 없는 dead code | 삭제 또는 data_loader.fetch에서 활용 |
| L-6 | app.jsx TopBar tape | KOSPI/KOSDAQ/DXY/VIX 하드코딩 fallback | `marketSnap` 값으로 wire |
| L-7 | Design §11.1 test 목록 | 구현이 더 풍부 (test_health/test_errors 등) | Design 갱신 |

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

## 8. 권장 진행 순서

### 즉시 (1시간 이내, ≥ 98% 목표)
1. **H-1 픽스**: signals-page.jsx claude-haiku-4-5 → llama-3.3-70b-versatile (5분)
2. **H-2 픽스**: portfolio-page.jsx에 api.portfolio 호출 추가 (40분)
3. **M-7 결정**: backtest 위치 통합 vs Design 갱신 (15분)

### 또는 Report로 진입 (95% ≥ 90%)
- 위 H/M 항목을 v0.5 백로그로 미루고 `/pdca report` 진입
- Critical 0건이므로 Report 단계 진행 가능

---

## 9. 결론

**전반적으로 Design에 충실한 구현 (95%)**. 백엔드는 Design을 거의 그대로 반영 (98~100%). 프론트엔드는 86% — H-1/H-2/M-7 세 항목이 주요 차이.

- ✅ Critical 0건 — 구현 차단 요소 없음
- ✅ 75/75 백엔드 테스트 통과
- ✅ 9 REST 엔드포인트 + Phase 9 end-to-end 검증 완료
- ⚠️ 프론트엔드 일부 영역(브랜딩·포트폴리오 호출·백테스팅 위치) 정합성 보강 필요

`/pdca iterate`로 자동 개선 1회 권장 — 95% → 98%+ 도달 후 `/pdca report` 진입이 이상적.

---

## Version History

| Version | Date | Author |
|---------|------|--------|
| 1.0 | 2026-04-30 | gap-detector 자동 분석 → 900033@interojo.com 검토 |
