---
template: design
version: 0.2
feature: improvement-plan
date: 2026-05-16
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.10.0
---

# improvement-plan Design Document

> **Summary**: `docs/improvement-plan.md`(Plan 기준)의 P0/P1/P2 항목을 어떻게
> 구현할지 구체화한다. 핵심은 P0 — "API 호출 → 실제 응답" 통합/회귀 테스트와
> 프론트엔드 스모크 테스트로 검증 레이어를 세우는 것. 신규 기능이 아니라
> **검증 인프라 + 기술 부채 정리**가 주 범위.
>
> **Project**: trading-analysis-tool · **Version**: 0.10.0 · **Date**: 2026-05-16
> **Builds on**: v0.4~v0.9 누적 + 2026-05-16 세션 버그 다수 수정
> **Plan basis**: `docs/improvement-plan.md` (PDCA 표준 경로 대신 사용자 지정 위치)

---

## 1. Overview

### 1.1 Goal

이번 사이클은 **기능 추가가 아니라 신뢰 기반 구축**이다. 2026-05-16 세션에서
드러난 패턴 — "기능은 만들어졌고 단위 테스트는 통과하는데 실제 사용 경로에서
실패" — 을 구조적으로 차단한다.

### 1.2 Design Principles

1. **대표 입력으로 검증** — 테스트는 happy-path 모형이 아니라 *실제 사용자가
   보내는 입력*(빌트인 전략 5종의 실제 식, 주/월봉 등)으로 호출한다.
2. **값 정확성까지** — `200 OK` / 응답 형태뿐 아니라 *수치 속성*을 단언한다.
3. **오프라인 결정성** — 외부 데이터(Binance/pykrx) 없이 고정 합성 데이터로
   재현 가능하게 한다 (`patch_fetch` 패턴 재사용).
4. **회귀 우선** — 세션 버그 9건을 각각 재현하는 회귀 테스트를 먼저 만든다.
5. **부채 정리는 P0 이후** — 검증 레이어가 없으면 P1/P2 작업이 같은 함정을
   반복한다.

### 1.3 Scope / Non-goals

- **In**: P0(통합·회귀·스모크 테스트), P1-1(지표 패리티 골든 테스트),
  P2-1~5 기능 개선 설계.
- **Out (이번 사이클 비대상)**: P1-2 빌드 파이프라인은 설계 스케치만 — 프로덕션
  전환 결정 시 별도 사이클. 신규 지표/시장 추가 없음.

---

## 2. 진단 근거 — 왜 기존 테스트가 못 잡았나

| 버그 | 누락 원인 | 검증 담당 |
|------|-----------|-----------|
| Strategy Coach `and`/`or` | `test_strategy.py`의 `_BASE_REQUEST`가 `buy_when: "SMA_20 > SMA_60"` — **단일 조건**이라 `and` 평가 경로 미진입 | P0-1 (R-1·R-2) |
| MACD 시그널선 시드 | 시그널선 *값*을 수치 검증하는 단언 없음 | P0-1 (R-4) |
| KR 주/월봉 tz | `download()`에 naive `start` 직접 전달 — 실제 API 경로(tz-aware)를 안 탐 | P0-1 (R-3, 어댑터 레벨) |
| 차트/워치리스트 UI | JSX 컴포넌트·렌더 검증 0건 (프론트 테스트 `loader.test.mjs` 1개뿐) | P0-2 (스모크) |

→ 인프라(`client` TestClient, `conftest.py`, `patch_fetch`)는 이미 있다.
**부족한 것은 "대표 입력 커버리지 + 값 단언 + 프론트 렌더 검증"**이다.

---

## 3. P0-1 — 통합 / 회귀 테스트 설계

### 3.1 위치 / 재사용

- 기존 `backend/tests/` 인프라 재사용 — **신규 픽스처 없음**:
  - `tests/test_api/` — `client`(TestClient) + `patch_fetch`(7개 라우트의
    `data_loader.fetch` 일괄 교체) + `synthetic_df`.
  - `tests/conftest.py` — `trending_up_df` / `golden_cross_df` / `sideways_df`
    / `short_df` 등 합성 OHLCV 픽스처를 그대로 쓴다.
