# 빌드 파이프라인 — 설계 (build-pipeline)

| 항목 | 값 |
|------|-----|
| Feature | `build-pipeline` |
| 사이클 | v0.11.0 |
| Phase | Design |
| 버전 | v0.3 (구현 중 발견 반영) |
| 작성일 | 2026-05-17 |
| Plan | `docs/01-plan/features/build-pipeline.plan.md` |

---

## 1. 개요 / 접근 확정

Plan 권장안 **esbuild A-최소**(파일 단위 JSX→JS 변환, 번들링 없음)를 확정.

핵심: esbuild는 `--bundle` 없이도 각 파일에 로더(jsx)와 트랜스폼을 적용한다 —
`--bundle`은 모듈 해석·연결만 제어한다. 따라서 **파일 단위 변환**은 6개 JSX를
각각 독립 트랜스파일하여, 현재의 *전역 스코프 + 로드 순서* 구조를 그대로
보존한다. 컴포넌트 6개 + 평문 JS 4개는 **거의 무변경** — 단,
`charts.jsx`·`app.jsx` 각 1줄(`const`→`var`)만 수정 (→ §13 v0.3 발견).

### 환경 (검증 완료)

- Node `v22.20.0` · npm `10.9.3` — 설치 가능
- 프론트엔드 = `Tradingmode/` · `index.html`은 CRLF 줄바꿈
- `index.html` 로드 순서: 인라인 `API_BASE_URL` → React/ReactDOM/Babel CDN
  → `api.js` → `data.js` → `loader.js` → `lib/storage.js` →
  6 JSX(`type="text/babel"`) · 모두 `?v=13` 쿼리
- 6 JSX 전부 `React` 전역 참조 · `import`/`require` 0건
- `smoke.py`: `FRONTEND_DIR`(=`Tradingmode/`)를 `http.server`로 `:5599` 서빙,
  `cwd` 한 곳(L68)이 서빙 디렉터리. 리스너는 `page.on("pageerror")`만(L81) —
  `console` 리스너·`shutil` import 없음 (→ F1·F3)
- `import.meta.dirname` 동작 확인 (Node ≥20.11; v22.20에서 `string` 반환)
- React UMD 경로 — 현 `index.html`이 `react@18.3.1/umd/react.development.js`
  를 사용 → `node_modules/react/umd/react.production.min.js` 존재 보장

---

## 2. 아키텍처 / 디렉터리 레이아웃

```
Tradingmode/
  index.html            ← 소스 템플릿 (무변경 — 빌드 입력 겸 no-build 폴백)
  *.jsx  *.js  styles.css  lib/storage.js   ← 소스 (무변경)
  package.json          ← 신규
  package-lock.json     ← 신규 (npm install 산출)
  build.mjs             ← 신규 — 빌드 스크립트
  .gitignore            ← 신규 — node_modules/, build/
  node_modules/         ← gitignore
  build/                ← gitignore — 생성물, 배포 단위
    index.html          ← 소스 index.html을 변환 생성
    app.js  charts.js  signals-page.js  portfolio-page.js
    strategy-coach-page.js  tweaks-panel.js     ← 6 JSX 트랜스파일
    api.js  data.js  loader.js  lib/storage.js  ← 4 평문 JS 패스스루
    styles.css                                 ← 복사
    vendor/
      react.production.min.js                  ← node_modules에서 복사
      react-dom.production.min.js
```

`build/`는 자기완결적 정적 사이트 — 어떤 정적 호스트에도 통째 배포.
`build/`가 gitignore이므로 빌드마다 `index.html`의 `?v=` 쿼리가 바뀌어도
git churn 없음.

---

## 3. 빌드 스크립트 — `build.mjs`

ESM Node 스크립트. esbuild JS API 사용. `--dev` 플래그로 모드 분기.

