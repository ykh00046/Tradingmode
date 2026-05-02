---
template: plan
version: 1.2
feature: ux-improvements
date: 2026-05-02
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.7.0
---

# ux-improvements Planning Document

> **Summary**: 차트 인터벌 라벨 충돌(`1m` vs `1M`) 해소, 우측 패널 collapsible 섹션화, 지표 토글 그룹화, TopBar 반응형 축약, Watchlist 즐겨찾기 — 사용 편의성 전반 개선.
>
> **Project**: trading-analysis-tool
> **Version**: 0.7.0 (이전 사이클 v0.6.0 위에 누적)
> **Author**: 900033@interojo.com
> **Date**: 2026-05-02
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

UX 검토에서 발견된 7개 이슈를 우선순위별로 해결하여 차트 페이지 사용 편의성을 정량 향상. 백엔드 변경 없음 — Frontend (Tradingmode/) 단일 영역 작업.

### 1.2 Background

이전 3 사이클(v0.4~v0.6)은 *기능 추가* 위주로 진행. 사용자가 직접 사용해보며 **명백한 UX 결함** 발견:

1. **`1m` (1분봉) vs `1M` (1개월 zoom)** 동일 화면에 표시 — 대소문자만 다른 라벨로 거의 식별 불가
2. **분/시간/일 그룹 시각 구분 X** — 6 인터벌 모두 동일 visual weight
3. **우측 패널 92px 잘림** (883/791) — 섹션 접기 기능 없음
4. **TopBar 좁은 화면(929px)에서 잘림** — 시세 6개 가로 배치 고정
5. **Watchlist 즐겨찾기 X** — 종목 많아지면 스크롤만 길어짐
6. **지표 토글 그룹화 X** — 추세/변동성/표시가 혼재
7. **최근 신호 무한 스크롤** — 페이지네이션 X

### 1.3 Related Documents

- 이전 사이클: `docs/archive/2026-05/rsi-price-bands/` (v0.6.0)
- UX 검토 리포트: 본 사이클 직전 사용자 요청에서 도출
- 기존 코드: `Tradingmode/{charts.jsx, app.jsx, styles.css}`

---

## 2. Scope

### 2.1 In Scope (우선순위 1 + 2 — v0.7)

#### 우선순위 1 — Critical (혼란 유발)
- [ ] **Interval 라벨 한국어 단위로 변경** — `1m`→`1분`, `1h`→`1시간`, `1d`→`일` 등 (1M↔1m 충돌 해소)
- [ ] **Interval 버튼 그룹 시각 구분** — 분/시간/일 사이 구분선 또는 색조 그라디언트
- [ ] **Zoom과 Interval 위치 분리** — Zoom은 차트 우상단 작은 칩으로 이동
- [ ] **우측 패널 섹션 collapsible** — "현재 상태", "지표 오버레이", "최근 신호" 각각 ▼ 토글 (펼침 상태 localStorage 저장)

#### 우선순위 2 — High (편의성)
- [ ] **지표 토글 그룹화** — "추세" / "변동성" / "선행 (RPB)" / "표시" 4 섹션
- [ ] **TopBar 반응형 축약** — < 1280px 시 시세 텍스트 줄임 (예: `BTC $76,330` → `BTC 76K`), < 1024px 시 핵심 3개만
- [ ] **Watchlist 즐겨찾기 ★** — 별표 클릭 → 상단 고정 (localStorage 저장)
- [ ] **최근 신호 limit slider** — 기본 20개, "더 보기" 버튼 또는 슬라이더

### 2.2 Out of Scope (v0.8 이상)

