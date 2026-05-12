---
template: design
version: 0.1
feature: ux-improvements
date: 2026-05-02
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.7.0
---

# ux-improvements Design Document

> **Summary**: Plan v1.2 의 10 FRs(우선순위 1+2)를 실제 컴포넌트·CSS·localStorage 키 단위까지 구체화. Frontend(`Tradingmode/`) 단일 영역, 백엔드 무영향. 한국어 인터벌 라벨 + Zoom 차트 우상단 칩 + 우측 패널 3 섹션 collapsible + 지표 4 그룹 + TopBar 1280/1024 반응형 축약 + Watchlist ★ + 신호 limit slider.
>
> **Project**: trading-analysis-tool · **Version**: 0.7.0 · **Date**: 2026-05-02

---

## 1. Overview

### 1.1 Goal
v0.7.0 사이클은 **사용 편의성** 단일 카테고리 — 추가 기능 0건, 기존 화면의 정보 밀도/가독성 재배치. 백엔드 147 테스트 무영향.

### 1.2 Design Principles
1. **Stateless first** — 모든 UI 상태는 localStorage에만 (서버 동기화 X).
2. **Backward compat** — localStorage 키 누락 시 기본값 = 기존 UX와 동일.
3. **Frontend only** — `backend/` 디렉토리 변경 0건, 기존 REST 호출 시그니처 무변경.
4. **CSS-driven transitions** — JS 애니메이션 없음, `transition: all 200ms ease`로 통일.
5. **Pine 스타일 유지** — 색상 토큰/폰트 변경 X. 그룹 구분은 옅은 배경/구분선만.

---

## 2. Architecture

### 2.1 변경 영역 매핑

```
Tradingmode/
├── index.html              (캐시 버스트 v8 → v9, lib/storage.js script 등록)
├── lib/storage.js          ✨ NEW — localStorage 헬퍼 (prefix wrapper, plain JS IIFE)
├── app.jsx                 (수정: TopBar 반응형, Watchlist ★, RightPanel 3섹션 collapsible,
│                            지표 그룹 헤더, RecentSignals limit, Interval 그룹 구분선, Zoom 칩 우상단 이동)
├── charts.jsx              (변경 없음 — 차트 SVG 자체는 유지)
└── styles.css              (확장: ~120 lines 신규 클래스)
```

> 정정: Interval/Zoom 칩은 `charts.jsx`(`CandleChart` SVG 전용)가 아니라 **`app.jsx` `ChartPage` 내부 `.ih-right`**(line 229–245)에 위치. v0.1 초안의 `charts.jsx` 명시는 사실 오류. v0.2에서 모두 `app.jsx`로 정정.

### 2.2 Component 변경 요약

| 컴포넌트 | 위치 (검증) | 변경 |
|---|---|---|
| `TopBar` | app.jsx | `useViewportWidth()` Hook + `formatPriceCompact()` |
| `WatchlistRow` | app.jsx (`.wl-row`) | `★` 버튼 추가 + `.wl-row.is-fav` state class + 정렬 로직 |
| `RightPanel` | app.jsx (`.right-panel` line 333) | 기존 `.panel-section` 3개에 collapsible 동작 추가 (클래스 신설 X) |
| `IndicatorToggles` | app.jsx (`.ind-list` line 351) | 4 그룹 헤더(`.ind-group-header`) 삽입, 기존 `<IndToggle>` 재배열만 |
| `RecentSignals` | app.jsx (`.signal-feed` line 370) | limit `<select>` + slice + max-height 적용 |
| Interval 그룹 | app.jsx (`.tf-group` line 230) | 라벨 한글화 + 그룹 구분선 + `.tf-group--minute/hour/day` modifier |
| Zoom 그룹 | app.jsx (`.tf-group` line 235) | `.ih-right` 에서 `.chart-pane` 내부로 이동, `.zoom-fab` 우상단 absolute |

---

## 3. Data Model

### 3.1 localStorage Schema (4 keys, prefix `tradingmode-`)