```js
import * as esbuild from 'esbuild';
import { cpSync, mkdirSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const DEV      = process.argv.includes('--dev');
const ROOT     = import.meta.dirname;                  // Tradingmode/
const OUT      = join(ROOT, 'build');
const BUILD_ID = DEV ? 'dev' : Date.now().toString(36);
const VARIANT  = DEV ? 'development' : 'production.min';

const ENTRIES = [
  'api.js', 'data.js', 'loader.js', 'lib/storage.js',
  'tweaks-panel.jsx', 'charts.jsx', 'signals-page.jsx',
  'portfolio-page.jsx', 'strategy-coach-page.jsx', 'app.jsx',
];

const buildOpts = {
  entryPoints: ENTRIES.map((f) => join(ROOT, f)),
  outdir: OUT,
  outbase: ROOT,                       // lib/storage.js → build/lib/storage.js
  loader: { '.jsx': 'jsx' },
  jsx: 'transform',                    // classic → React.createElement (전역)
  minifyWhitespace: !DEV,
  minifySyntax:     !DEV,
  minifyIdentifiers: false,            // ★ 전역 식별자 보존 (C-1)
  logLevel: 'info',
};

function copyStatic() {
  cpSync(join(ROOT, 'styles.css'), join(OUT, 'styles.css'));
  mkdirSync(join(OUT, 'vendor'), { recursive: true });
  for (const pkg of ['react', 'react-dom']) {
    cpSync(join(ROOT, 'node_modules', pkg, 'umd', `${pkg}.${VARIANT}.js`),
           join(OUT, 'vendor', `${pkg}.${VARIANT}.js`));
  }
}

function genIndexHtml() {
  let html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  html = html
    .replace(/^.*@babel\/standalone.*\r?\n/m, '')                        // Babel 제거
    .replace(/<script src="https:\/\/unpkg\.com\/react@[^"]*"[^>]*><\/script>/,
             `<script src="vendor/react.${VARIANT}.js"></script>`)
    .replace(/<script src="https:\/\/unpkg\.com\/react-dom@[^"]*"[^>]*><\/script>/,
             `<script src="vendor/react-dom.${VARIANT}.js"></script>`)
    .replace(/<script type="text\/babel" src="([^"]+)\.jsx\?v=\d+">/g,    // text/babel→plain
             `<script src="$1.js?v=${BUILD_ID}">`)
    .replace(/\?v=\d+/g, `?v=${BUILD_ID}`);                              // 캐시 무효화
  writeFileSync(join(OUT, 'index.html'), html);
}

rmSync(OUT, { recursive: true, force: true });
if (DEV) {
  const ctx = await esbuild.context(buildOpts);
  await ctx.watch();
  copyStatic(); genIndexHtml();
  await ctx.serve({ servedir: OUT, port: 5173 });
  console.log('dev server → http://localhost:5173');
} else {
  await esbuild.build(buildOpts);
  copyStatic(); genIndexHtml();
  console.log(`build complete → build/  (v=${BUILD_ID})`);
}
```

> **D-핵심 — `minifyIdentifiers: false`.** 컴포넌트는 `import` 없이 공유
> 전역 스코프에서 bare 이름으로 교차 참조한다(C-1). 비번들 스크립트에서
> esbuild는 전역 식별자 리네이밍을 보수적으로 처리하지만, 명시적으로
> 꺼서 `App`↔`Charts`↔helper 교차 참조가 절대 깨지지 않도록 보장한다.
> 화이트스페이스·구문 미니파이는 유지 — 크기 이득 대부분 확보.

---

## 4. `package.json`

```json
{
  "name": "tradingmode-frontend",
  "private": true,
  "version": "0.11.0",
  "type": "module",
  "scripts": {
    "build": "node build.mjs",
    "dev": "node build.mjs --dev"
  },
  "devDependencies": {
    "esbuild": "^0.25.0",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  }
}
```

`react`/`react-dom`은 **빌드 시 UMD 파일을 vendor로 복사**하는 용도로만 설치
(소스가 import하지 않음) → devDependencies. `npm install`이 `package-lock.json`
생성 → 재현 가능 설치(FR-01).

---

## 5. `index.html` 변환 규칙

`build.mjs:genIndexHtml()`이 소스 `index.html`(불변)을 읽어 `build/index.html`
생성. 5개 문자열 치환:

