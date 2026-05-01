---
template: analysis
version: 1.0
feature: ai-strategy-coach
date: 2026-04-30
author: 900033@interojo.com
project: trading-analysis-tool
matchRate: 97
phase: check
---

# ai-strategy-coach — Gap Analysis Report

> **Match Rate**: **97%** (Critical 0 · High 0 · Medium 2 · Low 7)
> **Date**: 2026-04-30
> **Design**: v0.2 (84% → 92% 보강 후)
> **Backend**: 132/132 tests PASSED
> **Frontend**: e2e Playwright 검증 완료

이전 사이클 v0.4.1 첫 검증 95% 대비 +2pt — Design 단계 검증을 78%(v0.4) / 84%(v0.5) 첫 측정 후 보강해 92%까지 올린 효과로 추정.

---

## 1. 영역별 매칭률

| Category | Score | Status |
|----------|:-----:|:------:|
| Plan FR Coverage (FR-01~15) | 100% | ✅ |
| §3 Domain/Pydantic Schemas | 96% | ✅ |
| §4.2 Function Signatures | 90% | ⚠️ |
| §4.3 REST Endpoints | 100% | ✅ |
| §5 UI | 98% | ✅ |
| §6 Error Handling | 100% | ✅ |
| §7 Security | 100% | ✅ |
| §10 Convention + env | 95% | ✅ |
| §12 Out-of-scope | 100% | ✅ |
| **Overall** | **~97%** | ✅ |

---

## 2. Critical / High Gap

**없음.** 구현 차단 또는 사용자 영향 사안 0건.

---

## 3. Medium Gap (디자인 문서 갱신 권장)

### M-1. CoachRequest 스키마가 Design §3.2와 일부 다름
- **위치**: `backend/api/schemas.py:330` `StrategyCoachRequest`, `backend/api/ai.py:117-128`
- **차이**: Design은 `{strategy, market, symbol, is_result: BacktestResultResponse, builtin_indicators: list[str], history_summary}`. 구현은 `{strategy, is_result: IsResultSummary, history_summary}` — `market/symbol/builtin_indicators` 제거 + 6 scalar summary 도입.
- **이유**: 서버가 권위 있는 `BUILTIN_INDICATORS` 보유, 클라이언트 forwarding은 spoofing 위험. 의도적·합리적 결정.
- **조치**: Design v0.3에서 §3.2 / §4.5 갱신 (구현 정합화 권장)

### M-2. `evaluate_rules`가 numexpr-first 정책 미적용
- **위치**: `backend/core/strategy_engine.py:200`
- **차이**: Design §4.2는 "engine='numexpr' 우선, Call 노드만 'python' fallback". 구현은 항상 `engine='python'`.
- **이유**: DSL이 `Call` 노드(prev/abs/min/max/mean) 허용, numexpr은 미지원. 안전성은 AST validator가 담당.
- **조치**: Design §4.2의 numexpr 우선 절 삭제 (Design 갱신) 또는 wrapper 추가. **권장: Design 정정** (안전 모델 변화 없음)

---

## 4. Low Gap (Housekeeping)

| ID | 위치 | 문제 | 조치 |
|---|---|---|---|
| L-1 | `strategy_coach.py:286` | `recommend()` 시그니처가 Design §4.2 의사코드와 다름 (M-1과 연관) | Design 갱신 |
| L-2 | — | apply_trading_costs 정상 매칭 (L 없음) | — |
| L-3 | `tests/test_strategy_engine.py` | Design §8 명시한 `__import__`, `os.system` 테스트 케이스 누락 (동일 코드 경로는 `eval`로 커버됨) | 명시적 테스트 추가 |
| L-4 | `tests/test_strategy_engine.py` | `writable_tmp_dir` 미사용 (FS touch 없으므로 정당) | Design에 한 줄 주석 |
| L-5 | `api/schemas.py:305-317` | `BacktestSplitResponse`에 Design 외 필드(`warnings`, `iteration_id`, `attempt_no`, `persist`) 추가 — 긍정적 확장 | Design 추가 명시 |
| L-6 | `strategy_coach.py:77-84` + `design.md §4.2` | "5 scalar summary"라고 하지만 실제 6 (num_trades 포함). 구현은 6 scalar 사용 권장 | "6 scalar"로 갱신 |
| L-7 | `strategy_coach.py:116` | 프롬프트 user_payload에 `sort_keys=True` (Design은 캐시 키만 명시) | 결정성 개선, harmless |