- 신규 파일:
  - `tests/test_api/test_regression.py` — API 레벨 회귀 (R-1·R-2·R-4·R-5).
  - `tests/test_data_loader.py` 확장 — 어댑터 레벨 회귀 (R-3).

> **검증 v0.2 — 중요**: `patch_fetch`는 `data_loader.fetch`를 *통째로* 교체하므로
> `krx_adapter`의 resample 로직이 실행되지 않는다. 따라서 **R-3(KR 주/월봉 tz
> 버그)은 `/api/ohlcv` + `patch_fetch`로 못 잡는다** — 어댑터 레벨로 분리 설계.

### 3.2 핵심 시나리오

| ID | 레벨 | 대상 | 단언 |
|----|------|------|------|
| R-1 | API (`patch_fetch`) | `/api/strategy/backtest` — 빌트인 5종 실제 식 (parametrize) | 각 식이 400 없이 실행, `is_result` 수치 존재 |
| R-2 | API | 동 — `and`/`or`/`not` 식 직접 | element-wise 평가 (entry/exit Series 길이·dtype) |
| R-3 | **어댑터** | `data_loader.fetch` — `1w`/`1M` + **tz-aware `start`** | resample 후 candles 반환, TypeError 없음 |
| R-4 | API (`patch_fetch`) | `/api/indicators` | MACD 시그널선 null-prefix 길이가 워밍업과 일치 (정확 인덱스는 구현 시 확인) |
| R-5 | API | `/api/signals` | 신호 kind·timestamp 정합 |

- **R-3 설계 상세**: `krx_adapter._try_pykrx`(/`_try_fdr`)를 monkeypatch로
  고정 일봉 DataFrame을 반환하게 한 뒤, `data_loader.fetch`를 `interval='1w'`
  + `converters.ms_to_ts`가 만드는 **tz-aware `pd.Timestamp` start**로 호출 →
  resample 트림(`resampled.index >= start`)이 TypeError 없이 통과하는지 단언.
  (이 경로가 2026-05-16 세션 tz 버그의 실제 위치.)
- **대표-입력 원칙**: R-1은 빌트인 템플릿 5종의 *실제* `buy_when`/`sell_when`
  문자열을 `pytest.mark.parametrize`로 전수.

### 3.3 완료 기준 (DoD)

- 백엔드 회귀 3종 — 전략 `and`/`or` 평가(R-1·R-2) · KR 주/월봉 tz(R-3) ·
  MACD 시그널선(R-4) — 각각 회귀 테스트 존재 + PASS.
- 빌트인 전략 5종 backtest 통합 테스트 PASS.
- `pytest -q` 전체 GREEN, 신규 테스트가 CI에서 실행.

> UI 버그(워치리스트 겹침·상단바·차트 마커)는 백엔드 회귀로 만들 수 없다 —
> P0-2 프론트 스모크가 담당(§4).

---

## 4. P0-2 — 프론트엔드 스모크 테스트 설계

### 4.1 위치 / 도구

- Playwright (Python). **현재 `.venv`에 임시 설치만 돼 있고 의존성 매니페스트에
  없음 → 재현·CI 불가.** 신규 `backend/requirements-dev.txt`(또는 동등 파일)에
  `playwright` 명시 + 셋업 단계에 `playwright install chromium` 추가 (§11 Risk).
- 신규: `Tradingmode/tests/e2e/smoke.py` + 실행 가이드 `Tradingmode/tests/e2e/README.md`.
- 데모 모드(`?demo=1`)로 구동 — 백엔드 의존 없이 결정적·고속.

### 4.2 시나리오

```
loadAll(?demo=1) → pageerror 리스너 등록
for tab in [차트분석, 매매신호, 백테스팅, 포트폴리오, Strategy Coach]:
    click(tab) → 대표 엘리먼트 가시성 확인 → pageerror 누적 0 단언
핵심 인터랙션:
    워치리스트 행 클릭(종목 전환) · 지표 토글 ON/OFF · 인터벌 전환(일↔주)
    · 신호 피드 행 펼치기
```