| # | 원본 | 결과 |
|---|------|------|
| 1 | `@babel/standalone` `<script>` 줄 | 삭제 |
| 2 | `unpkg.com/react@...development.js` | `vendor/react.production.min.js` (SRI·crossorigin 제거 — 동일 출처) |
| 3 | `unpkg.com/react-dom@...development.js` | `vendor/react-dom.production.min.js` |
| 4 | `<script type="text/babel" src="X.jsx?v=13">` | `<script src="X.js?v=<BUILD_ID>">` (6개) |
| 5 | 잔여 `?v=13` (styles.css·api/data/loader.js·lib/storage.js) | `?v=<BUILD_ID>` |

결과: `build/index.html`은 브라우저 내 변환 0건, prod React, 동일 출처 vendor.

---

## 6. 개발 모드 (`npm run dev`)

`build.mjs --dev` → esbuild `context()` + `.watch()` + `.serve()`.

- 미니파이 없음, dev React(`react.development.js`) vendor
- 소스 `.jsx`/`.js` 수정 시 esbuild가 자동 재컴파일 (브라우저 새로고침)
- `http://localhost:5173`에서 `build/` 서빙
- 백엔드는 별도 `:8000` (`window.API_BASE_URL` 불변)
- **개발 모드에도 브라우저 내 Babel 없음** — JSX는 dev에서도 사전 컴파일

> 한계: dev에서 `index.html`/`styles.css` 자체 수정은 watch가 잡지 않음
> (esbuild watch는 JS 엔트리만). 빌드 재실행 필요 — 인라인 주석으로 명시.

---

## 7. 스모크 테스트 통합 (FR-07)

`smoke.py`를 빌드 산출물 대상으로 전환 — 3곳 수정:

1. **import 추가**: `import shutil` (현재 미import — F3).
2. **사전 설치 + 빌드**: 서버 기동 전 `npm install`(idempotent — 충족 시
   빠름) 후 `npm run build` 실행. `node_modules/`는 gitignore이므로 신선한
   클론에선 없음 → 설치 선행 필수. 둘 중 하나라도 실패 시 즉시
   `check(..., False)` 후 종료 → 설치·빌드 깨짐도 스모크가 포착.
   - Windows: `npm` 실행파일은 `npm.cmd` — `shutil.which("npm")`로 해석.
3. **서빙 디렉터리**: `http.server`의 `cwd`(L68)를 `FRONTEND_DIR` →
   `FRONTEND_DIR / "build"`로 변경. 나머지 테스트 로직(5탭·인터랙션 4종·
   `pageerror` 0)은 불변.

```python
import shutil   # 파일 상단

BUILD_DIR = FRONTEND_DIR / "build"
npm = shutil.which("npm") or "npm"
for step in (["install"], ["run", "build"]):
    r = subprocess.run([npm, *step], cwd=str(FRONTEND_DIR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        check(f"npm {' '.join(step)}", False, r.stderr.strip()[-200:])
        return 1
    check(f"npm {' '.join(step)}", True)
# ... http.server cwd=str(BUILD_DIR)
```

---

## 8. 설계 결정

| ID | 결정 | 근거 |
|----|------|------|
| D1 | esbuild (Vite 아님) | Plan A-최소. 단일 의존성, ESM 리팩터 불요 |
| D2 | `--bundle` 미사용, 파일 단위 변환 | 전역 스코프·로드 순서 보존 → 소스 무변경 |
| D3 | `minifyIdentifiers: false` | 전역 교차 참조(C-1) 보호 — 리네이밍 금지 |
| D4 | React를 npm 설치 후 UMD를 `build/vendor/`로 복사 | prod React + 동일 출처(SRI 불요) + lockfile 재현성. 빌드 시 네트워크 불요 |
| D5 | `build/index.html` 생성, `build/` gitignore | 빌드마다 `?v=` 갱신해도 git churn 0 |
| D6 | 캐시 무효화 = 단일 `BUILD_ID` 쿼리 (timestamp base36) | Plan FR-08 "빌드 단위 버전". 콘텐츠 해시보다 단순, metafile 불요 |
| D7 | 소스 `index.html` 유지 (no-build 폴백) | 빌드 입력 템플릿 겸용. 배포물은 `build/index.html` |
| D8 | `smoke.py`가 `npm run build` 선행 후 `build/` 서빙 | FR-07 — 빌드 깨짐까지 포착 |
| D9 | `react`/`react-dom`을 devDependencies | 소스가 import하지 않음 — 빌드 시 vendor 복사용 |
| D10 | 6 JSX + 4 평문 JS **거의 무변경** (`charts.jsx`·`app.jsx` 각 1줄 `const`→`var` — §13) | A-최소의 핵심 — 회귀 표면 최소화 |

