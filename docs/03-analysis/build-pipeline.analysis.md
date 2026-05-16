# 빌드 파이프라인 — 갭 분석 (build-pipeline)

| 항목 | 값 |
|------|-----|
| Feature | `build-pipeline` |
| 사이클 | v0.11.0 |
| Phase | Check (Gap Analysis) |
| 버전 | v1.0 |
| 작성일 | 2026-05-17 |
| 대조 | Design v0.3 ↔ Do 구현 |
| **Match Rate** | **98%** |

---

## 1. Executive Summary

Design v0.3의 in-scope 항목이 **전부 구현·검증**됐다. 8개 FR · 11개 설계
결정(D1~D11) · 7개 테스트 케이스(T-01~T-07) 모두 충족. 설계가 구현 중
v0.3으로 자체 보정(const/var 발견)됐기에 설계↔구현 불일치가 거의 없다.

- **Critical / High / Medium: 0건**
- **Low: 2건** — 둘 다 구현이 설계보다 정확하거나 동등 (G-1 정당한 생략,
  G-2 설계 누락 보완)

검증 자산: 스모크 **12/12**, page error 0, console warning 0.
Match Rate 98% ≥ 90% → iterate 불요 → `/pdca report` 진행 가능.

---

## 2. 기능 요구사항 검증 (8/8)

| FR | 설계 | 구현 | 상태 |
|----|------|------|------|
| FR-01 | `package.json` + lockfile | `Tradingmode/package.json` + `package-lock.json` (esbuild 0.25.12) | ✅ |
| FR-02 | JSX 6 사전 컴파일 | `build.mjs` esbuild 비번들 변환 → `build/{6}.js` | ✅ |
| FR-03 | `@babel/standalone`·`text/babel` 제거 | `genIndexHtml` 치환 — `build/index.html` babel 0건 검증 | ✅ |
| FR-04 | React production | `copyStatic` → `build/vendor/react.production.min.js` | ✅ |
| FR-05 | `npm run build` 단일 명령 | `"build": "node build.mjs"` | ✅ |
| FR-06 | `npm run dev` watch | `"dev": "node build.mjs --dev"` — watch+serve :5173, 재컴파일 실측 | ✅ |
| FR-07 | 스모크 산출물 대상 | `smoke.py` 빌드 선행 + `build/` 서빙, 12/12 | ✅ |
| FR-08 | 캐시 무효화 | `BUILD_ID`(base36 timestamp) 쿼리, 빌드마다 변경 실측 | ✅ |

---

## 3. 설계 결정 검증 (11/11)

| D | 결정 | 구현 확인 |
|---|------|-----------|
| D1 | esbuild | `devDependencies.esbuild ^0.25` → 0.25.12 | ✅ |
| D2 | 비번들 파일 단위 변환 | `build.mjs` `bundle` 미설정, 10 엔트리 독립 변환 | ✅ |
| D3 | `minifyIdentifiers: false` | `build.mjs:39` | ✅ |
| D4 | React npm→`build/vendor/` | `copyStatic` `node_modules/{pkg}/umd/{pkg}.{VARIANT}.js` | ✅ |
| D5 | `build/` gitignore | 루트 `.gitignore`가 `build/` 포함 — `git check-ignore` 확인 | ✅ |
| D6 | `BUILD_ID` 쿼리 | `Date.now().toString(36)` `build.mjs:20` | ✅ |
| D7 | 소스 `index.html` 유지 | 무변경, 빌드 입력 템플릿으로 사용 | ✅ |
| D8 | `smoke.py` 빌드 선행 | `npm install`+`npm run build` 선행 후 `build/` 서빙 | ✅ |
| D9 | react/react-dom devDeps | `package.json devDependencies` | ✅ |
| D10 | 거의 무변경 (2줄) | `charts.jsx`·`app.jsx` 각 `const`→`var` 1줄 | ✅ |
| D11 | (v0.3) `const`→`var` | §13 — 구현·검증 완료 | ✅ |

---

## 4. 테스트 케이스 (7/7)

| T | 검증 | 결과 |
|---|------|------|
| T-01 | `npm run build` 산출 — `build/`에 index.html+10 `.js`+vendor 2+styles.css | ✅ 14파일 |
| T-02 | `build/index.html` babel 0건, `vendor/react.production.min.js` 참조 | ✅ |
| T-03 | 5탭 렌더 + `pageerror` 0 (빌드 산출물 대상) | ✅ 스모크 12/12 |
| T-04 | in-browser Babel 경고 없음 | ✅ console warning 0 (T-02 구조적 보장 + 실측) |
| T-05 | 교차 전역 참조 — `App`이 `Charts`/helper 발견 | ✅ 앱 렌더 정상 |
| T-06 | `npm run dev` watch 재컴파일 | ✅ `[watch] build` 실측 |
| T-07 | 재빌드 시 `BUILD_ID` 변경 | ✅ `mp8jilfb` → `mp8jxkmn` |

---

## 5. 갭 목록

### G-1 (Low) — `Tradingmode/.gitignore` 미생성

- **설계**: §2 디렉터리 레이아웃·§11 Phase A가 `Tradingmode/.gitignore`
  (`node_modules/`·`build/`)를 신규 파일로 명시.
- **구현**: 생성하지 않음 — 루트 `.gitignore`가 `node_modules/`·`build/`를
  이미 전역 패턴으로 무시. `git check-ignore`로 둘 다 무시 확인.
- **판정**: 정당한 생략 (DRY) — 기능적으로 완전 충족. 중복 파일 회피.
- **조치**: 불요. 설계 의도(빌드 산출물 비추적)는 달성.

### G-2 (Low) — `smoke.py` subprocess UTF-8 인코딩 (설계 누락 보완)

- **설계**: §7 코드 스케치가 `subprocess.run(..., text=True)`만 명시.
- **구현**: `encoding="utf-8", errors="replace"` 추가 — esbuild가 출력하는
  비-cp949 문자(`⚡`/`→`)가 Windows 기본 코덱(cp949)에서 `UnicodeDecodeError`
  유발. 첫 실행 시 발견·수정.
- **판정**: 설계 누락을 구현이 보완 — 구현이 설계보다 정확.
- **조치**: 불요. 설계에 반영하려면 §7에 인코딩 명시(후속 문서 정리 시).

---

## 6. 설계 외 성과

- **잠재 취약점 발견·수정**: `app.jsx`·`charts.jsx`의 최상위 `const` 훅
  구조분해는 원본이 `@babel/standalone`의 ES5 다운컴파일 덕에 *우연히*
  동작하던 것. 빌드 파이프라인 전환이 이 취약점을 드러냈고 v0.3에서
  근본 수정(`const`→`var`, 페이지 파일의 기존 별칭 패턴과 동일 의도).
- 검증 레이어가 의도대로 동작 — 스모크 테스트가 빌드 깨짐(`npm install`/
  `build` 실패)과 런타임 회귀를 모두 포착하는 구조.

---

## 7. 결론 / 다음 단계

| | |
|---|---|
| Match Rate | **98%** |
| Critical / High / Medium | 0 / 0 / 0 |
| Low | 2 (G-1 정당한 생략, G-2 설계 누락 보완 — 둘 다 조치 불요) |
| 검증 | 스모크 12/12 · page error 0 · console warning 0 |

iterate 불요 (98% ≥ 90%) → **`/pdca report`** 진행 가능.

비대상(설계 §12): ESM 모듈 그래프 전환 + Vite + 트리셰이킹 + 콘텐츠 해시 —
개발 경험 병목 시 별도 사이클(A-번들).