| Key | Type | Default | 용도 |
|---|---|---|---|
| `tradingmode-ws-right-collapsed` | `{[sectionId]: boolean}` | `{}` | 우측 패널 3 섹션 펼침 상태 (key 없음 = 펼침) |
| `tradingmode-wl-favs` | `string[]` | `[]` | 즐겨찾기 심볼 (예: `["BTC/USDT", "AAPL"]`) |
| `tradingmode-signals-limit` | `number` | `20` | 최근 신호 표시 개수 (10/20/50/100) |
| `tradingmode-ind-groups-collapsed` | `{[groupId]: boolean}` | `{}` | 지표 그룹 헤더 접힘 상태 |

**Section ID 규약** (right-panel — 기존 클래스 `.right-panel` line 334 그대로 사용; v0.1 초안의 `ws-right` 키 이름은 *localStorage 키* 한정이며 DOM 클래스가 아님):
- `current-status` — 현재 상태
- `indicators-overlay` — 지표 오버레이
- `recent-signals` — 최근 신호

**Group ID 규약** (indicators):
- `trend` — 추세 (MA20/50/200, ICH_*)
- `volatility` — 변동성 (BB_*, ATR_*)
- `leading` — 선행 (RPB_* 12 컬럼)
- `display` — 표시 (Volume, Signals 마커)

### 3.2 INTERVAL_LABELS 매핑

```js
// charts.jsx
const INTERVAL_LABELS = {
  '1m':  { label: '1분',   group: 'minute' },
  '5m':  { label: '5분',   group: 'minute' },
  '15m': { label: '15분',  group: 'minute' },
  '1h':  { label: '1시간', group: 'hour'   },
  '4h':  { label: '4시간', group: 'hour'   },
  '1d':  { label: '일',    group: 'day'    },
};
```

**그룹 시각**: `minute` / `hour` / `day` 사이에 `<div class="tf-divider"/>` 삽입 + 그룹별 옅은 배경 (`oklch(0.18 0.01 240 / 0.4)`).

### 3.3 ZOOM_PRESETS (변경 없음, 위치만 이동)

```js
const ZOOM_PRESETS = ['1M','3M','6M','1Y','ALL'];
```

차트 우상단 floating 위치(`position: absolute; top: 8px; right: 8px`).

### 3.4 INDICATOR_GROUPS 매핑

> 정정: v0.1 초안은 빌트인 *컬럼명* (`MA_20`, `BB_UPPER`, `RPB_DOWN_30` …) 으로 키를 잡았으나, **실제 우측 패널은 컬럼이 아닌 상위 토글 6개**를 보여줌. 실제 React state shape (verified at `app.jsx:693`):
> ```js
> const [indicators, setIndicators] = useState({
>   ma20: true, ma60: true, ma120: false, bb: true, rpb: false, rpbBoth: false
> });
> const [signalsOn, setSignalsOn] = useState(true);
> const [trendBand, setTrendBand] = useState(true);
> ```
> 그리고 RPB 컬럼명은 `RPB_DOWN_*` 가 아니라 **`RPB_DN_*`**, RSI 임계값은 `60/40` 이 아니라 **`70/75/80 ↔ 30/25/20`** (verified `backend/core/indicators.py:25-26`, `loader.js:76-94`).

따라서 그룹화는 **토글 단위**로 적용:

```js
// app.jsx (RightPanel 내부)
const INDICATOR_GROUPS = [
  {
    id: 'trend', label: '추세',
    items: [
      { key: 'ma20',  type: 'indicator', label: 'MA 20',  color: 'oklch(0.78 0.16 75)'  },
      { key: 'ma60',  type: 'indicator', label: 'MA 60',  color: 'oklch(0.70 0.13 230)' },
      { key: 'ma120', type: 'indicator', label: 'MA 120', color: 'oklch(0.62 0.18 320)' },
    ],
  },
  {
    id: 'volatility', label: '변동성',
    items: [
      { key: 'bb', type: 'indicator', label: '볼린저밴드 (20,2)', color: 'rgba(150,180,220,0.7)' },
    ],
  },
  {
    id: 'leading', label: '선행 (RPB)',
    items: [
      { key: 'rpb',     type: 'indicator', label: 'RSI Price Band',  color: 'oklch(0.62 0.22 25)', dataTestid: 'indicator-toggle-rpb' },
      { key: 'rpbBoth', type: 'indicator', label: '└ 양방향 표시',  color: 'rgba(180,180,180,0.5)', dependsOn: 'rpb' },
    ],
  },
  {
    id: 'display', label: '표시',
    items: [
      { key: 'signalsOn', type: 'flat', label: '신호 마커',      color: 'oklch(0.78 0.16 75)' },
      { key: 'trendBand', type: 'flat', label: '추세 영역 음영', color: 'var(--up)' },
    ],
  },
];
```

