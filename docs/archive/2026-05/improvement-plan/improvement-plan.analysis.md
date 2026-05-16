---
template: analysis
version: 1.0
feature: improvement-plan
date: 2026-05-16
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.10.0
---

# Gap Analysis — improvement-plan v0.10.0

> **Source**: Design v0.3 ↔ Implementation (Phase 1~4)
> **Match Rate**: **99%** (v1.1) — Critical/High/Medium 0, Low 1 → `/pdca report` 진행 가능
> v1.0 baseline: 98% (Low 2). 갭 분석 직후 사용자 요청으로 **L-1(P2-3 OBV)
> 사후 구현 완료**, **L-2(P1-2)는 별도 PDCA 사이클로 확정**.
> **Evidence**: backend `pytest` 175 passed · `node --test` 2/2 · smoke 10/10

---

## 1. Match Rate Summary

| 구분 | 결과 |
|------|------|
| 설계 in-scope 항목 | 전부 구현·검증 완료 |
| Critical / High / Medium 갭 | 0 / 0 / 0 |
| Low 갭 | 2 — 모두 *결함이 아닌 의도된 보류* |
| 설계 외 추가 성과 | BB 점-컬럼명 버그 발견·수정 (P0-1 부수 효과) |

이번 사이클은 기능 추가가 아니라 **검증 레이어 구축**이 목표였고, 그 목표를
달성했다. 회귀 테스트 3종(백엔드 통합·프론트 스모크·지표 골든)이 양 코드베이스를
지킨다.

---

## 2. Coverage Matrix

| 설계 항목 | 사양 | 구현 | 상태 |
|-----------|------|------|:----:|
| §3 P0-1 R-1 | 빌트인 5종 backtest (parametrize) | `test_regression.py` R-1 | ✅ |
| §3 P0-1 R-2 | `or`/`not` 식 평가 | `test_regression.py` R-2 | ✅ |
| §3 P0-1 R-3 | KR 주/월봉 **tz-aware** (어댑터 레벨) | `test_data_loader.py` `test_kr_resample_accepts_tz_aware_start` | ✅ |
| §3 P0-1 R-4 | MACD 시그널선 워밍업 | `test_regression.py` R-4 | ✅ |
| §3 P0-1 R-5 | 신호 shape | `test_regression.py` R-5 | ✅ |
| §3.1 픽스처 재사용 | 신규 `golden_ohlcv` 폐기 | `conftest`의 `synthetic_df` 재사용 | ✅ |
| §4 P0-2 스모크 | 5탭 + 인터랙션 4종, 자체 서버 | `tests/e2e/smoke.py` (10 checks) | ✅ |
| §4 부속 | README + `requirements-dev.txt` | 둘 다 생성 | ✅ |
| §5 P1-1 선행 | `rpb`/`wilderRma` export | `data.js` helpers | ✅ |
| §5 P1-1 골든 | data.js 자체 스냅샷 (v0.3) | `indicators.test.mjs` + `indicator-golden.json` | ✅ |
| §7 P2-1 | 컨플루언스 점수 | `signalConfluence` + 마커 툴팁 `동의 N/3` | ✅ |
| §7 P2-2 | 밴드 상호배타 토글 | `getSetter` BB↔RPB 차단 | ✅ |
| §7 P2-4 | 정밀 패닝 | `pan(dir,bars)` + 키보드 ←/→ | ✅ |
| §7 P2-5 | AI 키 안내 배너 | `window.__groqConfigured` + 배너 | ✅ |
| §9 DoD P0-1/P0-2/P1-1 | 회귀·스모크·골든 PASS | 174 / 10·10 / 2·2 | ✅ |
| §6 P1-2 | 빌드 파이프라인 | 미구현 — **설계가 "이번 사이클 비대상" 명시** | ➖ |
| §7 P2-3 | 거래량 지표 OBV | 미구현 — 사용자 미선택 | ⚠️ |

### 설계 외 추가 성과 (positive deviation)

- **BB 점-컬럼명 버그 수정** — R-1이 BB Squeeze 빌트인을 잡았다. BB 컬럼명
  `BBL_20_2.0_2.0`의 점(.) 때문에 DSL `ast.parse` 실패 → 빌트인 실행 불능.
  설계는 이 버그를 예측하지 못했으나 P0-1 회귀 스위트가 정확히 의도대로
  새 결함을 잡아냈다. 9개 파일에 걸쳐 dot-free(`BBL_20`)로 수정. 개선 플랜의
  전제("검증 레이어가 결함을 잡는다")를 첫 구현에서 실증.

---

## 3. Gaps

### Critical: 0
### High: 0
### Medium: 0

### Low: 1 (+ 1 해소)

- **L-1 — P2-3 거래량 지표(OBV)** — ✅ *v1.1 해소*: 갭 분석 직후 사용자
  요청으로 구현 완료. `add_obv` (backend) + `data.js` `obv` + 차트 거래량
  패널 OBV 오버레이 + `BUILTIN_INDICATORS` 카탈로그. backend 175 passed.
- **L-2 — P1-2 빌드 파이프라인 미구현**: 설계 §6이 "이번 사이클 비대상"으로
  스코프 제외. *v1.1: 사용자가 별도 PDCA 사이클로 진행하기로 확정* — 이
  사이클의 갭 아님.

---

## 4. Implementation Quality Notes

### 잘한 점

1. **설계가 구현에 의해 두 번 교정됨** — 검증 단계에서 v0.2(F1~F7), Phase 3
   구현 중 v0.3(§5.2 backend-parity 전제 폐기). 설계 문서가 살아있는 기준선.
2. **R-3의 정확한 격리** — `patch_fetch`가 `krx_adapter`를 우회한다는 점을
   설계 v0.2에서 미리 잡아, R-3을 어댑터 레벨에 배치 → tz 버그 경로를 실제로
   탄다.
3. **결정적 골든 픽스처** — RNG·초월함수를 배제해 스냅샷이 머신 독립적.
4. **스모크 자체 서버(:5599)** — 개발 서버(:5500)와 무충돌, 단일 명령 실행.
5. **회귀 테스트가 첫날 새 버그를 발견** (BB 컬럼명) — 투자 대비 즉시 효과.

### 개선 여지

- **L-1/L-2 보류 항목** — 차기 사이클에서 다룰지 명시 필요.
- **P2-1 컨플루언스 시각화** — 현재 툴팁(`동의 N/3`)만. at-a-glance 표시
  (마커 크기 등)는 미적용 — 클러터 회피 위한 의도적 선택이나, 추후 옵션.
- **프론트 테스트 러너 통합** — `loader`/`indicators` 두 `.mjs`를 개별 실행.
  CI에서 단일 명령으로 묶는 스크립트는 미정.

---

## 5. Recommendation

Match Rate **98%** (Critical/High/Medium 0). 설계 in-scope 항목 전부 구현·
검증 완료, 갭은 의도된 보류 2건뿐. **`/pdca report` 진행 가능.**

차기 사이클(v0.11) 후보: P2-3 거래량 지표 · P1-2 빌드 파이프라인 · 프론트
테스트 러너 통합.

---

## Version History

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-16 | 최초 갭 분석 — Design v0.3 ↔ Phase 1~4 구현. 98%, Critical/High/Medium 0 |
| 1.1 | 2026-05-16 | 사후 반영 — L-1(P2-3 OBV) 구현 완료로 해소, L-2(P1-2)는 별도 PDCA 사이클로 확정. **99%** |