- 키보드 단축키 (`d` 일봉, `h` 1시간) — v0.8
- 우측 패널 width 드래그 조절 — v0.8
- 대시보드 layout 사용자 저장 (localStorage 전체 직렬화) — v0.8
- 모바일 네이티브 레이아웃 (touch first) — v2
- 다크/라이트 테마 전환 — v2
- 다국어 (영어/일본어) — 추후

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Interval 라벨 한국어 단위로 표시 (`1분/5분/15분/1시간/4시간/일`) | High | Pending |
| FR-02 | Interval 버튼 분/시간/일 그룹 시각 구분 (구분선 또는 옅은 배경) | High | Pending |
| FR-03 | Zoom 프리셋(1M/3M/6M/1Y/ALL)을 차트 우상단으로 이동, 작은 칩 디자인 | High | Pending |
| FR-04 | 우측 패널 3 섹션 각각 ▼ 토글 가능, 펼침 상태 localStorage `ws-right-collapsed` 저장 | High | Pending |
| FR-05 | 지표 오버레이 토글을 4 그룹(추세/변동성/선행/표시)으로 묶고 그룹 헤더 표시 | Medium | Pending |
| FR-06 | TopBar 가로폭 < 1280px 시 시세 텍스트 축약 (`BTC $76,330` → `BTC 76.3K`), < 1024px 시 KOSPI/USD-KRW/BTC 3개만 | Medium | Pending |
| FR-07 | Watchlist 종목 우측에 ★ 별표 버튼, 클릭 시 즐겨찾기 토글, localStorage `wl-favs` 저장 | Medium | Pending |
| FR-08 | 즐겨찾기 종목은 Watchlist 상단에 고정 표시 (구분선 아래 일반 종목) | Medium | Pending |
| FR-09 | "최근 신호" 패널에 표시 개수 슬라이더 (10/20/50/100), 기본 20 | Low | Pending |
| FR-10 | 모든 변경은 백엔드 영향 0건 (Frontend only) — 기존 147 테스트 무영향 | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| Performance | 토글 클릭 → 시각 반응 < 100ms (CSS transition) | 수동 측정 |
| Accessibility | 모든 토글 button role + aria-expanded 속성 | DOM 검증 |
| Reproducibility | localStorage 키 충돌 X (`ws-right-collapsed`, `wl-favs`, `signals-limit` prefix `tradingmode-`) | 수동 검증 |
| Backward Compat | localStorage 값 없을 때 기본 동작 (이전 UX와 동일) | 수동 검증 |
| Visual | 다크 테마 OKLCH 토큰 일관성 유지 | 시각 점검 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 High 우선순위 FR 구현 완료
- [ ] e2e Playwright 시나리오:
  - Interval 클릭 → 라벨 한국어로 표시 (`1분/5분/15분/1시간/4시간/일`)
  - Zoom과 시각 구분 (위치/크기 다름)
  - 우측 패널 ▼ 토글 클릭 → 섹션 접힘/펼침
  - localStorage에 `tradingmode-ws-right-collapsed` 키 저장 검증
  - Watchlist ★ 클릭 → 종목이 상단으로 이동, `tradingmode-wl-favs` 저장
- [ ] 백엔드 147/147 테스트 무영향 (regression 0건)
- [ ] 좁은 화면(929px)에서 TopBar 시세 잘림 없음 (축약 표시)

### 4.2 Quality Criteria

- [ ] Gap Analysis 매치율 ≥ 90%
- [ ] 빌드/실행 시 에러 0건
- [ ] localStorage 4개 키만 사용 (충돌 방지 prefix `tradingmode-`)
- [ ] 모든 collapsible 섹션 기본 펼침 상태 (이전 UX 호환)
- [ ] CSS transition 부드러움 (200~300ms ease)

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Interval 한국어화로 i18n 부채 누적 (영어권 사용자 추가 시) | Low | Low | 추후 i18n 도입 시 한국어를 default locale로 (현재 단일 사용자) |
| Zoom 칩 위치 변경으로 기존 사용자 혼란 | Medium | Low | 첫 사용 시 1회 toast "Zoom 위치가 변경됐습니다" 표시 (선택, v0.8) |
| localStorage 4개 키 추가로 사용자 데이터 누적 | Low | Low | prefix `tradingmode-`로 관리, 향후 단일 객체로 통합 가능 |
| 우측 패널 collapsible 시 차트 영역 width 변경 안 됨 (펼치든 접든 같은 width) | Low | High | width 변동 X — 단지 내부 스크롤 해소가 목적. 펼침/접힘은 세로 공간만 절약 |
| 즐겨찾기 종목 데이터 마이그레이션 (universe 변경 시 stale ★) | Low | Medium | localStorage 즐겨찾기 검증 — 현재 universe에 없는 심볼은 무시 |
| 그룹 헤더로 우측 패널 세로 길이 증가 | Medium | Medium | 그룹 헤더는 collapsible과 통합 — 헤더 클릭이 곧 ▼ 토글 |
| TopBar 축약 표기 가독성 저하 (76,330 → 76.3K) | Low | Low | hover 시 tooltip으로 정확한 값 표시 (선택) |
| 최근 신호 슬라이더로 세로 길이 변동 → 차트 영역과 충돌 | Low | Low | "최근 신호" 섹션 자체 max-height + 내부 스크롤 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Selected |
|-------|:--------:|
| Starter | ☐ |
| **Dynamic** | ☑ |
| Enterprise | ☐ |