`type: 'indicator'` → `setIndicators({ ...indicators, [key]: v })` 로 갱신.
`type: 'flat'` → 별도 setter (`setSignalsOn` / `setTrendBand`) — `<RightPanel>` 가 props로 받음.

`dependsOn: 'rpb'` → `indicators.rpb === true` 일 때만 렌더 (기존 line 357 `{indicators.rpb && (...)}` 그대로).

**RPB 컬럼은 그룹화 대상이 아님** — 차트 라인 12개는 `rpb` 토글 단일로 함께 켜지고, `rpbBoth` 가 ATR 양방향 12 모두 vs 6만(단방향) 분기.

---

## 4. API / Helper Specifications

### 4.1 `lib/storage.js` (신규, ~30 lines)

```js
// Tradingmode/lib/storage.js
(function() {
  const PREFIX = 'tradingmode-';

  function get(key, fallback) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw === null) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      console.warn('[storage] parse failed', key, e);
      return fallback;
    }
  }

  function set(key, value) {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch (e) {
      console.warn('[storage] set failed', key, e);
    }
  }

  function remove(key) {
    try { localStorage.removeItem(PREFIX + key); } catch (_) {}
  }

  window.tmStorage = { get, set, remove };
})();
```

**호출 패턴**:
```js
const collapsed = window.tmStorage.get('ws-right-collapsed', {});
window.tmStorage.set('ws-right-collapsed', { ...collapsed, [sectionId]: true });
```

### 4.2 `formatPriceCompact(value)` (app.jsx 인라인)

```js
function formatPriceCompact(v) {
  if (v == null || isNaN(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return v.toFixed(2);
}
```

`76330` → `76.3K`, `1234567` → `1.2M`, `2.5` → `2.50`.

### 4.3 `useViewportWidth()` Hook (app.jsx)

```js
function useViewportWidth() {
  const [w, setW] = React.useState(typeof window !== 'undefined' ? window.innerWidth : 1920);
  React.useEffect(() => {
    const onResize = () => setW(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return w;
}
```

**파생 분기**:
- `w < 1024` → TopBar 시세 3개 (`KOSPI`, `USD/KRW`, `BTC`) + 모두 compact
- `1024 ≤ w < 1280` → TopBar 시세 6개 + compact
- `w ≥ 1280` → 시세 6개 + 풀 가격 (현재와 동일)

### 4.4 즐겨찾기 Stale 자동 정리

```js
// app.jsx, Watchlist 마운트 시
React.useEffect(() => {
  const favs = window.tmStorage.get('wl-favs', []);
  const validSyms = new Set(universe.map(u => u.symbol));
  const cleaned = favs.filter(s => validSyms.has(s));
  if (cleaned.length !== favs.length) {
    window.tmStorage.set('wl-favs', cleaned);
  }
}, [universe]);
```

---

## 5. UI Wireframes

### 5.1 Interval + Zoom 분리

**현재** (problem):
```
[1m] [5m] [15m] [1h] [4h] [1d]   |   [1M] [3M] [6M] [1Y] [ALL]
       ↑ minute              day      ↑ Zoom (혼란)
```

**v0.7** (target):
```
Header:  [1분] [5분] [15분] | [1시간] [4시간] | [일]
                                                          ┌─ chart top-right ─┐
                                                          │ [1M][3M][6M][1Y][ALL] │
                                                          └────────────────────┘
```

