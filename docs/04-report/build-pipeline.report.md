# 빌드 파이프라인 — 완료 보고서 (build-pipeline)

| 항목 | 값 |
|------|-----|
| Feature | `build-pipeline` |
| 사이클 | v0.11.0 |
| Phase | Completed |
| 작성일 | 2026-05-17 |
| Match Rate | **98%** |
| 기간 | 1일 (2026-05-17, 단일 세션) |

---

## 1. Executive Summary

프론트엔드의 브라우저 내 `@babel/standalone` 변환을 **esbuild 사전 컴파일**로
대체했다. improvement-plan 사이클 P1-2가 별도 사이클로 분리된 것.

- 매 로드마다 ~4,240줄 JSX를 재변환하던 구조 → 빌드 시 1회 컴파일
- 콘솔 Babel 경고 소멸 · React production 빌드 적용 · 재현 가능 설치(lockfile)
- 접근 **esbuild A-최소** — 비번들 파일 단위 변환으로 전역 스코프 + 로드
  순서 구조 보존, 소스는 2줄만 수정
- **부수 성과**: 원본의 잠재적 `const` 스코프 취약점 발견·수정

8 FR 전부 구현, 스모크 12/12, page error 0, console warning 0.

---

## 2. 사이클 타임라인

| 단계 | 산출 |
|------|------|
| Plan | `build-pipeline.plan.md` — 진단·8 FR·접근 옵션(esbuild vs Vite)·esbuild A-최소 권장 |
| Design v0.1 | esbuild A-최소 확정 — `build.mjs`·10 설계결정·7 테스트케이스 |
| Design v0.2 | 코드 사실 대조 검증 — F1~F5 보강 (T-04 재정의, `import shutil`, `npm install` 선행 등) |
| Do | Phase A/B/C 구현 — `package.json`·`build.mjs`·`smoke.py` 통합 |
| Design v0.3 | 구현 중 발견 반영 — `const`/`var` 스코프 충돌 §13 |
| Check | 갭 분석 98% — Critical/High/Medium 0, Low 2(조치 불요) |
| Report | 본 문서 |

---

## 3. 산출물

### 신규

| 파일 | 내용 |
|------|------|
| `Tradingmode/package.json` | esbuild `^0.25` · react · react-dom (devDeps), `build`/`dev` 스크립트, `type:module` |
| `Tradingmode/package-lock.json` | 재현 가능 설치 — esbuild 0.25.12 고정 |
| `Tradingmode/build.mjs` | 빌드 스크립트 — esbuild 비번들 변환 + `copyStatic` + `genIndexHtml`, `--dev` 분기 |
| `docs/01-plan/.../build-pipeline.plan.md` | Plan |
| `docs/02-design/.../build-pipeline.design.md` | Design v0.3 |
| `docs/03-analysis/build-pipeline.analysis.md` | 갭 분석 |
| `docs/04-report/build-pipeline.report.md` | 본 문서 |

### 수정

| 파일 | 변경 |
|------|------|
| `charts.jsx` · `app.jsx` | React-훅 구조분해 `const`→`var` (각 1줄, §6 참조) |
| `tests/e2e/smoke.py` | 빌드 산출물 대상으로 전환 — `import shutil`, `npm install`+`build` 선행, 서빙 디렉터리 `build/`, subprocess UTF-8 인코딩 |

### 빌드 산출물 (`build/`, gitignore)

`index.html` + 10 `.js`(6 JSX 변환 + 4 평문 JS) + `vendor/react*.js` +
`styles.css` — 자기완결적 정적 배포 단위.

---

## 4. 기능 요구사항 (8/8)

| FR | 결과 |
|----|------|
| FR-01 | ✅ `package.json` + lockfile |
| FR-02 | ✅ JSX 6 사전 컴파일 |
| FR-03 | ✅ `@babel/standalone`·`text/babel` 제거 (`build/index.html` 검증) |
| FR-04 | ✅ React production 빌드 vendor |
| FR-05 | ✅ `npm run build` 단일 명령 |
| FR-06 | ✅ `npm run dev` watch + serve :5173 |
| FR-07 | ✅ 스모크가 빌드 산출물 대상 — 12/12 |
| FR-08 | ✅ `BUILD_ID` 캐시 무효화 |

---

## 5. 핵심 설계 결정

| D | 결정 | 근거 |
|---|------|------|
| D2 | `--bundle` 미사용, 파일 단위 변환 | 전역 스코프·로드 순서 보존 → 소스 거의 무변경 |
| D3 | `minifyIdentifiers: false` | 컴포넌트 교차 전역 참조 보호 |
| D4 | React npm 설치 후 UMD를 `build/vendor/`로 복사 | prod React + 동일 출처(SRI 불요) + lockfile 재현성, 빌드 시 네트워크 0 |
| D5 | `build/` gitignore | 빌드마다 `?v=` 갱신해도 git churn 0 |
| D11 | (v0.3) `const`→`var` 2줄 | §6 — 비번들 다중 스크립트 스코프 충돌 해소 |