---

## 9. FR 매핑

| FR | 설계 반영 |
|----|-----------|
| FR-01 | §4 `package.json` + `npm install` → `package-lock.json` |
| FR-02 | §3 esbuild가 6 JSX 트랜스파일 |
| FR-03 | §5 치환 1·4 — `@babel/standalone`·`text/babel` 제거 |
| FR-04 | §3 `copyStatic` + D4 — prod React vendor |
| FR-05 | §4 `npm run build` |
| FR-06 | §6 `npm run dev` watch + serve |
| FR-07 | §7 `smoke.py` 빌드 산출물 대상 |
| FR-08 | §3·§5 치환 5 + D6 — `BUILD_ID` 쿼리 |

---

## 10. 테스트 케이스

| T | 검증 | 방법 |
|---|------|------|
| T-01 | `npm run build` exit 0, `build/`에 `index.html`+10 `.js`+`vendor/`(2)+`styles.css` 존재 | 빌드 후 파일 확인 |
| T-02 | `build/index.html`에 `@babel/standalone`·`type="text/babel"` 0건, `vendor/react.production.min.js` 참조 | 문자열 검사 |
| T-03 | 5탭 렌더 + `pageerror` 0 (빌드 산출물 대상) | `smoke.py` 10/10 |
| T-04 | in-browser Babel 경고 없음 | **T-02에 의해 구조적 보장** — 경고는 `@babel/standalone`이 발생시키며, §5 치환1로 스크립트 자체가 제거되면 경고는 발생 불가. (smoke.py에 `console` 리스너 없음 — 별도 캡처 불요) |
| T-05 | 교차 전역 참조 정상 — `App`이 `Charts`/helper 발견, 앱 렌더 | T-03에 포함 |
| T-06 | `npm run dev` 빌드+서빙, 소스 수정 시 재컴파일 | 수동 확인 |
| T-07 | 재빌드 시 `BUILD_ID` 쿼리 변경 | 연속 2회 빌드 비교 |

---

## 11. 구현 순서

**Phase A — 빌드 기반** (FR-01·02·05)
`.gitignore` → `package.json` → `npm install` → `build.mjs`(prod 경로) →
`npm run build`로 `build/*.js` 생성 확인 (T-01).

**Phase B — index.html + React prod** (FR-03·04·08)
`copyStatic`(vendor) + `genIndexHtml` 완성 → `build/index.html` 검증
(T-02). 브라우저로 `build/` 직접 열어 콘솔 청결 확인 (T-04).

**Phase C — dev 모드 + 스모크** (FR-06·07)
`--dev` 경로(watch+serve) → `smoke.py`에 선행 빌드 + `build/` 서빙 →
`smoke.py` 10/10 (T-03·05). `npm run dev` 수동 확인 (T-06).

규모: 작음~중 · ~2h · 백엔드 무영향.

---

## 12. 리스크 / 미해결

| # | 항목 | 대응 |
|---|------|------|
| R-1 | esbuild 비번들 미니파이가 전역명을 건드릴 가능성 | esbuild는 비-ESM(import/export 0건) 스크립트의 최상위 식별자를 전역 스코프로 간주해 리네이밍하지 않음 — 우리 6 JSX가 정확히 이 경우. D3 `minifyIdentifiers: false`는 **이를 명시적으로 한 번 더 보장**(belt-and-suspenders). Phase A에서 T-05로 실측 확인 |
| R-2 | esbuild `^0.25` API(`context`/`serve`/`outbase`) 버전차 | Phase A에서 설치 버전 고정·`package-lock.json` 커밋 |
| R-3 | Windows `npm.cmd` 경로 | §7 `shutil.which("npm")` |
| R-4 | dev watch가 `index.html`/`styles.css` 미감지 | §6 명시 — 해당 수정 시 재빌드. 후속 개선 여지 |
| R-5 | 신선한 클론에 `node_modules/` 부재 → `npm run build` 실패 | §7 — `smoke.py`가 `npm install` 선행 |
| 비대상 | ESM 모듈 그래프 전환 + Vite + 트리셰이킹 + 콘텐츠 해시 | 개발 경험 병목 시 별도 사이클 (A-번들) |

