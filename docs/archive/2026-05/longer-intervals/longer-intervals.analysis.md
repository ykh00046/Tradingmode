---
template: analysis
version: 1.0
feature: longer-intervals
date: 2026-05-06
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.8.0
---

# Gap Analysis — longer-intervals v0.8.0

> **Source**: gap-detector agent (Design v0.3 ↔ Implementation Phase A/B/C + Cleanup)
> **Match Rate**: **99%** (v1.1 post-cleanup) — Critical 0, High 0, Medium 0, Low 0 → `/pdca report` 진행 가능
> v1.0 baseline: 97% (Critical 0, High 0, Medium 1 (M-1), Low 4)

---

## 1. Match Rate Summary

| 항목 | 결과 |
|---|---|
| **Match Rate** | **97%** |
| Critical Gaps | 0 |
| High Gaps | 0 |
| Medium Gaps | 1 (M-1 T-B3 의도-구현 mismatch) |
| Low Gaps | 4 (L-1~L-4) |
| FR Coverage | 10/10 (100%, FR-09 env caveat) |
| T-NN Backend (T-B1~T-B4) | 4/4 PASSED + 기존 4 = 8/8 |
| T-NN Frontend (T-F1~T-F5) | 5/5 structural feasibility |
| Frontend v0.7 Code-paths | ✅ ws-right + CollapsibleSection + wl-favs + signals-limit (13 hits) + ★/☆ (4 hits) intact |
| Backend file isolation | ✅ data_loader.py UNCHANGED, lib/cache.py UNCHANGED (Design §3.6) |

---

## 2. Coverage Matrix

| FR | Design Spec | Implementation (file:line) | Match | Test |
|----|-------------|----------------------------|:-----:|:----:|
| FR-01 | Interval enum +W1/MN1 | `core/types/schemas.py:33-34` | ✅ | T-B4 (Interval.W1/MN1 round-trip) |
| FR-02 | IntervalLiteral +"1w","1M" | `api/schemas.py:36` | ✅ | indirect (FastAPI Query) |
| FR-03 | Binance _INTERVAL_MAP +2 | `core/adapters/binance_adapter.py:32-33` | ✅ | T-B4 PASSED |
| FR-04 | KRX resample(open=first/high=max/low=min/close=last/volume=sum) + dropna(close) | `core/adapters/krx_adapter.py:56-82` `_resample_ohlcv()` | ✅ | T-B1, T-B2 PASSED |
| FR-05 | INTERVAL_LABELS +'1w':'주','1M':'월' group:'longer' | `app.jsx:245-246` | ✅ | T-F1, T-F2, T-F4 |
| FR-06 | INTERVAL_GROUP_ORDER +'longer' + .tf-group--longer CSS | `app.jsx:248`, `styles.css:400` | ✅ | T-F4 |
| FR-07 | LOOKBACK_BY_INTERVAL +'1w':730, '1M':3650 | `loader.js:195-196` | ✅ | T-F1, T-F2 |
| FR-08 | KR insufficient data → DataSourceError | `krx_adapter.py:155-164` | ✅ | T-B3 PASSED (M-1 caveat) |
| FR-09 | 기존 + 신규 4 = 151 PASSED | env reality 8/8 in test_data_loader.py + 137 elsewhere PASSED, 10 pre-existing backtesting failures | ⚠️ Caveat | §4 |
| FR-10 | v0.7 UX 무영향 | grep ws-right/CollapsibleSection/wl-favs/signals-limit 13 hits, ★/☆ 4 hits, race-guard 263/291/295/301 intact | ✅ | manual |

### Design-specific (Plan 외)

