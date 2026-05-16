# 빌드 파이프라인 (build-pipeline)

| 항목 | 값 |
|------|-----|
| Feature | `build-pipeline` |
| 사이클 | v0.11.0 |
| Phase | Plan |
| 작성일 | 2026-05-17 |
| 출처 | improvement-plan 사이클 P1-2 (별도 사이클로 분리 결정) |

---

## 1. 배경 / 문제

프론트엔드(`Tradingmode/`)는 빌드 단계 없이 동작한다 — 브라우저가 매
로드마다 JSX를 즉석에서 변환한다.

`index.html`이 로드하는 것:

- React 18.3.1 · ReactDOM 18.3.1 · **@babel/standalone 7.29.0** — 전부
  unpkg CDN (SRI 해시 포함)
- 평문 JS 4개 — `api.js` · `data.js` · `loader.js` · `lib/storage.js`
  (각각 `window.*` 전역 설정)
- JSX 6개 — `tweaks-panel` · `charts` · `signals-page` · `portfolio-page`
  · `strategy-coach-page` · `app` (`<script type="text/babel">`, 총 ~4,240줄)

### 증상

| # | 문제 |
|---|------|
| 1 | 콘솔 경고 — *"You are using the in-browser Babel transformer. Be sure to precompile your scripts for production."* (앱 스스로 프로덕션 부적합을 알림) |
| 2 | 매 페이지 로드마다 ~4,240줄 JSX를 브라우저에서 재변환 — 첫 페인트 지연 |
| 3 | React **development 빌드**를 배포 (`react.development.js`) — 더 크고 느림 |
| 4 | 미니파이·트리셰이킹·데드코드 제거 없음 |
| 5 | 의존성이 URL로만 고정 — lockfile 없음, npm 공급망 검증 불가 |
| 6 | 캐시 무효화가 수동 (`?v=13` 쿼리스트링을 직접 증가) |

improvement-plan 사이클의 P1-2 항목. "프로토타입 단계에선 후순위 — 프로덕션
전환을 결정할 때 착수"로 분류됐고, 검증 레이어(P0+P1)가 완성된 지금
별도 사이클로 진행한다.

---

## 2. 목표 (성공 기준)

1. `index.html`이 **사전 컴파일된 산출물**을 로드 — `@babel/standalone`
   제거, `type="text/babel"` 제거. 브라우저 내 변환 0건.
2. 콘솔에서 Babel 경고 사라짐.
3. React를 **production 빌드**로 제공 (`react.production.min.js` 또는
   번들 내 포함).
4. 빌드가 **단일 명령** (`npm run build`) — 산출물은 정적 파일, 어떤
   정적 호스트에도 배포 가능.
5. **재현 가능한 설치** — `package.json` + lockfile.
6. **동작 회귀 0건** — 빌드 산출물 대상으로 스모크 테스트 10/10 유지.
7. 개발 워크플로 보존 — watch/serve 모드 제공(이상적).

---

## 3. 범위

### In

- `Tradingmode/` 프론트엔드 빌드 도구 도입
- `index.html` 스크립트 로딩 방식 전환
- `package.json` · lockfile · 빌드 스크립트
- 스모크 테스트를 빌드 산출물 대상으로 실행하도록 조정

### Out

- 백엔드(`backend/` FastAPI) — 무변경
- TypeScript 전환
- 번들링이 강제하지 않는 범위의 컴포넌트 리팩터
- 신규 기능

---

## 4. 기능 요구사항 (FR)

| FR | 내용 |
|----|------|
| FR-01 | 프론트엔드에 `package.json` + lockfile 추가, 빌드 의존성 명시 |
| FR-02 | JSX 6개를 사전 컴파일 — 브라우저 내 Babel 변환 제거 |
| FR-03 | `index.html`에서 `@babel/standalone` CDN + 모든 `type="text/babel"` 제거 |
| FR-04 | React/ReactDOM을 production 빌드로 전환 |
| FR-05 | `npm run build` 단일 명령으로 정적 산출물 생성 |
| FR-06 | `npm run dev`(또는 watch) 개발 모드 — 소스 수정 시 자동 재컴파일 |
| FR-07 | 스모크 테스트(`tests/e2e/smoke.py`)가 빌드 산출물을 대상으로 통과 |
| FR-08 | 캐시 무효화 — 콘텐츠 해시 파일명 또는 빌드 단위 버전 (수동 `?v=` 대체) |