esbuild A-최소를 선택한 이유: Vite의 가치는 HMR + ESM인데 이 앱은 전역
스코프 구조에 규모가 작다. 실제 통증(브라우저 내 변환·dev React·경고)은
A-최소로 전부 해소되며 회귀 표면이 최소다. ESM 리팩터 + Vite + 트리셰이킹은
개발 경험이 병목이 될 때 후속 사이클로.

---

## 6. 발견된 취약점 — `const` 스코프 충돌

### 증상

Phase C 첫 스모크에서 `Identifier 'useState' has already been declared`.

### 근본 원인

`app.jsx`·`charts.jsx`가 **둘 다** 최상위에
`const { useState, useMemo, useRef, useEffect, useCallback } = React`를 선언.
별도 classic 스크립트로 로드되면 전역 어휘 스코프를 공유하므로 `const`
재선언은 `SyntaxError`다. 원본 앱은 `@babel/standalone`의 기본 ES5
다운컴파일이 `const`→`var`로 낮춰주어 *우연히* 동작했다 (`var` 재선언은
합법). 페이지 파일 3개가 훅을 별칭으로 쓴 것이 작성자가 이 스코프 공유를
인지했다는 방증 — 단 `app`/`charts`는 누락.

### 조치

전수 조사로 충돌이 `charts ∩ app`의 훅 5개뿐임을 확인 → 두 줄 `const`→`var`
변경. 페이지 파일의 기존 별칭 패턴과 동일한 의도이며, 원본 Babel-ES5 런타임
스코핑을 정확히 재현한다.

### 교훈

> 빌드 단계 도입은 *우연히 동작하던* 코드를 드러낸다. "테스트 통과 ≠ 기능
> 동작"의 사촌 격 — **"실행됨 ≠ 견고함"**. 빌드 파이프라인은 이런 잠재
> 취약점을 표면화하는 가치도 있다.

---

## 7. 품질 지표

| 지표 | 값 |
|------|-----|
| Match Rate | 98% |
| Critical / High / Medium 갭 | 0 / 0 / 0 |
| Low 갭 | 2 (둘 다 조치 불요 — 정당한 생략·설계 누락 보완) |
| 스모크 테스트 | 12/12 (npm install·build 2 + 5탭 + 인터랙션 4 + 종합) |
| page error / console warning | 0 / 0 |
| 소스 변경 | 2줄 (`const`→`var`) + `smoke.py` 통합 |
| 백엔드 영향 | 없음 |

---

## 8. 프로세스 교훈

1. **설계 사전 검증의 가치** — v0.2 코드 대조에서 F1~F5 5건을 사전 포착
   (smoke.py에 console 리스너 없음, `shutil` 미import, `npm install`
   선행 누락 등). 구현 단계 시행착오를 줄였다.
2. **설계는 구현 중 보정될 수 있다** — `const`/`var` 충돌은 사전 검증으로도
   못 잡은 런타임 의존성. 설계를 v0.3으로 정직하게 보정하고 §13에 기록.
3. **검증 레이어가 일했다** — improvement-plan 사이클이 구축한 스모크
   테스트가 이번 빌드 전환의 회귀를 즉시 포착. P0 투자 회수.
4. **루트 자원 재확인** — `.gitignore`를 새로 만들기 전 루트가 이미
   `node_modules/`·`build/`를 무시함을 확인 → 중복 회피 (G-1).

---

## 9. 로드맵 (후속)

| 항목 | 트리거 |
|------|--------|
| ESM 모듈 그래프 전환 + Vite + HMR | 개발 경험이 병목이 될 때 (A-번들, 별도 사이클) |
| 트리셰이킹 · 콘텐츠 해시 파일명 | 번들 크기·캐시 정밀도가 문제될 때 |
| dev watch가 `index.html`/`styles.css` 감지 | 편집 빈도가 높아질 때 (build.mjs watch 확장) |
| `app.jsx`/`charts.jsx`의 전역 스코프 의존 제거 | ESM 전환 시 자연 해소 |

---

## 10. 결론

빌드 파이프라인 사이클 **완료**. improvement-plan P1-2가 검증 레이어 위에서
안전하게 구현됐다. 프로토타입의 마지막 프로덕션 부적합 요소(브라우저 내
Babel)가 제거됐고, 그 과정에서 잠재 취약점 하나를 추가로 해소했다.

`v0.4~v0.11` 누적 **7 사이클** — Critical/High 0건 연속.