### v0.2 검증 보강 (코드 사실 대조)

| F | 발견 | 조치 |
|---|------|------|
| F1 | T-04가 "smoke의 console 캡처"를 전제했으나 `smoke.py`엔 `console` 리스너 없음(`pageerror`만) | T-04를 T-02에 의한 구조적 보장으로 재정의 — 별도 캡처 불요 |
| F2 | `import.meta.dirname`(Node ≥20.11) 사용 — 미검증 | v22.20에서 `string` 반환 실측 확인 |
| F3 | §7 코드가 `shutil` 사용하나 `smoke.py`에 미import | `import shutil` 추가 명시 |
| F4 | `node_modules/react/umd/...` 경로 가정 | 현 `index.html`의 `react@18.3.1/umd/...` 사용으로 경로 보장 확인 |
| F5 | `smoke.py`가 `npm run build`만 — `node_modules` 부재 시 실패 | `npm install` 선행 단계 추가 (R-5) |

---

## 13. v0.3 — 구현 중 발견 (const/var 스코프 충돌)

### 증상

Phase C 첫 스모크에서 `build/index.html` 로드 시
**`Identifier 'useState' has already been declared`** — 앱 렌더 실패.

### 근본 원인

설계 v0.1~v0.2의 "소스 무변경" 전제가 **불완전**했다. 원본 앱이 다중 스크립트
전역 스코프에서 동작한 진짜 이유:

- 브라우저 내 `@babel/standalone`은 기본 프리셋이 **ES5로 다운컴파일** —
  `const`/`let` → `var`. (DOM 검사로 확인: Babel 주입 스크립트에
  `_typeof`·`ownKeys`·`_extends` ES5 헬퍼 존재.)
- `app.jsx`·`charts.jsx`는 **둘 다** 최상위에
  `const { useState, useMemo, useRef, useEffect, useCallback } = React`
  를 선언. 별도 classic 스크립트로 로드되면 전역 어휘 스코프를 공유 —
  `const` 재선언은 `SyntaxError`지만 **`var` 재선언은 합법**(같은 값).
- 즉 원본은 *Babel의 `const`→`var` 강등 덕분에* 우연히 동작했다.
  페이지 파일 3개가 훅을 별칭(`useStateP`/`useStateS`/`useStateSC`)으로
  쓴 것이 이 스코프 공유를 작성자가 인지했다는 방증 — 단 `app`/`charts`는
  누락.

esbuild는 `const`/`let` → `var` 강등을 **지원하지 않는다**
(`supported:{'const-and-let':false}` 시도 → "Transforming const … not
supported yet"). `target:es5`는 `async/await` 미강등으로 불가.

### 충돌 범위 (전수 확인)

10개 소스의 최상위 `const`/`let`/`class` 전수 조사:

- 평문 JS 4개 — IIFE 래핑, 최상위 어휘 선언 **0**
- 페이지 3개 — 훅 별칭 처리, 고유 상수만
- **유일 충돌** = `useState`·`useMemo`·`useRef`·`useEffect`·`useCallback`
  (`charts.jsx` ∩ `app.jsx`). 그 외 교차 중복 0.

### 조치 (D11)

`charts.jsx:4`·`app.jsx:4`의 React-훅 구조분해를 **`const` → `var`**로
변경 (각 1줄 + 설명 주석 3줄). `var`는 파일 내 의미가 동일하고, 스크립트 간
재선언이 합법 — 원본 Babel-ES5 런타임 스코핑을 정확히 재현. esbuild는 `var`를
그대로 출력. 회귀 표면 = 2줄.

> 이것이 "소스 무변경"보다 정직한 수정 — 원본은 *우연히* 동작했고, 실제
> 빌드 환경에선 이 잠재 취약점이 드러난다. 페이지 파일의 기존 별칭 패턴과
> 동일한 의도.

### 결과

수정 후 `npm run build` 성공, `build/` 로드 시 page error 0 · console
warning 0 (Babel 경고 소멸 = T-04 확인), 스모크 **12/12**
(npm install·build 2 + 기존 10).