---

## 5. 제약 / 리스크

| # | 항목 |
|---|------|
| C-1 | **전역 스코프 의존** — 컴포넌트는 `import`/`export` 없이 공유 전역 스코프에서 서로를 참조(`App`이 `Charts`를, `Charts`가 helper를 bare 이름으로). Babel이 모든 `text/babel` 스크립트를 같은 스코프로 합쳐 동작. 번들러는 이 교차 참조를 깨면 안 됨. |
| C-2 | **로드 순서 의존** — 평문 JS가 `window.MarketData`/`loader`/`api`/`tmStorage`를 설정한 뒤 JSX가 읽음. 11개 스크립트 순서가 유지돼야 함. |
| C-3 | `import`/`require` 사용처 0건 — 현재 ESM 모듈 그래프가 전혀 없음. 진정한 번들링은 entry point + import 도입(별도 리팩터)을 요구. |
| R-1 | 스모크 테스트가 **소스가 아닌 빌드 산출물**을 대상으로 돌아야 함 — 안 그러면 빌드 깨짐을 못 잡음. |
| R-2 | React를 CDN external로 둘지 번들에 포함할지 결정 필요(설계 단계). |

---

## 6. 접근 방식 옵션 (설계 단계에서 확정)

| 옵션 | 도구 | 성격 | 트레이드오프 |
|------|------|------|--------------|
| **A** | esbuild | 경량. 단일 바이너리, 매우 빠름 | 의존성 최소. dev 서버는 별도(기존 정적 서버 + watch) |
| B | Vite | dev 서버 + HMR + prod 빌드 | 개발 경험 우수하나 ESM 모듈 그래프 전제 — 전역 스코프 구조와 충돌, import 리팩터 동반 |

esbuild 내부 세부 옵션:

- **A-최소** — JSX 6개를 *파일 단위*로 JSX→JS 변환만(번들링 X).
  `index.html`의 11개 스크립트 로드 순서·전역 스코프 구조 그대로 유지,
  `type="text/babel"`만 평문 `<script>`로 교체. **소스 변경 0**, 최저 리스크.
  문제(브라우저 내 변환)는 완전히 제거하되 구조는 안 건드림.
- A-번들 — entry point + import 도입해 단일 파일로 번들. 트리셰이킹
  이득은 있으나 전 파일 import 리팩터 동반.

### 권장

**옵션 A-최소 (esbuild 파일 단위 변환)**.

근거: Vite의 가치는 HMR + ESM인데, 이 앱은 전역 스코프 구조에 규모가 작다.
실제 통증(브라우저 내 Babel 변환·dev React·경고)은 A-최소로 전부 해소되며
소스 변경이 0이라 회귀 리스크가 가장 낮다. ESM 리팩터 + Vite + 트리셰이킹은
개발 경험이 병목이 될 때 후속 사이클로.

---

## 7. 권장 진행 순서 / 예상 규모

1. `package.json` + esbuild 의존성 + 빌드/watch 스크립트 (FR-01·05·06)
2. JSX 사전 컴파일 + `index.html` 전환 + React production (FR-02·03·04)
3. 캐시 무효화 + 스모크 테스트를 산출물 대상으로 조정 (FR-07·08)

규모: **작음~중** · 예상 ~2h · 백엔드 무영향.

---

## 8. 한 줄 요약

브라우저 내 Babel을 사전 컴파일로 대체한다 — esbuild 파일 단위 변환으로
**소스 변경 없이** 프로덕션 적합성(변환 0·미니파이·prod React)을 확보하고,
검증은 스모크 테스트를 빌드 산출물 대상으로 돌려 보장한다.
