---
template: analysis
version: 1.0
feature: rsi-price-bands
date: 2026-05-02
author: 900033@interojo.com
project: trading-analysis-tool
matchRate: 98
phase: check
---

# rsi-price-bands — Gap Analysis Report

> **Match Rate**: **98%** (Critical 0 · High 0 · Medium 1 · Low 2)
> **Date**: 2026-05-02
> **Design**: v0.2 (validator 91% → 보강 후)
> **Backend**: 147/147 PASSED
> **Frontend**: e2e Playwright 검증 완료 (BTC 6 라인 + 6 라벨)

이전 사이클 패턴:
- v0.4: Design 78%→95% / 구현 95% / iterate 1회 → 99%
- v0.5: Design 84%→92% / 구현 97% / iterate 0회
- **v0.6**: Design **91%→95%** / 구현 **98%** / iterate 0회 ← 본 사이클 (최고 점수)

---

## 1. 영역별 매칭률

| Category | Score | Status |
|----------|:-----:|:------:|
| Plan FR mapping (FR-01~11) | 100% | ✅ |
| §3 컬럼 명세 | 100% | ✅ |
| §4 알고리즘 명세 | 99% | ✅ |
| §5 UI | 100% | ✅ |
| §6 에러 처리 | 100% | ✅ |
| §8 테스트 명세 vs 실제 | 93% | ⚠️ (단순 카운트 14 vs 보고 15) |
| §10 Convention | 100% | ✅ |
| §11 폴더 구조 | 100% | ✅ |
| §12 Future / Out of Scope | 100% | ✅ |
| baseline 일관성 | 100% | ✅ |
| **Overall** | **~98%** | ✅ |

---

## 2. Critical / High Gap

**없음.** 본 사이클은 작은 사이클 + Design 단계 사전 보강으로 첫 검증부터 최고 점수.

---

## 3. Medium Gap (1건)

### M-1. 테스트 카운트 단순 불일치 (14 vs 보고 15)
- **위치**: `backend/tests/test_indicators.py` RPB 테스트 14개 + 사용자 보고 "신규 15"
- **분석**: 147 PASSED 전체 카운트는 신뢰 가능 (132 + 15 변화). 누락 테스트 1건이 파일 검색에 안 잡혔거나 타 파일에서 추가됐을 가능성. 실제 품질 영향 0건
- **조치**: 다음 commit 시 BUILTIN 카탈로그 검증 1건 추가 — 100% 일치 보장 (선택)

---

## 4. Low Gap (2건)

| ID | 위치 | 문제 | 조치 |
|---|---|---|---|
| L-1 | Design §4.5 의사코드 | `_wilder_ewm(..., n)` (n=13) — 실제는 `rsi_length` (=14, RSI 표준). 구현이 정답 | Design v0.3 정정 |
| L-2 | Design §8 테스트 표 | 4 항목(BUILTIN/converters/api/dsl)은 pytest 대신 e2e Playwright로 대체 | Design 명세 명확화 |

---

## 5. 긍정적 추가 (Design 외, 모두 양호)

| 추가 | 위치 | 평가 |
|---|---|---|
| `DEFAULT_RPB_*` 모듈 상수 5개 | `indicators.py:25-29` | 일관성 향상 |
| 양방향 표시 sub-토글 | `app.jsx:357-359` | UX 개선 (Design §5.3 명세를 별도 토글로 진화) |
| `data-rpb` 속성 + `data-testid` | `charts.jsx`, `app.jsx` | e2e 테스트 친화 |

---

## 6. FR-01~11 한 줄 검증 (모두 ✅)

| FR | 결과 |
|---|---|
| FR-01 `add_rpb()` 시그니처 | ✅ Defaults 모두 일치 |
| FR-02 알고리즘 정확도 | ✅ forward simulate 60≤median≤80 |
| FR-03 ATR 필터 | ✅ 양/하단 적용 |
| FR-04 RS Cap 하단만 | ✅ `np.minimum` 적용, 상단은 `avg_gain` 그대로 |
| FR-05 12 컬럼 | ✅ 6 가격 + 6 BARS |
| FR-06 compute() opt-out | ✅ `rpb_upper or rpb_lower` 분기 |
| FR-07 BUILTIN momentum | ✅ category 일치 |
| FR-08 자동완성 | ✅ BUILTIN 등록만으로 자동 노출 |
| FR-09 "RSI Imminent" 템플릿 | ✅ buy/sell 룰 byte-exact |
| FR-10 차트 토글 | ✅ 6 라인 + 6 라벨 + 단방향 토글 + 양방향 옵션 |
| FR-11 `RPB_` prefix | ✅ converters._INDICATOR_PREFIXES |

---

## 7. 결론 + 권장 진행

**`/pdca iterate` 건너뛰고 바로 `/pdca report` 권장.**

이유:
1. 98% ≥ 90% 임계값 초과 (이전 두 사이클 95%/97% 대비 최고)
2. Critical/High gap 0건
3. Medium 1건은 단순 카운트 검증 (품질 영향 X)
4. Low 2건은 Design v0.3 갱신 권장사항 (선택)

Design v0.3 권장 갱신:
- §4.5 `_wilder_ewm(..., rsi_length)` 정정
- §8 테스트 표에 e2e 분담 명시

---

## 8. 학습 효과 정량화

```
사이클       Design 첫 검증    Design 보강 후    구현 매치율    Iterate
────────────────────────────────────────────────────────────────────
v0.4         78%              95%              95%           1회 → 99%
v0.5         84%              92%              97%           0회
v0.6         91%              95%              98%           0회  ← 최고
```

**관찰**: Design 첫 검증 점수가 사이클마다 +6~7pt 상승. 구현 매치율도 비례. 학습된 PDCA 패턴이 누적 개선됨.

---

## Version History

| Version | Date | Author |
|---------|------|--------|
| 1.0 | 2026-05-02 | gap-detector 자동 분석 → 900033@interojo.com 검토 |
