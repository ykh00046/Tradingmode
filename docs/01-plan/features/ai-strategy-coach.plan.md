---
template: plan
version: 1.2
feature: ai-strategy-coach
date: 2026-04-30
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.5.0
---

# ai-strategy-coach Planning Document

> **Summary**: 사용자가 매매 전략을 정의하면 백테스트 결과를 AI(Groq llama-3.3-70b)가 분석해 보완 지표를 추천하고, 추천을 적용해 다시 백테스트하는 **반복 협업 루프**. 70/30 holdout으로 과적합 방지, iteration 이력 영구 저장.
>
> **Project**: trading-analysis-tool
> **Version**: 0.5.0 (이전 사이클 0.4.1 위에 누적)
> **Author**: 900033@interojo.com
> **Date**: 2026-04-30
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

기존 시스템(v0.4.1)은 빌트인 전략(MA Cross 1종)으로만 백테스트가 가능하며, 새 지표나 전략은 코드 수정이 필요했다. 본 사이클은 다음을 추가한다:

1. **사용자 정의 전략 백테스트**: 빌트인 지표 + 임계값/룰 조합으로 전략 정의 (코드 편집 없이 UI/JSON)
2. **AI 코치**: 백테스트 결과를 LLM에 전달하여 약점 진단 + 보완 지표 추천 + 우려점 출력
3. **추천 적용 + 재백테스트**: 추천 지표 클릭 → 자동 결합 → 재실행
4. **과적합 방지**: 70/30 split — AI는 In-sample(70%)만 보고 추천, Out-of-sample(30%)로 진짜 성능 검증
5. **이력 비교**: 시도별 결과를 parquet에 영구 저장, 세션 내에서 표/그래프 비교

### 1.2 Background

- v0.4.1 시스템 archived (matchRate 99%, 8 종목 실데이터 동작 확인)
- 사용자 피드백: "내가 만든 지표 + AI 추천 → 반복 테스트" 워크플로우가 현재 시스템의 핵심 차별화
- TradingView 등 시중 도구에 **AI 자동 추천 + iterative loop**가 거의 없음
- Groq llama-3.3-70b-versatile 무료 tier 30 req/min — 충분
- 빌트인에 없는 지표 추천 시 사용자가 Claude(개발자 채널)에 요청해 코드 추가 → 워크플로우 명확

### 1.3 Related Documents

- 이전 사이클: `docs/archive/2026-04/trading-analysis-tool/` (Plan/Design/Analysis/Report)
- 기존 코드 활용: `backend/core/{indicators, signals, backtest, ai_interpreter}.py`
- 외부: Groq Python SDK (Context7 `/groq/groq-python`), backtesting.py

---

## 2. Scope

### 2.1 In Scope

- [ ] **사용자 전략 정의(JSON)**: 빌트인 지표 + 매매 룰 (예: `{"buy": "RSI_14 < 30 AND ADX_14 > 25", "sell": "RSI_14 > 70"}`)
- [ ] **POST /api/strategy/backtest**: 사용자 전략 받아 70/30 split 백테스트 → In-sample + Out-of-sample 결과 둘 다 반환
- [ ] **POST /api/ai/strategy-coach**: 백테스트 결과 + 전략 + 시장 컨텍스트 → LLM이 약점 진단 + 보완 지표 3개 + 우려점
- [ ] **빌트인 외 지표 추천 처리**: AI가 자유 추천, 빌트인 미존재 시 응답에 `available: false` 플래그 + Claude 추가 요청 가이드
- [ ] **추천 적용 → 재백테스트**: 추천 카드 클릭 시 사용자 전략에 자동 결합 후 재실행
- [ ] **Iteration 이력**: 시도별 (전략 정의 + 결과 + 추천 + 적용 여부) 세션 메모리 + parquet 영구 저장
- [ ] **이력 비교 UI**: 표 형식으로 시도들 나란히 (수익률/MDD/샤프/승률 등)
- [ ] **최적화 목표 선택**: 매 iteration마다 사용자가 (수익/샤프/MDD/승률) 중 1개 선택 → AI 프롬프트에 반영
- [ ] **거래 비용 명시**: commission(BPS)/slippage(BPS)/세금(KR 주식 0.18% 매도 기본) 입력란
- [ ] **Strategy Coach 페이지** (5번째 탭): 좌측 전략 편집 / 중앙 결과 / 우측 AI 코치 카드 / 하단 이력
- [ ] **이전 사이클 백로그 일부 흡수**: M-3 (`/api/trend?series=true`) 추가하여 차트와 일관성 보강