| 항목 | 명세 | 구현 (file:line) | Match |
|---|---|---|:---:|
| §4.1 _resample_ohlcv signature + dropna(subset=['close']) | 정확 | `krx_adapter.py:56-82` | ✅ |
| §4.1 빈 DF guard | `if daily_df.empty: return daily_df` | `krx_adapter.py:70-71` | ✅ |
| §4.2 _INTERVAL_TO_FREQ / _SUPPORTED_INTERVALS / _RESAMPLE_BUFFER_DAYS | 모두 module-level 상수 | `krx_adapter.py:38-44` | ✅ |
| §4.2 buffer 70/350일 | `{"1w": 70, "1M": 350}` | `krx_adapter.py:44` | ✅ |
| §4.2 _ensure_supported_interval | 1d/1w/1M 허용 | `krx_adapter.py:47-53` | ✅ |
| §4.2 download() 분기 (1d → raw, 1w/1M → buffer fetch + resample) | 정확 | `krx_adapter.py:138-166` | ✅ |
| §4.2 buffer trim `resampled[resampled.index >= start]` | 정확 | `krx_adapter.py:166` | ✅ |
| §4.3 W-FRI (Korea Friday close) | 정확 | `krx_adapter.py:39` | ✅ |
| §4.4 ME (pandas 2.x) | 정확 | `krx_adapter.py:40` | ✅ |
| §3.6 data_loader.py / lib/cache.py 변경 0건 | 양쪽 UNCHANGED | — | ✅ |
| §6.2 intervalReqRef line citation 260/288/292/298 | 실제 263/291/295/301 (+3 drift) | `app.jsx` | ⚠️ L-1 |
| §10.1 Phase A 안정성 | 기존 4 무영향 | `test_data_loader.py:40-100` | ✅ |
| §10.2 Phase B 4 신규 + 기존 4 = 8/8 | 8 PASSED | `test_data_loader.py:104-210` | ✅ |
| Phase C cache bust v11 → v12 | 7 assets 모두 v12 | `index.html` | ✅ |

---

## 3. Gaps

### Critical: 0
### High: 0
### Medium: 1

- **M-1** — **T-B3 (insufficient data) 테스트가 의도와 다른 경로로 검증됨**. Design §7 시나리오는 "신규상장 종목 일봉 < 7일 → 주봉 0개" 인데 실제 테스트(`test_data_loader.py:173-185`)는 `daily["close"] = float("nan")` 강제. 즉 진짜 신규상장 (3 daily rows) 상황에서는 W-FRI resample 이 1주 partial bucket 1행을 만들고 `dropna(close)` 통과 → `DataSourceError` 미발생. **production 신규상장 3일치 → 1행 partial bucket 반환** 으로 사용자에게 misleading 데이터. v0.9 에 minimum-bars guard 추가 권장 (weekly ≥5 daily, monthly ≥15 daily).

### Low: 4

- **L-1** — Design §6.2 race-guard citation `260/288/292/298` → 실제 `263/291/295/301` (+3 line drift, INTERVAL_LABELS 주석 추가로 발생). Design 갱신만, 기능 영향 0.
- **L-2** — Plan §3.1 FR-08 의 한국어 메시지 의도 vs 실제 영어 메시지 (`"insufficient daily data..."`). Frontend `app.jsx:303` 이 raw `e.message` 노출. v0.9 에 한국어 매핑 layer 검토.
- **L-3** — Plan FR-01 `M1_LONG` 제안 → Design `MN1` 정정 → 구현 `MN1`. 개선 (M1 분봉과 명확 구분). Plan 갱신 불필요.
- **L-4** — Design §3.4 case-sensitive 검증이 인라인 주석 뿐, 형식적 unit test 또는 runtime assert 없음. JS 자체 case-sensitive 라 자연 보장. v0.9 e2e 검증 추가 검토.

---

## 4. Backend Test Caveat (FR-09)

- 사용자 보고: `pytest tests/test_data_loader.py` → **8/8 PASSED** (기존 4 + 신규 4).
- Design §8.2 의 "147 + 4 = 151 PASSED" 예측은 환경에서 **8/8 in test_data_loader + 137 elsewhere = 145 PASSED, 10 pre-existing failures**.
- 10 failures = `ModuleNotFoundError: No module named 'backtesting'` (v0.4/v0.5 strategy/backtest 테스트, env 의존). **v0.8 longer-intervals 와 무관**.
- 영향: **v0.8 도입 회귀 0**. FR-09 본질("기존 무영향 + 신규 4 추가") 충족. 절대 숫자 환경 의존이므로 Design §8.2 / Plan §3.1 FR-09 갱신 권장 — `"기존 PASSED 보존 + 신규 T-B1~T-B4 4건 PASSED"` 로 환경 무관하게.

---

## 5. Implementation Quality Notes

### 잘한 점 (7)

1. **Design §3.6 약속 정확 이행** — `core/data_loader.py` (61줄) + `lib/cache.py` (137줄) 양쪽 변경 0. 신규 1w/1M 인터벌이 cache path `{interval}` 슬롯에 자동 분리.
2. **Buffer trim 정확성** — `resampled[resampled.index >= start]` (`krx_adapter.py:166`) 로 daily-buffer 기간 W-FRI/ME 행 정확히 제거. timezone 일관성 보존.
3. **에러 분기 깔끔** — `_ensure_supported_interval` 가 진입점에서 unsupported intraday(1m/5m/15m/1h/4h)를 즉시 거절. 의도하지 않은 인터벌 0% 통과.
4. **Test parametrization** — T-B4 가 단일 loop 로 W1/MN1 모두 검증, `bin_dl.call_count == 2` + `called_intervals` 검사로 enum value pass-through 확인.
5. **Pandas 2.x compliance** — `'ME'` 사용 (deprecated `'M'` 회피), `dropna(subset=['close'])` 명시 column.
6. **Frontend v0.7 회귀 0** — `ws-right`/`CollapsibleSection`/`wl-favs`/`signals-limit`/★ 17 hits 모두 intact. race-guard 도 신규 1w/1M 클릭에 그대로 적용.
7. **Cache bust 일관성** — `index.html` 7 asset 모두 v12 동시 갱신.