CSS 분리 (실제 ancestor 기반):
- `.tf-group--minute { background: oklch(0.18 0.01 240 / 0.3); }` (그룹 modifier — 기존 `.tf-group` 위에 적층)
- `.tf-group--hour { background: oklch(0.18 0.01 240 / 0.18); }`
- `.tf-group--day { background: transparent; }` (가장 큰 단위 → 강조 X)
- `.tf-divider { width: 1px; height: 18px; background: var(--border); margin: 0 6px; align-self: center; }` (그룹 사이 inline 삽입 — `--border` 는 `styles.css:6-13` 기존 토큰)
- `.zoom-fab { position: absolute; top: 8px; right: 8px; z-index: 5; backdrop-filter: blur(6px); background: oklch(0.16 0.01 240 / 0.7); border-radius: 6px; padding: 2px; }` — `.chart-pane` (line 268)에 absolute 배치
- `.chart-pane` 은 이미 `position: relative; overflow: hidden` (verified `styles.css:340`) — 별도 작업 불필요

### 5.2 우측 패널 Collapsible

기존 `.panel-section` 3개 (line 335, 347, 365)를 **그대로 유지**하고 헤더에 토글 버튼만 추가. 접힘 시 `.panel-section.collapsed` state class 부여(BEM modifier `--collapsed` 신설 X — 기존 `.wl-row.active` 컨벤션과 일치).

```
펼침 상태:                        일부 접힘 상태:
┌─ ▼ 현재 상태 ──────────┐    ┌─ ▶ 현재 상태 (요약) ───┐
│  추세: 상승             │    └────────────────────────┘
│  RSI 14: 58.4 중립      │    ┌─ ▼ 지표 오버레이 ───┐
│  MACD: -120 시그널 위   │    │ [추세]                │
│  MA20→60: 정배열        │    │   ☑ MA 20             │
└─────────────────────────┘    │   ☑ MA 60             │
┌─ ▼ 지표 오버레이 ──────┐    │   ☐ MA 120            │
│ [추세]                  │    │ [변동성]              │
│   ☑ MA 20  ☑ MA 60     │    │   ☑ 볼린저밴드 (20,2) │
│   ☐ MA 120             │    │ [선행 (RPB)]         │
│ [변동성]                │    │   ☐ RSI Price Band    │
│   ☑ 볼린저밴드 (20,2)  │    │ [표시]                │
│ [선행 (RPB)]           │    │   ☑ 신호 마커         │
│   ☐ RSI Price Band     │    │   ☑ 추세 영역 음영    │
│ [표시]                  │    └────────────────────────┘
│   ☑ 신호 마커          │    ┌─ ▶ 최근 신호 (8) ─────┐
│   ☑ 추세 영역 음영     │    └────────────────────────┘
└─────────────────────────┘
┌─ ▼ 최근 신호 ──────────┐
│  표시: [20 ▾]           │
│  [BUY] $76,200 13:42    │
│  [SELL] $76,500 14:10   │
│  ...                    │
└─────────────────────────┘
```

CSS 추가:
- `.panel-header { cursor: pointer; user-select: none; }` (기존 line 181 확장)
- `.panel-header::before { content: '▼'; margin-right: 6px; transition: transform 200ms ease; }`
- `.panel-section.collapsed .panel-header::before { transform: rotate(-90deg); }` (▼ → ▶)
- `.panel-section.collapsed > :not(.panel-header) { display: none; }` (헤더 외 자식 모두 hide)
- 그룹 헤더 (지표 4 그룹): `.ind-group-header { font-size: 11px; color: var(--text-dim); text-transform: uppercase; padding: 8px 0 4px 4px; letter-spacing: 0.05em; }`

### 5.3 TopBar 반응형 (3 breakpoint)

```
≥ 1280px:  [KOSPI 2,540.32 +0.45%] [USD/KRW 1,378.5 +0.12%] [BTC $76,330 -1.2%] [ETH $3,820] [...]
                                                                                     ↑ 6 tapes, full price

1024-1279: [KOSPI 2.5K +0.45%] [USD/KRW 1.3K +0.12%] [BTC 76.3K -1.2%] [ETH 3.8K] [...]
                                                                                     ↑ 6 tapes, compact

< 1024px:  [KOSPI 2.5K +0.45%] [USD/KRW 1.3K +0.12%] [BTC 76.3K -1.2%]
                                                                                     ↑ 3 tapes only (others hidden)
```