- 백엔드 의존 플로우(실데이터 백테스트)는 스모크 범위 밖 → P0-1에서 커버.

### 4.3 완료 기준

- 5탭 × `pageerror == 0`.
- 핵심 인터랙션 4종 무오류 동작.
- 단일 명령(`python tests/e2e/smoke.py`)으로 실행, exit code로 성공/실패.

---

## 5. P1-1 — 지표 이중 구현 일원화 설계

### 5.1 문제

지표를 `data.js`(프론트 합성, 데모)와 백엔드 `indicators.py`(pandas-ta,
라이브)가 **각각** 계산 → 드리프트 위험. 실제 사례: MACD 시드 버그가
`data.js`에만 존재했음(세션에서 수정 완료).

### 5.2 설계 결정 — 골든값 테스트 (option B)

데모 모드의 "오프라인·무백엔드" 속성을 유지하기 위해 **재작성(option A)
대신 골든값 고정(option B)** 을 택한다.

0. **선행 (검증 v0.2)**: `data.js`의 `window.MarketData.helpers`에
   `rpb`(+`wilderRma`) export 추가 — 현재 `helpers`에 `sma/ema/rsi/macd/
   bbands`만 노출돼 `rpb`를 골든 테스트로 직접 호출할 수 없다.
1. 백엔드가 고정 시드 OHLCV에 대해 지표 기준값을 산출 → `Tradingmode/tests/
   fixtures/indicator-golden.json` 으로 저장 (1회 생성).
2. 신규 `Tradingmode/tests/indicators.test.mjs` (node --test) — `vm`으로
   `data.js`를 로드(기존 `loader.test.mjs` 패턴)해 `helpers.{sma,ema,rsi,
   macd,bbands,rpb}`를 동일 입력으로 실행, 골든값과 비교.
3. 허용 오차: 상대오차 < 0.1%.

### 5.3 완료 기준

- 6개 지표 전부 골든값 대비 오차 < 0.1%.
- 드리프트 발생 시 CI가 빨갛게 됨.

> 참고: 볼린저밴드는 양쪽 모두 모집단 표준편차(ddof=0)로 *현재는 일치* —
> 골든 테스트는 *미래 드리프트 방지*가 목적.

---

## 6. P1-2 — 빌드 파이프라인 (설계 스케치, 후순위)

- 현재: 인-브라우저 Babel(`@babel/standalone`) — 앱이 콘솔 경고를 띄움.
- 방향: esbuild로 `.jsx` 사전 컴파일 → 단일 번들. `index.html`의
  `type="text/babel"` 스크립트를 빌드 산출물로 교체.
- **이번 사이클 비대상** — 프로토타입 단계에선 후순위. 프로덕션 전환을
  결정할 때 별도 plan/design 사이클로 착수.

---

## 7. P2 — 기능 개선 설계 (스케치)

| ID | 항목 | 설계 요지 |
|----|------|-----------|
| P2-1 | 컨플루언스 점수 | 신호 발생 봉에서 추세(MA)·모멘텀(RSI/MACD)·변동성(BB) 3범주 동의 수 0~3 집계 → 마커 크기/투명도 매핑. `signalRegimeFit` 옆에 `signalConfluence(kind, ind, i)` 헬퍼 |
| P2-2 | 밴드 상호배타 토글 | 볼린저밴드 ↔ RPB 동시 ON 시 한쪽 자동 투명도 강하, 또는 라디오 토글. `INDICATOR_GROUPS`에 `exclusiveWith` 메타 |
| P2-3 | 거래량 지표 | OBV를 `indicators.py` + `data.js`에 추가, 차트 거래량 패널에 오버레이. 빠진 유일 범주 |
| P2-4 | 정밀 패닝 | `pan()`에 step 인자 — 키보드 ←/→ = 1봉, Shift+←/→ = 현행 25% |
| P2-5 | AI 키 안내 | `groq_configured=false` 시 Strategy Coach·신호 AI 해설에 "GROQ_API_KEY 설정 안내" 인라인 배너 |