기존 사이클 그대로 — 단일 페이지 UX 개선은 Dynamic 충분.

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| Interval 라벨 형식 | 영어 (1m/1h/1d) / 한국어 (1분/1시간/일) / 기호 (m/h/d) | **한국어** | 1M ↔ 1m 충돌 즉시 해소, 한국 사용자 친화 |
| Zoom 위치 | 헤더 옆 / 차트 위 / 차트 우상단 칩 | **차트 우상단 칩** | 차트와 시각적 결합, 헤더 분리 |
| Collapsible 상태 저장 | sessionStorage / localStorage / 서버 | **localStorage** | 백엔드 변경 없음, 영구 저장 |
| 즐겨찾기 데이터 | 별도 array / Set / Map | **string[]** localStorage | 단순, JSON 직렬화 친화 |
| 지표 그룹 그룹화 방식 | 헤더 + 들여쓰기 / 별도 카드 / 탭 | **헤더 + 들여쓰기** | 기존 ind-toggle 컴포넌트 재사용 |
| TopBar 축약 임계값 | 1280/1024 / 1440/1024 / 1280만 | **1280/1024 2단계** | 일반적 노트북(1280) + 작은 노트북(1024) 대응 |
| 신호 limit 기본값 | 10 / 20 / 50 | **20** | 화면 1~2 스크롤 분량 |

### 6.3 폴더 구조 (변경분만)

```
Tradingmode/
├── app.jsx                  (확장: TopBar 반응형, indicators 그룹 헤더, Watchlist ★, signals limit)
├── charts.jsx               (확장: Interval 라벨/그룹/구분선, Zoom 칩 우상단)
├── styles.css               (확장: .interval-group, .ws-section.collapsed, .wl-fav, .topbar-tape-compact 등)
└── lib/storage.js           ✨ NEW (선택) — localStorage 헬퍼 (prefix, JSON 직렬화)
```

`lib/storage.js`는 4개 키 관리를 위해 선택적으로 신규 — 단순하면 인라인 처리 가능.

---

## 7. Convention Prerequisites

### 7.1 Existing Conventions (재사용)

- [x] React 18 (CDN), Babel standalone
- [x] OKLCH 다크 테마 토큰
- [x] JetBrains Mono / Inter 폰트
- [x] BEM-like 클래스명 (`.ws-right`, `.wl-row`, `.ind-toggle`)

### 7.2 Conventions to Define

| Category | New | Priority |
|----------|-----|:--------:|
| localStorage 키 prefix | `tradingmode-` (예: `tradingmode-wl-favs`) | High |
| Collapsible 섹션 클래스 | `.ws-section`, `.ws-section.collapsed`, `.ws-section-header` | High |
| 즐겨찾기 별표 | `.wl-fav` (active 시 채워진 별), `.wl-row.is-fav` | Medium |
| 인터벌 그룹 구분 | `.cp-interval-group-{minute|hour|day}` | Medium |
| TopBar 축약 함수 | `formatPriceCompact(value)` 헬퍼 (`76330` → `76.3K`) | Low |

### 7.3 Environment Variables (변경 없음)

기존 그대로. 신규 추가 X.

### 7.4 Pipeline Integration

기존 v0.6.0 그대로.

---

## 8. Next Steps

1. [ ] 사용자 검토 및 Plan 승인
2. [ ] Design 문서 작성 (`/pdca design ux-improvements`)
   - 핵심: localStorage 헬퍼 명세, collapsible 섹션 컴포넌트, Interval/Zoom 위치 와이어프레임
3. [ ] 구현 (`/pdca do ux-improvements`)
4. [ ] Gap Analysis (`/pdca analyze ux-improvements`)

**예상 작업량**: ~4시간 (중간 사이클)
- Phase A: Interval/Zoom 라벨·그룹·위치 (1.5h)
- Phase B: 우측 패널 collapsible + 지표 그룹화 (1.5h)
- Phase C: TopBar 반응형 + Watchlist ★ + 신호 limit (1h)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-02 | 초안 — UX 검토 7 이슈 기반 우선순위 1+2 작업 | 900033@interojo.com |
