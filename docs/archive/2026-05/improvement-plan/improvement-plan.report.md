---
template: report
version: 1.0
feature: improvement-plan
date: 2026-05-16
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.10.0
---

# improvement-plan Completion Report

> **Summary**: 프로젝트 객관 리뷰에서 드러난 "검증 성숙도 격차"를 메운 사이클.
> 기능 추가가 아니라 **검증 레이어 구축**이 목표였다. P0(백엔드 통합/회귀
> 테스트 + 프론트 스모크), P1-1(지표 골든 스냅샷), P2(기능 개선 5종 중 4종 +
> OBV)를 구현. **99% 설계-구현 일치**, Critical/High/Medium 갭 0. 백엔드
> 175 passed · `node --test` 2/2 · 프론트 스모크 10/10. P0-1 회귀 스위트가
> 첫 구현에서 새 버그(BB 점-컬럼명)를 발견·수정 — 개선 플랜의 전제를 실증.
> P1-2(빌드 파이프라인)는 별도 PDCA 사이클로 분리.
>
> **Project**: trading-analysis-tool · **Version**: 0.10.0 · **Date**: 2026-05-16
> **Builds on**: v0.4~v0.9 누적 + 2026-05-16 세션 버그 다수 수정

---

## 1. Executive Summary

이 사이클은 기능 사이클이 아니다. 2026-05-16 세션의 전수 코드 리뷰에서
드러난 패턴 — "기능은 만들어졌고 · 단위 테스트는 통과하고 · UI는 완성돼
보이는데 · 실제 사용 경로에서 실패" — 을 구조적으로 차단하는 **검증 레이어**를
세웠다.

산출물: 백엔드 통합/회귀 테스트 스위트, 프론트엔드 스모크 테스트, 지표 골든
스냅샷 테스트, 그리고 P2 기능 개선 4종 + 거래량 지표(OBV). 회귀 테스트 3종이
이제 백엔드·프론트 양쪽 코드베이스를 지킨다.

---

## 2. Cycle Timeline

| 단계 | 내용 |
|------|------|
| Plan | `docs/improvement-plan.md` — 객관 리뷰 기반 P0/P1/P2 로드맵 |
| Design v0.1 | P0/P1/P2 구현 설계 |
| Design v0.2 | 설계 검증 — F1~F7 보강 (R-3 어댑터 레벨 재설계 등) |
| Design v0.3 | Phase 3 구현 중 발견 — §5.2 "백엔드 패리티" 전제 폐기 |
| Do Phase 1 | P0-1 백엔드 회귀 — **BB 점-컬럼명 버그 발견·수정** |
| Do Phase 2 | P0-2 프론트 스모크 (10/10) |
| Do Phase 3 | P1-1 지표 골든 스냅샷 |
| Do Phase 4 | P2 기능 개선 4종 (P2-1/2/4/5) |
| Check | 갭 분석 98% → v1.1 99% |
| 후속 | P2-3 OBV 구현 / P1-2 별도 사이클 분리 |

---

## 3. Deliverables

| 항목 | 산출물 | 검증 |
|------|--------|------|
| P0-1 백엔드 회귀 | `test_api/test_regression.py` (R-1~R-5) + `test_data_loader.py` R-3 | backend 175 passed |
| P0-2 프론트 스모크 | `tests/e2e/smoke.py` + README + `requirements-dev.txt` | 10/10 |
| P1-1 지표 골든 | `tests/indicators.test.mjs` + `indicator-golden.json` (+ `rpb`/`wilderRma` export) | node --test 2/2 |
| P2-1 컨플루언스 | `signalConfluence` 헬퍼 → 마커 툴팁 `동의 N/3` | 검증 |
| P2-2 밴드 토글 | 볼린저밴드 ↔ RPB 상호배타 | 검증 |
| P2-4 정밀 패닝 | 키보드 ←/→ 1봉, Shift 25% | 검증 |
| P2-5 AI 키 안내 | `groq_configured` 배너 | 검증 |
| P2-3 거래량 지표 | `add_obv` + 거래량 패널 OBV 오버레이 + DSL 카탈로그 | 검증 |

---

## 4. Bugs Found & Fixed

P0-1 회귀 스위트는 세션 전반에 수정된 버그(KR 주/월봉 tz, MACD 시그널선,
전략 `and`/`or` 평가)를 **회귀 테스트로 고정**한다. 그리고 첫 구현에서
**새 버그를 발견**했다:

- **BB 점-컬럼명 버그** — R-1을 빌트인 5종 *실제 식*으로 돌리자 BB Squeeze가
  `400 syntax error`. BB 컬럼명 `BBL_20_2.0_2.0`의 점(.) 때문에 DSL의
  `ast.parse`가 실패. 6번째 깨진 빌트인. 9개 파일에 걸쳐 dot-free
  (`BBL_20`)로 수정.

→ "대표 입력으로 검증하면 결함이 잡힌다"는 개선 플랜의 핵심 전제가 사이클
첫날 실증됐다.

---

## 5. Decisions Worth Remembering

- **설계가 구현에 의해 두 번 교정됨** — 검증 단계 v0.2(F1~F7), Phase 3 구현
  중 v0.3(§5.2). 설계 문서는 살아있는 기준선이며, 구현이 설계를 정당하게
  교정할 수 있다.
- **R-3는 어댑터 레벨** — `patch_fetch`가 `data_loader.fetch`를 통째로 교체해
  `krx_adapter` resample을 우회한다는 점을 v0.2에서 미리 잡아, KR tz 회귀를
  어댑터 레벨에 배치했다. API 레벨로 설계했다면 버그 경로를 못 탔다.
- **data.js 자체 골든 스냅샷** — data.js와 백엔드는 EMA/Wilder 시드 컨벤션이
  달라 byte-identical일 수 없다. "백엔드 패리티" 대신 결정적 fixture 기반
  자체 스냅샷으로 — data.js 드리프트 회귀 가드.
- **스모크 자체 서버(:5599)** — 개발 서버와 무충돌, 단일 명령 실행.
- **대표 입력 원칙** — `and`/`or` 버그가 샌 이유는 기존 API 테스트가
  단일 조건(`SMA_20 > SMA_60`)만 썼기 때문. 회귀 테스트는 빌트인 5종의
  *실제* 식을 parametrize한다.

---

## 6. Quality Metrics

| 지표 | 값 |
|------|-----|
| 설계-구현 일치율 | **99%** (v1.0 98% → v1.1 99%) |
| Critical / High / Medium 갭 | 0 / 0 / 0 |
| 백엔드 테스트 | 175 passed (사이클 시작 165 → +10) |
| 프론트 테스트 | `node --test` 2/2 (loader + indicators) |
| 프론트 스모크 | 10/10 (5탭 + 인터랙션 4종) |
| 신규 회귀/테스트 자산 | `test_regression.py`, `smoke.py`, `indicators.test.mjs`, `indicator-golden.json` |

---

## 7. Process Lessons

1. **"테스트 통과 ≠ 기능 동작"** — 이 사이클의 전제. P0-1이 첫날 BB 버그를
   잡으며 즉시 입증.
2. **대표 입력이 핵심** — 단위 테스트 수가 아니라 *실사용 경로*를 타는
   입력으로 검증해야 한다.
3. **설계 검증을 구현 전에** — v0.2의 F1(patch_fetch 우회)을 코딩 전에 잡아
   R-3을 처음부터 올바르게 설계했다.
4. **구현이 설계를 교정한다** — v0.3은 Phase 3 구현이 §5.2 전제의 오류를
   드러낸 결과. 설계를 사후 갱신하는 것이 정직한 PDCA.

---

## 8. Next Cycle Roadmap

- **P1-2 빌드 파이프라인** — 별도 PDCA 사이클(plan→design→do). 인-브라우저
  Babel 제거는 개발 흐름·npm 툴링·모듈 구조에 영향이 커 독립 사이클 필요.
- **프론트 테스트 러너 통합** — `loader`/`indicators` `.mjs`를 CI 단일 명령으로.
- **P2-1 컨플루언스 시각화** — 현재 툴팁만. at-a-glance 마커 표현은 옵션.
- (지표 리포트 §6 잔여) 추가 검토 항목.

---

## 9. Sign-Off

improvement-plan 사이클 완료. Match Rate 99%, Critical/High/Medium 갭 0.
검증 레이어(P0+P1)가 구축됐고 P2 개선 4종 + OBV가 반영됐다. `/pdca archive`
대상.

---

## Version History

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-16 | 최초 완료 보고서 — Plan/Design v0.3/Do Phase 1~4/Check 통합. 99% |