### 개선 여지 (4, 모두 Low)

- **C-1** — `_RESAMPLE_BUFFER_DAYS` 70/350 magic number — module 상수에 산정근거 docstring 추가 권장.
- **C-2** — `download()` 56줄 → `_fetch_daily_with_fallback()` 헬퍼 추출 가능. v0.9 cleanup 후보.
- **C-3** — T-B1 의 `len(result) >= 2` 가 정확 count 미검증. `>= 11, <= 13` 같은 범위 검사 권장.
- **C-4** — `krx_adapter.py:130` 에 `# Note: daily fetch is NOT cached separately — only the resampled output is.` 1줄 inline comment 추가 권장 (Design §3.6 caveat 코드 옆 표기).

---

## 6. v0.4–v0.7 사이클 트렌드 비교

| Cycle | Design 1차 | Design 보강 후 | 구현 매치율 | Iterate |
|---|---:|---:|---:|:---:|
| v0.4.1 trading-analysis-tool | 78% | 95% | 95% | 1회 → 99% |
| v0.5.0 ai-strategy-coach | 84% | 92% | 97% | 0회 |
| v0.6.0 rsi-price-bands | 91% | 95% | 98% | 0회 |
| v0.7.0 ux-improvements | 78% | 96% | 96% | 0회 |
| **v0.8.0 longer-intervals** | **92%** | **96%** | **97%** | **0회** |

**관찰**:
- v0.8 첫 검증 92% — v0.7 78% 대비 +14pt 회복. **사전 grep 그라운딩 효과 입증** (process lesson #1 from v0.7 stuck).
- 보강 폭 (+4pt) 이 가장 작아 Design 의 "사실관계 정확도" 향상 누적.
- 구현 매치율 97% — v0.5 와 동급, v0.6 (98%) 다음 가는 quality.
- Critical/High 0건 5 사이클 연속.

---

## 7. Recommendation

✅ **Match Rate 97% ≥ 90% → `/pdca report longer-intervals` 진행 (iterate 단계 생략).**

선택적 cleanup (15분, v0.9 로 미뤄도 무방):
- **M-1 (가장 중요)**: T-B3 의 NaN-injection 패턴 대신 진짜 minimum-bars guard 를 `_resample_ohlcv` 또는 `download()` 에 추가, T-B3 도 그 guard 검증. **production safety 영향 가장 큼**.
- **L-1**: Design §6.2 line citation `260/288/292/298` → `263/291/295/301`.
- **L-2**: 에러 메시지 한국어화 매핑 (`app.jsx:303`).
- **L-4**: Quality Criteria §4.2 case-sensitive 검증 형식화.
- **C-3**: T-B1 정확 count 검증 강화.
- Design §8.2 / Plan §3.1 FR-09 에 backtesting-module env caveat 추가.

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 1.0 | 2026-05-06 | gap-detector 분석. 97% 매치. FR 10/10 (FR-09 env caveat), T-B1~T-B4 4/4 PASSED, T-F1~T-F5 structural feasibility 100%. Critical/High 0건. M-1 (T-B3 의도-구현 mismatch) + L-1~L-4. v0.6 trend (98%) 근접. | 900033@interojo.com |
| 1.1 | 2026-05-06 | Cleanup 적용 후 재산정 — **99% 매치**. M-1 해소 (krx_adapter `_MIN_DAILY_FOR_INTERVAL` minimum-bars guard, T-B3 진짜 검증, T-B3b 분리). L-1 해소 (Design line citation 갱신). L-2 해소 (frontend `localizeIntervalError` 한국어 매핑 헬퍼). L-4 해소 (`_assertIntervalKeysDistinct` IIFE 런타임 검증). C-3 해소 (T-B1/T-B2 정확 count). Plan FR-09 + Design §8.2 backtesting env caveat 명시. 9/9 pytest PASSED. v0.6 (98%) 추월. | 900033@interojo.com |