### 2.2 Out of Scope

- 사용자 정의 **수식 지표** (예: `MA(20) - MA(60)`) — Claude가 코드로 추가하는 방식 유지 (DSL 파서 불필요)
- 실시간 자동매매 — v3 사이클 별도
- 멀티 자산 동시 최적화 (포트폴리오 백테스팅) — v2 별도
- AI가 생성한 추천 거절 학습(메모리) — 단순(같은 세션 내 재추천 OK)
- Walk-forward 분석 — 70/30 split만 (정밀 분석은 v2)
- AI 추천 자동 적용 — 항상 사용자 승인 필요(안전)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 사용자 전략 정의 스키마 — 매수/매도 조건 expression(빌트인 지표 컬럼명 + 비교/논리 연산자) | High | Pending |
| FR-02 | POST /api/strategy/backtest — 단일 종목 + 사용자 전략 → In-sample(70%) + Out-of-sample(30%) 결과 둘 다 | High | Pending |
| FR-03 | 70/30 split: 시간순 앞 70% In-sample(IS), 뒤 30% Out-of-sample(OOS). IS로 전략 백테스트, OOS는 동일 룰로 검증만 | High | Pending |
| FR-04 | POST /api/ai/strategy-coach — Groq에 IS 결과+전략+사용자 목표 전달, 약점/추천/우려 JSON 반환 | High | Pending |
| FR-05 | AI 추천 카드: 지표명 + 파라미터 + 추천 사유 + 빌트인 가용 여부 | High | Pending |
| FR-06 | 추천 적용 버튼: 클릭 시 사용자 전략에 추천 조건 자동 추가 후 재백테스트 | High | Pending |
| FR-07 | Iteration 이력 저장 — 시도별 (id, 전략, 결과 IS/OOS, 추천, 적용 여부, ts) parquet 영구 | High | Pending |
| FR-08 | 이력 비교 UI — 표로 누적, 컬럼: 시도N · IS수익 · OOS수익 · IS-OOS gap · MDD · 샤프 · 룰 요약 | Medium | Pending |
| FR-09 | 최적화 목표 선택 (수익률/샤프/MDD/승률) — AI 프롬프트에 명시적 전달 | High | Pending |
| FR-10 | 거래 비용 입력 — commission BPS, slippage BPS, KR 주식 매도세 0.18% 기본 | Medium | Pending |
| FR-11 | Strategy Coach 페이지 (5번째 탭) — 편집/결과/AI/이력 4분할 | High | Pending |
| FR-12 | 빌트인 외 지표 추천 시 ⚠️ 카드 + "Claude에 추가 요청" 가이드 텍스트 표시 | Medium | Pending |
| FR-13 | `/api/trend?series=true` — 시계열 추세 반환 (백로그 M-3 흡수, 프론트 도메인 로직 중복 제거) | Low | Pending |
| FR-14 | IS/OOS 결과 시각화 — equity curve 둘 다 한 차트에 (다른 색), gap 표시 | Medium | Pending |
| FR-15 | AI 응답 캐시 — (전략 hash + 결과 hash + 목표 + model) 키로 디스크 영구 캐시 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| Performance | 단일 종목 1년치 70/30 백테스트 < 3초 (캐시 hit 기준) | `time.perf_counter` |
| AI Cost | 매 iteration AI 호출 1회 (Groq 무료 30 req/min 충분) | 로그 카운터 |
| Reliability | AI 응답 파싱 실패 시 사용자 친화적 메시지 + 결과는 그대로 표시 | 단위 테스트 (mock LLM) |
| Safety | 추천 자동 적용 X, 항상 사용자 승인 후 재백테스트 | 코드 리뷰 |
| Reproducibility | 동일 전략 + 동일 데이터 → 동일 백테스트 결과 (LLM 제외) | 단위 테스트 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 High 우선순위 FR 구현 완료
- [ ] BTC/USDT 1년 일봉으로 end-to-end 시연: 사용자 전략 → 70/30 백테스트 → AI 추천 3개 → 1개 적용 → 재백테스트 → 이력 표 비교
- [ ] 빌트인 외 지표 추천 케이스 시연 (AI가 모르는 지표 추천 → ⚠️ 카드 + 사용자가 Claude에 요청 → 추가 후 재시도)
- [ ] 백엔드 새 endpoint 2개 (`/api/strategy/backtest`, `/api/ai/strategy-coach`) + `/api/trend?series=true` 추가, 통합 테스트 통과
- [ ] start.bat → 정상 기동, 5번째 "Strategy Coach" 탭 동작
- [ ] README에 Strategy Coach 사용법 + 안전성 면책 문구 추가