### 5.4 Watchlist 즐겨찾기

```
┌─ Watchlist ────────────────┐
│ ★ BTC/USDT    $76,330 -1.2%│   ← 즐겨찾기 (상단 고정)
│ ★ AAPL        $245.30 +0.5%│
│ ─────────────────────────  │   ← 구분선
│ ☆ ETH/USDT    $3,820 +0.3% │
│ ☆ MSFT        $451.50 -0.1%│
│ ☆ ...                       │
└─────────────────────────────┘
```

★ 버튼 클릭 시 즐겨찾기 토글 + localStorage 저장 + 정렬 재계산.

### 5.5 최근 신호 limit

```
┌─ ▼ 최근 신호 ──────────────┐
│ 표시: [20 ▾]   (10/20/50/100) │
│ ─────────────────────────  │
│ [scrollable list, max-h]   │
│ ◉ BUY @ $76,200            │
│ ◉ SELL @ $76,500           │
│ ...                         │
└─────────────────────────────┘
```

---

## 6. Error Handling

| 시나리오 | 처리 |
|---|---|
| `localStorage` 비활성 (private mode 등) | `try/catch` 후 in-memory fallback (페이지 새로고침 시 기본값) |
| JSON 파싱 실패 (사용자 수동 변조 등) | `console.warn` + 기본값 반환 |
| `wl-favs` 에 universe에 없는 심볼 | `useEffect` 마운트 시 자동 정리 (§4.4) |
| `signals-limit` 비정상 값 (음수/문자) | `clamp(10, 100)` |
| `viewport resize` 빈번 시 | passive listener, 추가 throttle 불필요 (React 18 batching) |

---

## 7. Security

신규 보안 표면 0건:
- 외부 입력 없음 (모든 상태 localStorage + universe 기반)
- XSS 위험 X (`dangerouslySetInnerHTML` 미사용)
- localStorage 값은 신뢰 가능한 사용자 자체 데이터 — 직렬화/역직렬화 외 처리 X
- `wl-favs` 심볼 검증 — universe whitelist 비교 후 사용

---

## 8. Test Plan

### 8.1 Manual / Playwright 시나리오 (12)

| # | 시나리오 | 검증 |
|---|---|---|
| T-01 | Interval `1m` 클릭 | 라벨 `1분` 표시, 부모 컨테이너에 `.tf-group--minute` 클래스 |
| T-02 | Interval 전체 표시 | `1분 / 5분 / 15분 | 1시간 / 4시간 | 일` 그룹 구분선 보임 |
| T-03 | Zoom `1Y` 클릭 | 차트 우상단 칩에서 동작, 헤더에서 사라짐 |
| T-04 | "현재 상태" ▼ 클릭 | 섹션 접힘, localStorage `tradingmode-ws-right-collapsed.current-status: true` |
| T-05 | 새로고침 후 상태 유지 | 접힌 섹션 그대로 |
| T-06 | "지표 오버레이" 그룹 헤더 4개 | `추세 / 변동성 / 선행 (RPB) / 표시` |
| T-07 | TopBar viewport 1500px | 6 시세 풀 가격 |
| T-08 | TopBar viewport 1100px | 6 시세 compact (`76.3K`) |
| T-09 | TopBar viewport 900px | 3 시세만 (KOSPI/USD-KRW/BTC) |
| T-10 | Watchlist BTC ★ 클릭 | 채워진 별, 상단 고정, `tradingmode-wl-favs: ["BTC/USDT"]` |
| T-11 | Universe 변경 후 stale ★ | 자동 정리, 키에 무효 심볼 없음 |
| T-12 | 최근 신호 limit `50` 선택 | 최대 50개 표시, localStorage 저장 |
| T-13 | Watchlist 즐겨찾기 2개 + 비즐겨찾기 3개 | 즐겨찾기 2개가 상단, `.wl-favs-divider` DOM 노드 1개, 비즐겨찾기 3개가 그 아래 (DOM 순서 검증) |