- P2는 각 항목 착수 시 본 설계를 세부 design으로 확장한다 (스케치 단계).

---

## 8. 디렉터리 구조 변경

```
backend/tests/test_api/test_regression.py        [신규] API 레벨 회귀 R-1/2/4/5
backend/tests/test_data_loader.py                [수정] R-3 — KR 주/월봉 tz (어댑터 레벨)
backend/requirements-dev.txt                     [신규] playwright 등 개발 의존성
Tradingmode/data.js                              [수정] helpers에 rpb/wilderRma export
Tradingmode/tests/e2e/smoke.py                   [신규] Playwright 스모크
Tradingmode/tests/e2e/README.md                  [신규] 실행 가이드
Tradingmode/tests/indicators.test.mjs            [신규] 지표 패리티
Tradingmode/tests/fixtures/indicator-golden.json [신규] 골든값
```
> `golden_ohlcv` 신규 픽스처는 불필요 — `tests/conftest.py`의 기존 합성
> 픽스처(`trending_up_df` 등) 재사용 (검증 v0.2 / F4).

---

## 9. 검증 기준 (사이클 DoD)

- P0-1 (백엔드): `and`/`or`·KR tz·MACD 회귀 + 빌트인 5종 통합 PASS, `pytest` 전체 GREEN.
- P0-2 (프론트): 5탭 스모크 `pageerror 0` + 인터랙션 4종 PASS.
- P1-1: 지표 6종 골든 패리티 오차 < 0.1% (`rpb` export 선행).
- 종합: CI 한 번에 `pytest` + `node --test` + `smoke.py` 실행 가능.

---

## 10. Implementation Guide

| Phase | 범위 | 예상 |
|-------|------|------|
| **Phase 1** | P0-1 — `golden_ohlcv` 픽스처 + `test_regression.py` (R-1~R-5) | 중 |
| **Phase 2** | P0-2 — `smoke.py` 5탭 + 인터랙션 | 소~중 |
| **Phase 3** | P1-1 — 골든값 생성 + `indicators.test.mjs` | 중 |
| **Phase 4** | P2-1~5 — 각 항목 세부 design 후 구현 | 항목별 |
| (별도) | P1-2 빌드 — 프로덕션 전환 결정 시 | — |

순서 근거: **Phase 1~2(P0)가 안전망**이므로 최우선. Phase 3 이후 작업은
P0 테스트가 회귀를 잡아주는 상태에서 진행.

---

## 11. Risks

- **외부 데이터 비결정성** — pykrx/Binance 응답이 매일 바뀜 → 통합 테스트는
  반드시 `patch_fetch` + `golden_ohlcv`로 격리. 라이브 호출 테스트 금지.
- **Playwright 의존성** — 현재 `.venv`에 임시 설치만 됨. `requirements-dev.txt`에
  `playwright` 명시 + CI 셋업에 `playwright install chromium` 단계 필요 —
  없으면 재현·CI 불가.
- **골든값 노후화** — 지표 정의를 의도적으로 바꿀 땐 골든 파일도 함께 갱신
  (PR 리뷰 체크리스트에 명시).

---

## Version History

| 버전 | 날짜 | 변경 |
|------|------|------|
| 0.1 | 2026-05-16 | 최초 작성 — `improvement-plan.md` 기반 P0/P1/P2 구현 설계 |
| 0.2 | 2026-05-16 | 설계 검증 반영 (F1~F7) — **F1** R-3을 어댑터 레벨로 재설계(`patch_fetch`가 `krx_adapter` resample을 우회) · **F2** `rpb` export 선행 명시 · **F3** 버그를 P0-1(백엔드)/P0-2(프론트)로 분류 · **F4** 신규 `golden_ohlcv` 폐기, 기존 픽스처 재사용 · **F5** Playwright 의존성 `requirements-dev.txt` 관리 명시 · **F6** MACD 인덱스 하드코딩 완화 · **F7** `project_version` 확인(현재 0.9.0의 다음 마이너 0.10.0) |