---

## 5. Design 외 추가된 기능 (긍정적 확장)

| 추가 | 위치 | 평가 |
|---|---|---|
| `_serialise` / `_hydrate_cached` 캐시 round-trip | `strategy_coach.py:241-283` | Design 캐시 재사용을 깔끔히 구현 |
| `persist: bool = True` | `api/schemas.py:302` | 테스트에서 iteration_log 쓰기 비활성 가능 |
| `_persist_iteration` `CacheError` swallow | `api/strategy.py:67-107` | §6 fail-soft 정신 충실 |
| `BacktestSplitResponse.warnings` | `api/schemas.py` | §6.4 partial-success 정보 손실 방지 |
| `OptimizationGoal` Enum + `GoalLiteral` 동시 지원 | `core/types/schemas.py`, `api/schemas.py` | Pydantic Literal 호환 |

---

## 6. FR-01~15 한 줄 검증

| FR | 결과 |
|---|---|
| FR-01 StrategyDef DSL | ✅ `validate_expression`, `evaluate_rules` 동작 |
| FR-02 POST /api/strategy/backtest | ✅ IS+OOS 둘 다 |
| FR-03 70/30 split | ✅ `split_70_30` + indicators 사전 compute |
| FR-04 POST /api/ai/strategy-coach | ✅ Groq 호출 + JSON 파싱 |
| FR-05 추천 카드 + available | ✅ `CoachRecommendation.available` |
| FR-06 추천 적용 | ✅ `applyRecommendation` + `ROLE_COMBINATORS` |
| FR-07 parquet 영구 이력 | ✅ `iteration_log.append` |
| FR-08 이력 비교 표 | ✅ `HistoryTable` |
| FR-09 매 iteration 목표 선택 | ✅ `optimization_goal` 흐름 |
| FR-10 거래비용 분리 | ✅ `TradingCostsModel` 100/100/50 BPS 상한 |
| FR-11 5번째 탭 | ✅ `app.jsx:838-841` + 4분할 |
| FR-12 ⚠️ 빌트인 외 | ✅ `RecCard` unavailable 분기 + 가이드 |
| FR-13 /api/trend?series=true | ✅ `core_trend.classify_series` |
| FR-14 IS/OOS 시각화 | ✅ `SplitCard` 2개 + gap |
| FR-15 AI 응답 캐시 | ✅ `_cache_key` sha256 + sort_keys |

---

## 7. 결론 + 권장 진행

**`/pdca iterate` 건너뛰고 바로 `/pdca report` 권장.**

이유:
1. 97% ≥ 90% 임계값 초과
2. Critical/High gap 0건 — 사용자 영향 없음
3. Medium 2건은 모두 *"의도적 더 나은 구현"* — Design 문서 갱신이 정답 (코드 그대로 두기)
4. Low 7건은 housekeeping 수준

Design v0.3 권장 갱신사항을 Report에 명시하고, 실제 갱신은 archive 후 별도로:
- §3.2 `CoachRequest` → `StrategyCoachRequest` 명세 갱신 (M-1)
- §4.2 numexpr 우선 절 삭제 (M-2)
- §4.2/§4.5 "5 scalar" → "6 scalar" (L-6)
- `BacktestSplitResponse`에 `warnings/iteration_id/attempt_no/persist` 명시 (L-5)

이번 사이클은 **Design 단계 투자 효과를 명확히 보여줌**:
- v0.4.1: Design 첫 검증 78% → 95% 보강 → 구현 후 95% Match
- v0.5.0: Design 첫 검증 84% → 92% 보강 → 구현 후 **97% Match** (+2pt)

---

## Version History

| Version | Date | Author |
|---------|------|--------|
| 1.0 | 2026-04-30 | gap-detector 자동 분석 → 900033@interojo.com 검토 |
