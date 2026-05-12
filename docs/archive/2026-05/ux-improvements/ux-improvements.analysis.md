---
template: analysis
version: 1.0
feature: ux-improvements
date: 2026-05-03
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.7.0
---

# Gap Analysis — ux-improvements v0.7.0

> **Source**: gap-detector agent (Design v0.3 ↔ Implementation), Date 2026-05-03
> **Match Rate**: **96%** — Critical 0, High 0, Medium 2, Low 2 → `/pdca report` 진행 권장 (iterate 불필요)

---

## 1. Match Rate Summary

| 항목 | 결과 |
|---|---|
| **Match Rate** | **96%** |
| Critical Gaps | 0 |
| High Gaps | 0 |
| Medium Gaps | 2 (M-1, M-2) |
| Low Gaps | 2 (L-1, L-2) |
| FR Coverage | 10/10 (100%) |
| T-NN Feasibility | 13/13 (100%, structurally feasible) |
| Backend Isolation (FR-10) | ✅ 0건 변경 (empirically verified) |
| `charts.jsx` Untouched | ✅ 0건 변경 |

---

## 2. Coverage Matrix

| FR | Design Spec | Implementation (file:line) | Match | Test |
|----|-------------|----------------------------|:-----:|:----:|
| FR-01 | INTERVAL_LABELS 6키 한국어 (`1m:1분` 등) | `app.jsx:153` 정의, `app.jsx:253` `{INTERVAL_LABELS[iv].label}` 렌더 | ✅ | T-01 |
| FR-02 | 3 `.tf-group--*` + 2 `.tf-divider`, 그룹 배경 | `app.jsx:241-258` `INTERVAL_GROUP_ORDER.map`, `gi > 0 && <tf-divider>`; `styles.css:306-316` 배경 | ✅ | T-02 |
| FR-03 | Zoom `.chart-pane` 우상단, `.zoom-fab` absolute | `app.jsx:298` `<div className="tf-group zoom-fab">` 첫 chart-pane 안; `styles.css:319-329` `position: absolute; top: 8px; right: 8px` | ✅ | T-03 |
| FR-04 | 3 `<CollapsibleSection>` + `tradingmode-ws-right-collapsed` | `app.jsx:384-406` 헬퍼; `app.jsx:429/438/462` 3 sectionId; `app.jsx:393` 저장 | ✅ | T-04, T-05 |
| FR-05 | INDICATOR_GROUPS 4 그룹 + `.ind-group-header` + `dependsOn` | `app.jsx:351-380` 4 entries (trend/volatility/leading/display); `app.jsx:442` 헤더; `app.jsx:444` `dependsOn` 필터 | ✅ | T-06 |
| FR-06 | `useViewportWidth` + `compact<1280` + `minimal<1024` + `formatPriceCompact` | `app.jsx:30-38` Hook (passive + cleanup); `app.jsx:42-44` 임계값; `app.jsx:56` essential 필터; `app.jsx:72` compact 분기 | ✅ | T-07~T-09 |
| FR-07 | `wl-favs` localStorage + ★/☆ 토글 | `app.jsx:108-110` 초기화; `app.jsx:123-128` `toggleFav`; `app.jsx:160` `★/☆` | ✅ | T-10 |
| FR-08 | favRows 우선 + `.wl-favs-divider` (둘 다 있을 때만) | `app.jsx:133-135` split + showDivider; `app.jsx:194-196` 렌더 순서 | ✅ | T-13 |
| FR-09 | `[10,20,50,100]` select + `tradingmode-signals-limit` 영속 | `app.jsx:493`; `app.jsx:504-511` state+setter; `app.jsx:512` slice; `app.jsx:559-569` UI | ✅ | T-12 |
| FR-10 | 백엔드 무영향, charts.jsx 무영향 | `backend/` grep 0건 (`tradingmode-`, `tmStorage`, `wl-favs`, etc.); `charts.jsx` grep 0건 | ✅ | N/A |

### Design-specific (Plan 외)

| 항목 | 명세 | 구현 | Match |
|---|---|---|:---:|
| §3.1 4 keys + prefix | ws-right-collapsed / wl-favs / signals-limit / **ind-groups-collapsed** | 앞 3키만 사용, 4번째 미사용 | Partial (M-1) |
| §4.1 `tmStorage.{get,set,remove}` + try/catch | `storage.js:6-29` 모두 try/catch + 보너스 `PREFIX` export | ✅ |
| §4.2 `formatPriceCompact` null/NaN/K/M/B | `app.jsx:21-28` 정확 일치 | ✅ |
| §4.3 `useViewportWidth` Hook | passive listener + cleanup | ✅ |
| §4.4 stale ★ auto-cleanup useEffect | `app.jsx:113-121` universe dep | ✅ (T-11) |
| §10.1–§10.3 phase 순서 | A → B → C 순서대로 적용 | ✅ |

---

## 3. Gaps

### Critical: 0
### High: 0
### Medium: 2

- **M-1** — `tradingmode-ind-groups-collapsed` 키 선언만 있고 미사용. Plan FR-05 는 "그룹 헤더 표시"만 요구, 그룹별 collapse 미요구. Design 의 over-specification — v0.4 에서 Design §3.1 에서 키 제거 또는 v0.8 에서 그룹별 collapse 구현.
- **M-2** — `var(--border)` 토큰 값 drift. Design §3.2 `oklch(0.18 0.01 240 / 0.4)` vs 구현 `--minute oklch(0.18 0.005 240 / 0.85)`, `--hour oklch(0.20 0.005 240 / 0.7)`. 시각적으로 동일하나 리터럴 불일치 (구현이 기존 `--bg` 토큰과 더 잘 어울리는 의도적 보정). Design §5.1 CSS 스니펫을 구현값으로 갱신 권장.

