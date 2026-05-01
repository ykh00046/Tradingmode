# Archive — 2026-04

> 본 디렉토리는 PDCA 사이클이 완료된 feature의 모든 문서를 보관합니다.
> 해당 월(YYYY-MM)에 종료된 feature가 시간순으로 누적됩니다.

---

## 📦 Archived Features

### 1. trading-analysis-tool

| 항목 | 값 |
|---|---|
| **종료일** | 2026-04-30 |
| **최종 Match Rate** | 99% |
| **Iterations** | 1 (act-1) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |

**한 줄 요약**: 암호화폐(Binance Spot) + 한국 주식(KOSPI/KOSDAQ) 통합 분석 툴 — React SPA + FastAPI 분리 아키텍처, AI 신호 해석(Groq), 포트폴리오 일괄 분석, 자동매매 v3 placeholder.

**보관 문서** (`./trading-analysis-tool/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [trading-analysis-tool.plan.md](trading-analysis-tool/trading-analysis-tool.plan.md) | 319 | Plan v0.4.1 — 21 FRs, 9 리스크, 아키텍처 결정 |
| [trading-analysis-tool.design.md](trading-analysis-tool/trading-analysis-tool.design.md) | 1,767 | Design v0.4.2 — 9 REST 엔드포인트, Pydantic 12, dataclass 20 |
| [trading-analysis-tool.analysis.md](trading-analysis-tool/trading-analysis-tool.analysis.md) | 214 | Gap 분석 v1.1 — 95% → 99%, Iteration 1 결과 |
| [trading-analysis-tool.report.md](trading-analysis-tool/trading-analysis-tool.report.md) | 504 | 통합 완료 보고서 + v0.5/v2/v3 로드맵 |

**핵심 결과**

- 백엔드 38 파일, 75/75 테스트 PASSED (1.13초)
- 프론트엔드 10 파일 (React 18 SPA, 사용자 제공 프로토타입 + api.js + loader.js)
- 9 REST 엔드포인트 (OHLCV/Indicators/Signals/Trend/AI/Portfolio/Backtest/Market/Health)
- end-to-end 검증: BTC $75,900 + 005930 ₩226,000 + 124 신호 + ₩209M 포트폴리오
- 캐시 hit 13배 가속 (521ms → 39ms)

**다음 사이클 후보 (백로그)**

| 차기 사이클 | 주제 |
|---|---|
| ~~v0.5~~ | ✅ ai-strategy-coach 사이클로 흡수됨 (아래) |
| v0.6 | 거절 학습 누적, walk-forward 분석 |
| v0.7 | 사용자 정의 수식 지표 (AST 안전 모드 확장) |
| v2 | 포트폴리오 백테스팅 + 종목 상관관계 + 뉴스 sentiment + 실시간 알림 |
| v3 | 자동매매 (KIS/키움/Binance Trade) + 안전장치 (kill switch, dry-run, 일일 한도) |

---

### 2. ai-strategy-coach (v0.5.0)

| 항목 | 값 |
|---|---|
| **종료일** | 2026-04-30 |
| **최종 Match Rate** | **97%** (Critical/High 0건) |
| **Iterations** | 0 (97% ≥ 90% — iterate 건너뜀) |
| **상태** | completed → archived |
| **GitHub** | https://github.com/ykh00046/Tradingmode |

**한 줄 요약**: 사용자 정의 매매 전략 + 70/30 split 백테스트 + Groq llama-3.3-70b AI 보완 지표 추천 + parquet 영구 이력의 반복 협업 루프. 빌트인 외 추천 시 ⚠️ 카드로 Claude 추가 요청 워크플로우.

**보관 문서** (`./ai-strategy-coach/`)

| 문서 | 라인 | 설명 |
|------|-----:|------|
| [ai-strategy-coach.plan.md](ai-strategy-coach/ai-strategy-coach.plan.md) | 282 | Plan v0.1 — 15 FRs, 9 리스크, 7 사용자 결정사항 |
| [ai-strategy-coach.design.md](ai-strategy-coach/ai-strategy-coach.design.md) | 1,016 | Design v0.2 — design-validator 84% → 92% 보강 |
| [ai-strategy-coach.analysis.md](ai-strategy-coach/ai-strategy-coach.analysis.md) | 168 | Gap 분석 v1.0 — 97% match, Critical/High 0 |
| [ai-strategy-coach.report.md](ai-strategy-coach/ai-strategy-coach.report.md) | 568 | 통합 완료 보고서 + Design v0.3 갱신 권장 + v0.6/v0.7/v2 로드맵 |

**핵심 결과**

- 백엔드 132/132 테스트 PASSED (이전 75 + 신규 57)
- 13 REST 엔드포인트 (이전 9 + 신규 4: backtest/builtins/iterations/strategy-coach)
- 신규 도메인: StrategyDef DSL, BacktestSplitResult, CoachResponse, IterationEntry, BuiltinIndicator, OptimizationGoal, TradingCosts
- e2e 검증: BTC/USDT MA Crossover → IS -2.08% / OOS 0.00% / Stochastic 추천(⚠️ 빌트인 미존재)
- **Design 단계 투자 효과 입증**: v0.4 첫 78%→95% / v0.5 첫 84%→**97%** (+2pt 깔끔한 시작)

**핵심 안전 장치**
- AST 화이트리스트 — Lambda/Subscript/Attribute/walrus 모두 거부
- Prompt injection 방어 — 사용자 룰을 `json.dumps()` value로만 인용
- 70/30 split graceful — OOS<30봉 시 IS만 반환 + warning
- 추천 자동 적용 X — 항상 사용자 승인 필수
- BPS 상한 — commission/slippage ≤100, kr_sell_tax ≤50

---

## 📁 Archive 정책

- 각 feature는 `{feature_name}/` 하위 폴더에 plan/design/analysis/report 4종 문서 보관
- _INDEX.md에 종료일·매칭률·요약·다음 사이클 후보 기록
- 코드는 GitHub에 그대로 유지 (별도 백업 X)
- 30일 이상 지난 archived feature는 압축 백업 검토 (선택)
