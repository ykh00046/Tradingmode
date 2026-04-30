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
| v0.5 | M-2~M-6, L-1~L-7, S-1 정합화 (1~2일) |
| v2 | 포트폴리오 백테스팅 + 종목 상관관계 + 뉴스 sentiment + 실시간 알림 |
| v3 | 자동매매 (KIS/키움/Binance Trade) + 안전장치 (kill switch, dry-run, 일일 한도) |

---

## 📁 Archive 정책

- 각 feature는 `{feature_name}/` 하위 폴더에 plan/design/analysis/report 4종 문서 보관
- _INDEX.md에 종료일·매칭률·요약·다음 사이클 후보 기록
- 코드는 GitHub에 그대로 유지 (별도 백업 X)
- 30일 이상 지난 archived feature는 압축 백업 검토 (선택)