### 8.2 백엔드 회귀 테스트
- `pytest backend/tests/` → 147/147 PASSED 유지 (변경 0건)
- API 호출 시그니처 무변경 검증 (Network 탭 비교)

### 8.3 Browser
- Chromium (primary, Playwright)
- 수동: Edge / Firefox 1회씩 (UI 깨짐 점검)

---

## 9. Clean Architecture / Convention

### 9.1 계층 구조

```
[ Browser DOM ]
      │
[ React Components (app.jsx, charts.jsx) ]
      │
[ Hooks (useViewportWidth) + Helpers (formatPriceCompact) ]
      │
[ window.tmStorage  (lib/storage.js) ]
      │
[ window.localStorage  (브라우저 API) ]
```

상위 컴포넌트는 `tmStorage`의 prefix를 알 필요 없음 — 키 이름만 전달.

### 9.2 Naming

| Category | Convention | 예 |
|---|---|---|
| localStorage 키 | kebab-case, prefix 자동 | `ws-right-collapsed` |
| CSS 상태 클래스 | **compound class** (기존 v0.4–v0.6 컨벤션 — `.wl-row.active`, `.ind-toggle.on` 와 일치). BEM modifier (`--collapsed`) 는 사용 X | `.panel-section.collapsed`, `.wl-row.is-fav`, `.tf-btn.zoom` |
| CSS 그룹 modifier | 변형 modifier 가 의미적으로 더 명확할 때만 BEM `--` 허용 | `.tf-group--minute`, `.tf-group--hour`, `.tf-group--day` |
| Section ID | kebab-case | `current-status`, `indicators-overlay`, `recent-signals` |
| Group ID | 단일 단어 | `trend`, `volatility`, `leading`, `display` |

### 9.3 Coding Convention

- 함수형 컴포넌트만 사용 (class X)
- 200ms transition 상수 — `--transition-quick: 200ms ease`
- `console.warn` 만 사용 (error는 throw)
- 한국어 라벨은 컴포넌트 내부 상수로 인라인 (i18n X)

---

## 10. Implementation Guide

### 10.1 Phase A — Interval/Zoom (1.5h, localStorage 의존 X)

1. `app.jsx` 에 `INTERVAL_LABELS` 상수 추가 (line 230 근처)
2. `.tf-group` 안 `.map(['1m','5m',...])` 6개를 그룹별 분할 — `[1m,5m,15m] | divider | [1h,4h] | divider | [1d]`
3. `.tf-group--minute/--hour/--day` modifier + `.tf-divider` CSS 추가
4. Zoom 그룹(`.tf-group` line 235)을 `.ih-right` 에서 분리 → `.chart-pane`(line 268) 내부로 이동
5. `.chart-pane { position: relative; }` 1줄 보강 + `.zoom-fab { position: absolute; top: 8px; right: 8px; }` CSS 추가
6. Playwright T-01~T-03 검증

> Phase A 는 React state(`interval`, `zoomLevel`)만 다루고 localStorage 와 무관 — Phase B 의 `lib/storage.js` 도입 전에도 안전하게 진행 가능.

### 10.2 Phase B — RightPanel collapsible + 지표 그룹 (1.5h)

1. `Tradingmode/lib/storage.js` 작성 (plain JS IIFE — `window.tmStorage` 노출)
2. `index.html` script 등록 — **`loader.js` 다음, 첫 `.jsx` (`tweaks-panel.jsx`) 앞**:
   ```html
   <script src="loader.js?v=9"></script>
   <script src="lib/storage.js?v=9"></script>          <!-- ✨ NEW -->
   <script type="text/babel" src="tweaks-panel.jsx?v=9"></script>
   ```
   (`type="text/babel"` 아님 — plain JS)