### 4.2 Quality Criteria

- [ ] 백엔드 단위 테스트 ≥ 90% pass (기존 75 + 신규 ~20개)
- [ ] Gap Analysis 매치율 ≥ 90%
- [ ] 빌드/실행 시 에러 0건
- [ ] 70/30 split 검증: In-sample 압도적 좋음 + Out-of-sample 평범 = "과적합 위험" 경고 자동 표시
- [ ] AI 환각 검증: 명백히 잘못된 지표명(예: "RSI_999") 추천 시 ⚠️ 처리

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **AI 환각 — 효과 없는 지표 추천** | High | High | 70/30 OOS 결과로 진짜 성능 검증. AI 추천은 *가설*임을 UI에 명시 |
| **과적합 — 같은 데이터 반복 추천 누적** | High | High | OOS 결과를 매 iteration 표시. IS-OOS gap > 30% 시 경고 |
| 사용자 전략 expression 파싱 안전성 (Python eval) | High | Medium | `pandas.eval` 안전 모드 사용 또는 화이트리스트 토큰만 허용 |
| Groq Rate Limit (free tier) | Medium | Low | 동일 입력 응답 캐시, 매 iteration 1회만 호출 |
| 빌트인 외 지표 추천 시 사용자 혼란 | Medium | High | UI ⚠️ 카드 + 명확한 다음 단계(Claude 요청) 가이드 |
| 거래 비용 제외하면 비현실적 결과 | High | Medium | UI 기본값(0.05% 수수료)로 시작, 사용자 조정 가능 |
| KR 주식 매도세(0.18%) 누락 시 KR 백테스트 부정확 | Medium | Medium | KR 종목 자동 감지하여 매도세 자동 적용 (토글 가능) |
| AI 응답 JSON 파싱 실패 | Medium | Medium | response_format=json_object 강제 + 검증 + fallback "AI 분석 사용 불가" 메시지 |
| 사용자 전략이 너무 단순/복잡 | Low | High | 기본 템플릿 3개 제공 (보수/중립/공격), 사용자가 수정 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Selected |
|-------|:--------:|
| Starter | ☐ |
| **Dynamic** | ☑ |
| Enterprise | ☐ |

기존 사이클(v0.4.1)이 Dynamic 레벨이고 본 사이클은 그 위에 추가하는 기능이므로 동일 레벨 유지.

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 사용자 전략 표현 | Python eval / pandas.eval / 자체 AST 파서 / DSL | **pandas.eval** (안전 모드) | numpy 함수만 허용, 표준 라이브러리, 안전 |
| Holdout 방식 | 70/30 / 80/20 / Walk-forward | **70/30 시간순 split** | 단순, 명확, 사용자 결정 |
| 이력 저장 | SQLite / parquet / JSON | **parquet** | 기존 캐시와 일관, 컬럼 효율 |
| AI 프롬프트 구조 | 자유형 / 구조화 JSON | **구조화 JSON** | response_format=json_object로 강제 |
| 빌트인 지표 풀 | AI에 명시 / 자유 추천 | **자유 + 검증** (사용자 결정 B) | UI에서 ⚠️ 처리 |
| 거래 비용 | 단일 commission / 분리(comm/slip/tax) | **분리** | 사용자 결정 5번 |
| 추천 거절 학습 | 누적 / 단순(재추천 OK) | **단순** | 사용자 결정 6번 |
| 시연 종목 | 다종목 / 단일 | **BTC/USDT 위주** + 005930 보조 | 사용자 결정 7번 |

