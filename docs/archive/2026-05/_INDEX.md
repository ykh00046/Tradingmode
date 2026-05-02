# Archive — 2026-05

> 본 디렉토리는 2026년 5월에 PDCA 사이클이 완료된 feature를 보관합니다.

---

## 📦 Archived Features

### 1. rsi-price-bands (v0.6.0)

| 항목 | 값 |
|---|---|
| **종료일** | 2026-05-02 |
| **최종 Match Rate** | **98%** (Critical/High 0건, 전체 사이클 중 최고) |
| **Iterations** | 0 (98% ≥ 90%, iterate 불필요) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |
| **사이클 크기** | 작은 사이클 (3시간) |

**한 줄 요약**: 사용자 제공 Pine Script v5 "RSI Price Band" 알고리즘 채택. RSI 공식을 역산해 "다음 봉이 X로 마감하면 RSI=N" 가격 12개 컬럼(가격 6 + ATR 단위 거리 6)을 빌트인 지표에 추가. Strategy DSL에서 선행 신호 룰 작성 가능.

**보관 문서** (`./rsi-price-bands/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [rsi-price-bands.plan.md](rsi-price-bands/rsi-price-bands.plan.md) | 256 | Plan v0.1 — 11 FRs, Pine 컨셉 + 양방향+BARS 보완 |
| [rsi-price-bands.design.md](rsi-price-bands/rsi-price-bands.design.md) | ~600 | Design v0.2 — design-validator 91% → 95% 보강 |
| [rsi-price-bands.analysis.md](rsi-price-bands/rsi-price-bands.analysis.md) | ~150 | Gap v1.0 — 98% match, Critical/High 0 |
| [rsi-price-bands.report.md](rsi-price-bands/rsi-price-bands.report.md) | 450 | 통합 보고서 + Design v0.3 권장 + v0.7+ 로드맵 |

**핵심 결과**

- 백엔드 147/147 PASSED (이전 132 + 신규 15)
- 13 REST endpoint 변경 없음 (`RPB_` prefix 자동 인식 → `/api/indicators` 12 컬럼 추가)
- BUILTIN_INDICATORS 5 → 6 (Strategy Coach AI 코치 자동 노출)
- e2e Playwright (BTC/USDT 1년):
  - RPB_UP_70 = $80,047 (현재가 $76,330 +5.0%)
  - 6 라인 + 6 라벨 차트 오버레이 (Pine 모방)
  - 단방향(RSI≥50→상단)/양방향 토글 동작
  - "RSI Imminent" 5번째 템플릿 등록

**Pine Script 검토 시 채택한 보완 2가지**
1. **양방향 항상 계산** — 백엔드 12 컬럼 모두, UI 단방향 토글
2. **`_BARS` 컬럼 6개 추가** — `(price - close) / ATR` (음수 OK = 이미 통과). AI 코치 룰 활용

---

## 📊 학습 효과 정량화 (전체 3 사이클 누적)

| 사이클 | Design 첫 검증 | Design 보강 후 | 구현 매치율 | Iterate |
|--------|---------------:|---------------:|------------:|:-------:|
| v0.4.1 trading-analysis-tool | 78% | 95% | 95% | 1회 → 99% |
| v0.5.0 ai-strategy-coach | 84% | 92% | 97% | 0회 |
| **v0.6.0 rsi-price-bands** | **91%** | **95%** | **98%** | **0회 ← 최고** |

**관찰**: Design 첫 검증 점수가 사이클마다 +6~7pt 상승. 학습된 PDCA 패턴 누적 개선 — 차후 사이클은 첫 검증부터 95%+ 기대.

---

## 📁 Archive 정책

- 각 feature는 `{feature_name}/` 하위 폴더에 plan/design/analysis/report 4종 보관
- _INDEX.md에 종료일·매칭률·요약·다음 사이클 후보 기록
- 코드는 GitHub에 그대로 유지

## 🗓️ 이전 월 archive

- [`../2026-04/`](../2026-04/_INDEX.md) — trading-analysis-tool (99%) + ai-strategy-coach (97%)