3. 기존 `.panel-section` 3개 (`app.jsx:335, 347, 365`) 헤더에 토글 onClick 추가, `.collapsed` state class 부여 — DOM 구조/클래스 이름 변경 X
4. `INDICATOR_GROUPS` 상수 정의 + `.ind-list` 내부에 그룹 헤더(`.ind-group-header`) 4개 삽입, 기존 `<IndToggle>` 8개를 그룹별로 재배열
5. `.signal-feed` 은 이미 `max-height: 360px; overflow-y: auto` 적용됨 (`styles.css:449`) — limit 변경 시 재검증만 (Plan §5 Risk row 8 mitigation 확인용)
6. Playwright T-04~T-06 검증

### 10.3 Phase C — TopBar + Watchlist + Signals limit (1h)

1. `useViewportWidth` Hook + `formatPriceCompact` 헬퍼 (`app.jsx` 상단 helpers 영역)
2. `TopBar` 분기 렌더 (1280/1024 break point)
3. `WatchlistRow` 에 ★ 버튼 추가 + `.wl-row.is-fav` state class + 정렬 로직 (`favs.includes(s) ? 0 : 1`)
4. 즐겨찾기/일반 사이 `.wl-favs-divider` 노드 1개 삽입 (즐겨찾기 ≥ 1 일 때만)
5. Stale 즐겨찾기 자동 정리 useEffect (universe 변경 시)
6. `RecentSignals` limit `<select>` + slice
7. `index.html` 캐시 버스트 v8 → v9 일괄
8. Playwright T-07~T-13 검증

### 10.4 마무리

- `index.html` v8 → v9 캐시 버스트
- 백엔드 pytest 재실행 (147/147)
- 수동: 1500/1100/900px 3개 viewport 점검

**총 예상 시간**: ~4h

---

## 11. Future Extensions (v0.8+)

- 키보드 단축키 (`d`/`h`/`m` 인터벌, `s` watchlist 검색)
- 우측 패널 width 드래그 조절 (CSS `resize: horizontal` 또는 split.js)
- localStorage 전체 객체 통합 (`tradingmode-ui` 단일 키)
- i18n 도입 시 한국어 default + 영어 보조
- "Zoom 위치 변경됐습니다" 1회 toast (v0.8.0 release note)
- Watchlist 그룹 (`Crypto / KR Stocks / FX`)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-02 | 초안 — 10 FRs를 컴포넌트/CSS/localStorage 키 단위로 구체화. Phase A~C 4h. | 900033@interojo.com |
| 0.3 | 2026-05-03 | design-validator 91% → 보강. **N-1** T-01 클래스 어서션 `cp-interval-group-minute` → `.tf-group--minute`. **N-2** §3.2 divider 클래스 `cp-interval-divider` → `tf-divider` 통일. **N-3** `var(--line)` → `var(--border)` (실존 토큰). **N-4** `.chart-pane position:relative` 이미 적용 명시. **N-5** `.signal-feed max-height` 이미 적용 명시. Plan §7.2 의 `.cp-interval-*` 명세는 Design v0.3 의 `.tf-group--*` 로 대체됨 (코드/일관성 우선). 목표 95%+. | 900033@interojo.com |
| 0.2 | 2026-05-03 | design-validator 78% → 보강. **C-1** RPB 컬럼명 `RPB_DOWN_*` → `RPB_DN_*`, 임계값 `60/40` → `70/75/80↔30/25/20` 정정. **C-2** INDICATOR_GROUPS 를 가공 컬럼 → 실제 React state 토글(`ma20/ma60/ma120/bb/rpb/rpbBoth`+`signalsOn/trendBand`)로 재작성. **C-3/C-4** Interval/Zoom 위치 `charts.jsx` → `app.jsx`, 클래스 `.cp-*` → 실제 `.tf-group/.tf-btn/.ih-right/.chart-pane`. **H-1** `.panel-section` 기존 클래스 유지(rename X), `.collapsed` state class 만 추가. **H-2** BEM compound-class 컨벤션 통일(`.wl-row.active` 선례 일치). **H-3** 즐겨찾기 divider DOM 검증용 T-13 추가. **M-1** `lib/storage.js` script 슬롯 명시(loader.js 다음, 첫 .jsx 앞, plain JS). 목표 95%+. | 900033@interojo.com |