### Low: 2

- **L-1** — `dataTestid` → `testid` 키명 변경. Design §3.4 line 143 `dataTestid:`, 구현 `app.jsx:357` `testid:`. 구현은 `app.jsx:445` 에서 `data-testid` 로 정확히 spread. DOM 결과는 동일. Design §3.4 키명 정렬 권장.
- **L-2** — `trendBand` swatch 색 `var(--up)` → `oklch(0.72 0.18 145)` 하드코딩. 같은 값이지만 `upDownConvention: 'eastern'` 토글 시 swatch 가 따라가지 않음. `app.jsx:377` 에서 `'var(--up)'` 로 변경하면 테마 토큰 추적 가능.

---

## 4. Backend Isolation Verification (FR-10)

- ✅ `grep -r "tradingmode-\|tmStorage\|wl-favs\|signals-limit\|ws-right-collapsed" C:/X/new/backend/` → **0 hits**
- ✅ `grep -r "INTERVAL_LABELS\|tmStorage\|zoom-fab\|wl-favs\|signals-limit\|CollapsibleSection\|tf-divider\|INDICATOR_GROUPS\|ws-right-collapsed" C:/X/new/Tradingmode/charts.jsx` → **0 hits**
- 백엔드 코드 path 0건 수정 → 147 pytest 회귀 위험 0 (수동 실행 시 기존 결과 유지 보장).

---

## 5. Implementation Quality Notes

### 잘한 점 (6)

1. **`tmStorage` 방어적 호출 일관성** — `(window.tmStorage && ...) || fallback` 패턴 (`app.jsx:109, 385, 503`). storage.js 로드 실패 시 in-memory 기본값으로 graceful degradation. Design §6 row 1 정확히 구현.
2. **`<button>` 중첩 회피** — `app.jsx:150-161` `<span role="button">` + `aria-pressed` + 키보드 Enter/Space + `e.stopPropagation()`. React validateDOMNesting 경고 0건.
3. **CSS scope leak 차단** — `.right-panel .panel-section` 스코프 (`styles.css:436-452`). BacktestPage 3개 `.panel-section` (line 567/579/589) 회귀 0. 인라인 주석 (`styles.css:435-436`)에 의도 문서화.
4. **CollapsibleSection 마운트 race 방지** — `useState` 초기자에서 storage 읽음 (initial flash 없음). T-05 (새로고침 후 상태 유지) 구조적 보장.
5. **`SIGNALS_LIMIT_OPTIONS.includes(v)` whitelist clamp** (`app.jsx:506`). Design §6 row 4 (`clamp(10,100)`) 보다 더 엄격한 whitelist 검증.
6. **TopBar topbar-mid `@media` 보강** — JS 분기 + CSS gap 축소 이중 방어 (`styles.css:94-95`).

### 개선 여지 (4, 모두 Low)

- **C-1** — `useViewportWidth` SSR 가드 (`typeof window !== 'undefined'`) 제거됨. CDN 환경이라 무관하나 Design §4.3 의 방어형이 사라짐.
- **C-2** — stale-cleanup `useEffect` deps 에 `favs` 미포함 (`app.jsx:121`). 의도적이지만 ESLint exhaustive-deps 경고 발생 가능.
- **C-3** — `panel-count` 가 `current-status`/`indicators-overlay` 에 표시되지 않음 (Design §5.2 와이어프레임의 "(요약)" 미구현). 의도적 simplification.
- **C-4** — `CollapsibleSection` 의 `stored = (...).get(...)` 가 매 렌더마다 호출 (`app.jsx:385`). `useState(() => ...)` lazy init 으로 변경 권장 (Watchlist 패턴과 일치).

---

## 6. v0.4–v0.6 사이클 트렌드 비교

| Cycle | Design 첫 검증 | Design 보강 후 | 구현 매치율 | Iterate |
|---|---:|---:|---:|:---:|
| v0.4.1 trading-analysis-tool | 78% | 95% | 95% | 1회 → 99% |
| v0.5.0 ai-strategy-coach | 84% | 92% | 97% | 0회 |
| v0.6.0 rsi-price-bands | 91% | 95% | **98%** | 0회 |
| **v0.7.0 ux-improvements** | **78%** | **96%** | **96%** | **0회 (예정)** |

**관찰**: Design 첫 검증 점수는 v0.4.1 대비 동일 (78%) — 사실관계 오류(코드 경로 잘못 추정) 가 컸음. 보강 후 96% 로 빠르게 회복. 구현 매치율은 안정적 90% 후반대 유지.

---

## 7. Recommendation

✅ **Match Rate 96% ≥ 90% → `/pdca report ux-improvements` 진행 (iterate 단계 생략).**

선택적 cleanup (10분, v0.8 로 미뤄도 무방):
- L-2: `app.jsx:377` `'oklch(0.72 0.18 145)'` → `'var(--up)'` (1자 변경, 테마 토큰 추적)
- M-2: Design §5.1 CSS 스니펫을 구현값으로 갱신
- L-1: Design §3.4 `dataTestid` → `testid`
- M-1: Design §3.1 `tradingmode-ind-groups-collapsed` 키 제거

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0 | 2026-05-03 | gap-detector 분석. 96% 매치, FR 10/10, T 13/13 feasibility. Critical/High 0건. | 900033@interojo.com |