### 6.3 폴더 구조 (기존에 추가)

```
C:/X/new/
├── backend/
│   ├── api/
│   │   ├── strategy.py          # ✨ NEW: POST /api/strategy/backtest
│   │   ├── ai.py                # 갱신: + POST /api/ai/strategy-coach
│   │   └── trend.py             # 갱신: + ?series=true
│   ├── core/
│   │   ├── strategy_engine.py   # ✨ NEW: pandas.eval 기반 룰 평가 + 70/30 split
│   │   ├── strategy_coach.py    # ✨ NEW: AI 코치 프롬프트 빌더 + 응답 파서
│   │   ├── iteration_log.py     # ✨ NEW: parquet 이력 저장/조회
│   │   └── types/schemas.py     # 갱신: + StrategyDef, BacktestSplitResult, CoachRecommendation, IterationEntry
│   └── tests/
│       ├── test_strategy_engine.py     # ✨
│       ├── test_strategy_coach.py      # ✨
│       └── test_api/test_strategy.py   # ✨
│
├── Tradingmode/
│   ├── strategy-coach-page.jsx  # ✨ NEW: 5번째 탭
│   ├── api.js                   # 갱신: + api.strategyBacktest / api.strategyCoach
│   ├── loader.js                # 갱신: trend series 활용
│   └── app.jsx                  # 갱신: 5번째 탭 등록
│
└── data/
    └── _iterations/             # ✨ NEW: parquet 이력 (BTCUSDT_1d.parquet 등)
```

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

이전 사이클의 컨벤션 그대로 유지:
- [x] Python 3.11+, pandas-ta 0.4.x
- [x] FastAPI + Pydantic v2
- [x] React 18 (CDN), Babel standalone
- [x] pytest (75 tests baseline)
- [x] CORS / .env / parquet 캐시 정책

### 7.2 Conventions to Define

| Category | New | Priority |
|----------|-----|:--------:|
| 사용자 전략 JSON 스키마 (validation) | StrategyDef Pydantic 모델 | High |
| Iteration entry parquet 스키마 | timestamp, strategy_hash, is_stats, oos_stats, recommendation, applied | High |
| AI 코치 프롬프트 템플릿 위치 | `core/strategy_coach.py` 상단 SYSTEM_PROMPT 상수 | Medium |
| 안전 expression 화이트리스트 | indicator 컬럼명 + 비교/논리 연산자만 | High |

### 7.3 Environment Variables Needed

기존 변수 그대로 + 신규:

| Variable | Purpose |
|----------|---------|
| `ITERATION_LOG_DIR` | iteration 이력 parquet 저장 경로 (기본 `./data/_iterations`) |
| `STRATEGY_COACH_MODEL` | AI 코치 모델 (기본 `llama-3.3-70b-versatile`, 동일 GROQ_MODEL 재사용) |
| `MAX_STRATEGY_RULES` | 단일 전략의 최대 룰 수 (기본 10) |

### 7.4 Pipeline Integration

기존 v0.4.1 + Phase 7(SEO/Security) 검토 추가 고려.

---

## 8. Next Steps

1. [ ] 사용자 검토 및 Plan 승인
2. [ ] Design 문서 작성 (`/pdca design ai-strategy-coach`)
   - 핵심: StrategyDef JSON 스키마, AI 코치 프롬프트, 70/30 split 알고리즘, parquet 이력 스키마
3. [ ] 구현 시작 (`/pdca do ai-strategy-coach`)
4. [ ] Gap Analysis (`/pdca analyze ai-strategy-coach`)

**예상 작업량**: ~9시간 (1.5일)
- Phase A (백엔드 strategy_engine + 70/30 split): 3시간
- Phase B (백엔드 strategy_coach + iteration_log): 3시간
- Phase C (프론트 strategy-coach-page.jsx + 이력 표): 3시간

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-30 | 초안 — 사용자 요구사항 기반 (빌트인 외 자유 추천, 이력 영구+세션, 70/30 split, 매번 목표 선택, BTC 위주) | 900033@interojo.com |
