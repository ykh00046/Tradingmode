---
template: design
version: 1.2
feature: ai-strategy-coach
date: 2026-04-30
author: 900033@interojo.com
project: trading-analysis-tool
project_version: 0.5.0
---

# ai-strategy-coach Design Document

> **Summary**: 사용자 정의 매매 전략을 70/30 split 으로 백테스트하고, In-sample 결과를 Groq llama-3.3-70b 에 전달하여 보완 지표를 추천 받는 반복 협업 루프. Iteration 이력 parquet 영구 저장.
>
> **Project**: trading-analysis-tool
> **Version**: 0.5.0
> **Author**: 900033@interojo.com
> **Date**: 2026-04-30
> **Status**: Draft
> **Planning Doc**: [ai-strategy-coach.plan.md](../../01-plan/features/ai-strategy-coach.plan.md)

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | Schema | 본 문서 §3 + core/types/schemas.py 확장 |
| Phase 2 | Convention | v0.4.1 컨벤션 그대로 + 본 문서 §10 보강 |
| Phase 4 | API Spec | 본 문서 §4.5 신규 엔드포인트 3건 |
| Phase 5 | Design System | Tradingmode 다크 테마 그대로 |
| Phase 6 | UI Integration | 5번째 탭 strategy-coach-page.jsx |

---

## 1. Overview

### 1.1 Design Goals

- **순수 함수성**: StrategyEngine 의 룰 평가 결과는 (지표 DataFrame, 룰) → entry/exit boolean Series 로 결정론적
- **안전한 expression**: 사용자 룰은 `pandas.eval` 안전 모드 + 화이트리스트 토큰만, 임의 코드 실행 X
- **In-sample / Out-of-sample 분리**: 70/30 시간순 split, AI 는 IS 만 보고 추천. OOS 는 검증 전용
- **AI 보조성**: 백테스트 stats + 약점 제시 → 추천 *가설* 일 뿐. 사용자 승인 필수
- **이력 영구성**: 시도 누적, 사용자가 시간 지나도 어떤 조합이 효과적이었는지 비교 가능
- **점진적 확장**: 빌트인 지표 외 추천이 나오면 Claude 가 코드로 추가 → 다음 시도에 자동 사용 가능

### 1.2 Design Principles

- **Domain logic 백엔드 집중**: 룰 평가/split/지표 계산 모두 백엔드. 프론트는 시각화 + 입력
- **Fail Loud (사용자 룰)**: 잘못된 expression(미정의 컬럼, 금지 토큰)은 명시적 422 에러
- **Fail Soft (AI)**: AI 호출 실패 시 백테스트 결과는 그대로 반환, 코치 응답만 비활성
- **재현성**: (전략 정의 + OHLCV + 거래비용) → 동일 백테스트 결과
- **타입힌트 + Pydantic**: 사용자 입력 스키마는 Pydantic 으로 강제

---

## 2. Architecture

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Tradingmode/) — 5th Tab "Strategy Coach"              │
│  strategy-coach-page.jsx                                         │
│  ├─ EditorPanel (좌측: 룰 빌더 + 거래비용 + 최적화 목표)          │
│  ├─ ResultPanel (중앙: IS/OOS equity curve, stats 비교)          │
│  ├─ CoachPanel  (우측: AI 진단 + 추천 카드 3개 + ⚠️ 미존재 표시)  │
│  └─ HistoryTable (하단: iteration 이력 표 + 시도 클릭 → 복원)     │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Backend API                                                     │
│  POST /api/strategy/backtest   → run engine + 70/30 split        │
│  POST /api/ai/strategy-coach   → Groq 호출 + 추천 파싱           │
│  GET  /api/trend?series=true   → per-bar TrendState 시계열       │
│  GET  /api/strategy/builtins   → 빌트인 지표/연산자 목록 (UI 자동) │
└──────────────────────────────┬───────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────────┐
       ▼                       ▼                           ▼
┌─────────────────┐   ┌──────────────────┐    ┌─────────────────────┐
│ strategy_engine │   │ strategy_coach   │    │ iteration_log       │
│  - eval rules   │   │  - prompt build  │    │  - parquet append   │
│  - 70/30 split  │   │  - parse JSON    │    │  - read history     │
│  - apply costs  │   │  - cache key     │    └─────────────────────┘
└─────────┬───────┘   └────────┬─────────┘                  ▲
          │ uses               │ uses                       │
          ▼                    ▼                            │
   indicators.compute     ai_interpreter._client            │
   (pure pandas)          (existing Groq adapter)           │
                                                            │
                          backtest.run ────────────────────┘
                          (existing wrapper)
```

### 2.2 Data Flow

```
[사용자: 전략 정의 + 거래비용 + 최적화 목표 + symbol/range]
       │
       ▼
POST /api/strategy/backtest
       │
       ├→ data_loader.fetch(symbol, range) → df, cache_hit
       ├→ indicators.compute(df) → df with SMA/RSI/MACD/BB/ADX
       ├→ strategy_engine.split(df, ratio=0.7) → df_is, df_oos
       ├→ strategy_engine.run(df_is, strategy, costs) → BacktestResult (IS)
       └→ strategy_engine.run(df_oos, strategy, costs) → BacktestResult (OOS)
       │
       ▼
StrategyBacktestResponse {is, oos, gap_pct, warnings[]}
       │
       ▼
POST /api/ai/strategy-coach
       │
       ├→ build prompt(전략, IS stats, 목표, 시장 컨텍스트, builtin 목록)
       ├→ Groq client.chat.completions.create(json_object)
       ├→ parse → CoachResponse (diagnosis, recommendations[], warnings[])
       └→ for each rec: builtin? else available=false (⚠️ 카드)
       │
       ▼
[사용자: 추천 카드 클릭 → 룰에 자동 추가 → /api/strategy/backtest 재호출]
       │
       ▼
iteration_log.append(symbol, attempt_no, strategy, result, recommendation, applied)
       │
       ▼
HistoryTable 업데이트 (세션 + parquet)
```

### 2.3 Dependencies

**신규 모듈**

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| `core.strategy_engine` | core.indicators, core.types.schemas, pandas.eval | 룰 평가 + 70/30 split + 거래비용 적용 |
| `core.strategy_coach` | core.ai_interpreter (`_client`), groq | LLM 프롬프트 빌드 + 응답 파싱 + 캐시 |
| `core.iteration_log` | pyarrow, pathlib | parquet append/read |
| `api.strategy` | core.strategy_engine, lib.cache | POST /api/strategy/backtest |
| `api.ai (확장)` | core.strategy_coach | POST /api/ai/strategy-coach |
| `api.trend (확장)` | core.trend.classify_series | GET /api/trend?series=true |

**기존 재사용**: `core.indicators` (compute), `core.data_loader` (fetch), `core.ai_interpreter._client` (Groq SDK), `lib.cache` (parquet 헬퍼).

---

## 3. Data Model

### 3.1 신규 Domain Schemas (core/types/schemas.py 확장)

```python
# === 사용자 전략 정의 ===

class OptimizationGoal(str, Enum):
    RETURN = "return"        # 누적 수익률
    SHARPE = "sharpe"        # 샤프 지수
    MDD = "mdd"              # 최대낙폭 최소화
    WIN_RATE = "win_rate"    # 승률


@dataclass(frozen=True)
class TradingCosts:
    commission_bps: float = 5.0      # 0.05% 기본 (왕복)
    slippage_bps: float = 2.0        # 0.02% 기본
    kr_sell_tax_bps: float = 18.0    # 한국 주식 매도세 0.18%
    apply_kr_tax: bool = True        # KR 종목 자동 적용 토글


@dataclass(frozen=True)
class StrategyDef:
    """사용자가 정의한 매매 전략.

    expression 은 pandas.eval 안전 모드로 평가. 인덱스 정렬된 boolean Series 결과.
    토큰 화이트리스트: 빌트인 지표 컬럼명 + 산술/비교/논리/시프트(prev N).
    """
    name: str                                    # 사용자 부여 이름
    buy_when: str                                # 매수 조건 expr — 예: "RSI_14 < 30 and ADX_14 > 25"
    sell_when: str                               # 매도 조건 expr
    holding_max_bars: int | None = None          # 강제 청산 (선택, None = 무제한)
    indicator_config: IndicatorConfig | None = None
    costs: TradingCosts = field(default_factory=TradingCosts)
    optimization_goal: OptimizationGoal = OptimizationGoal.SHARPE


# === 백테스트 결과 (split) ===

@dataclass(frozen=True)
class BacktestSplitResult:
    """In-sample + Out-of-sample 결과 묶음."""
    is_result: BacktestResult
    oos_result: BacktestResult
    is_period: tuple[pd.Timestamp, pd.Timestamp]
    oos_period: tuple[pd.Timestamp, pd.Timestamp]
    is_oos_gap_pct: float                        # IS-OOS 수익률 차 (%) — 과적합 지표
    overfit_warning: bool                        # gap > 30% 경고 자동
    costs_applied: TradingCosts


# === AI 코치 ===

@dataclass(frozen=True)
class CoachRecommendation:
    indicator: str                               # 예: "ATR_14", "STOCH" — builtin 명 또는 자유 명
    params: dict                                 # 예: {"length": 14}
    role: Literal["filter", "exit_rule", "entry_filter", "sizing"]
    reason: str                                  # 한국어 1-2문장
    expected_synergy: str                        # "MDD 줄임" / "트렌드 강화" 등
    available: bool                              # 빌트인에 이미 있나?
    sample_rule: str | None = None               # 추천 적용 시 추가될 룰 expr (예: "ATR_14 < 0.05*close")


@dataclass(frozen=True)
class CoachResponse:
    diagnosis: str                               # 약점 진단 (1-2문장)
    recommendations: list[CoachRecommendation]   # 보통 3개
    warnings: list[str]                          # AI 우려점 (과적합/시장변화 등)
    model: str                                   # "llama-3.3-70b-versatile"
    generated_at: pd.Timestamp
    disclaimer: str = "본 추천은 LLM 패턴 매칭 결과로 시장 통찰이 아닙니다."


# === Iteration 이력 ===

# === 빌트인 지표 메타데이터 ===

@dataclass(frozen=True)
class BuiltinIndicator:
    """UI 자동완성 + AI 코치 빌트인 풀에 노출되는 지표 메타데이터."""
    name: str                                    # 사람용 이름 (예: "RSI")
    columns: list[str]                           # df 에 등장하는 컬럼명 (예: ["RSI_14"])
    params: dict                                 # 기본 파라미터 (예: {"period": 14})
    description: str                             # 한국어 1줄 설명
    category: Literal["momentum", "trend", "volatility", "volume"]


# === Iteration 이력 ===

@dataclass(frozen=True)
class IterationEntry:
    """단일 백테스트 시도 (parquet 한 행에 대응)."""
    iteration_id: str                            # uuid4().hex (32자 full) — collision 방어
    symbol: str
    interval: str
    attempt_no: int                              # 세션 내 번호
    strategy_def_json: str                       # StrategyDef 직렬화
    is_total_return: float
    oos_total_return: float
    is_sharpe: float
    oos_sharpe: float
    is_mdd: float
    oos_mdd: float
    is_win_rate: float
    is_oos_gap_pct: float
    overfit_warning: bool
    optimization_goal: str
    coach_diagnosis: str | None
    applied_recommendation: str | None           # 직전 시도에서 적용한 추천 indicator 명
    timestamp: pd.Timestamp                      # 시도 실행 시점 (UTC)
```

### 3.2 Pydantic Equivalents (api/schemas.py 확장)

```python
# 신규 모델은 모두 BaseModel — JSON-friendly 형식

class TradingCostsModel(BaseModel):
    """현실적 BPS 상한: commission/slippage 1%, KR 매도세 0.5%."""
    commission_bps: float = Field(default=5.0, ge=0, le=100)     # 0~1%
    slippage_bps: float = Field(default=2.0, ge=0, le=100)       # 0~1%
    kr_sell_tax_bps: float = Field(default=18.0, ge=0, le=50)    # 0~0.5%
    apply_kr_tax: bool = True


class StrategyDefModel(BaseModel):
    """사용자 룰 표현식 길이는 MAX_STRATEGY_RULES env 로 추가 제한 (and/or 토큰 수)."""
    name: str = Field(min_length=1, max_length=80)
    buy_when: str = Field(min_length=1, max_length=500)
    sell_when: str = Field(min_length=1, max_length=500)
    holding_max_bars: int | None = Field(default=None, gt=0)
    costs: TradingCostsModel = Field(default_factory=TradingCostsModel)
    optimization_goal: Literal["return", "sharpe", "mdd", "win_rate"] = "sharpe"


class StrategyBacktestRequest(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral = "1d"
    start: int                                    # unix ms
    end: int
    split_ratio: float = Field(default=0.7, gt=0.5, lt=0.95)
    cash: float = Field(default=10_000_000, gt=0)
    strategy: StrategyDefModel


class BacktestSplitResponse(BaseModel):
    is_result: BacktestResultResponse
    oos_result: BacktestResultResponse
    is_period_start: int                          # unix ms
    is_period_end: int
    oos_period_start: int
    oos_period_end: int
    is_oos_gap_pct: float
    overfit_warning: bool
    costs_applied: TradingCostsModel


class CoachRequest(BaseModel):
    strategy: StrategyDefModel
    market: MarketLiteral
    symbol: str
    is_result: BacktestResultResponse              # IS 결과만 전달 (OOS 는 AI 에 X)
    builtin_indicators: list[str]                  # UI 가 GET /api/strategy/builtins 결과 그대로 전달
    history_summary: list[dict] | None = None      # 직전 시도들 요약 (선택)


class CoachRecommendationModel(BaseModel):
    indicator: str
    params: dict = Field(default_factory=dict)
    role: Literal["filter", "exit_rule", "entry_filter", "sizing"]
    reason: str
    expected_synergy: str
    available: bool
    sample_rule: str | None = None


class CoachResponseModel(BaseModel):
    diagnosis: str
    recommendations: list[CoachRecommendationModel]
    warnings: list[str] = Field(default_factory=list)
    model: str
    generated_at: int
    disclaimer: str


class TrendSeriesPoint(BaseModel):
    t: int                                         # unix ms
    state: Literal["uptrend", "downtrend", "sideways"]


class TrendResponseExt(TrendResponse):
    """기존 TrendResponse + series=true 일 때 series 필드 추가."""
    series: list[TrendSeriesPoint] | None = None


class BuiltinIndicatorModel(BaseModel):
    name: str
    columns: list[str]
    params: dict = Field(default_factory=dict)
    description: str
    category: Literal["momentum", "trend", "volatility", "volume"]


class StrategyBuiltinsResponse(BaseModel):
    """GET /api/strategy/builtins 응답."""
    indicators: list[BuiltinIndicatorModel]
    operators: list[str]                            # ["+", "-", "*", "/", "<", "<=", ...]
    helpers: list[str]                              # ["abs", "min", "max", "mean", "prev"]


class IterationEntryModel(BaseModel):
    """GET /api/strategy/iterations 응답의 한 행. timestamp 만 unix ms."""
    iteration_id: str
    symbol: str
    interval: str
    attempt_no: int
    strategy_def_json: str
    is_total_return: float
    oos_total_return: float | None                 # OOS 부족 시 None
    is_sharpe: float
    oos_sharpe: float | None
    is_mdd: float
    oos_mdd: float | None
    is_win_rate: float
    is_oos_gap_pct: float | None
    overfit_warning: bool
    optimization_goal: str
    coach_diagnosis: str | None
    applied_recommendation: str | None
    timestamp: int                                  # unix ms
```

### 3.3 parquet 이력 스키마

```
data/_iterations/{symbol_safe}_{interval}.parquet
   columns: iteration_id, symbol, interval, attempt_no,
            strategy_def_json, is_total_return, oos_total_return,
            is_sharpe, oos_sharpe, is_mdd, oos_mdd, is_win_rate,
            is_oos_gap_pct, overfit_warning,
            optimization_goal, coach_diagnosis,
            applied_recommendation, timestamp
   index:   timestamp (정렬 보장)
   append:  매 백테스트마다 1 행 추가 (중복 unique key = iteration_id)
```

`symbol_safe` = symbol 의 `/` `:` 등 파일명 위험 문자를 `_` 로 치환.

---

## 4. API Specification

### 4.1 Internal Module API (Python)

| Module | Function | Purpose |
|--------|----------|---------|
| `core.strategy_engine` | `evaluate_rules(df, buy_when, sell_when) -> tuple[Series, Series]` | 안전 expression → boolean entry/exit |
| `core.strategy_engine` | `split_70_30(df, ratio=0.7) -> tuple[df_is, df_oos]` | 시간순 split |
| `core.strategy_engine` | `run_with_strategy_def(df, strategy_def, cash) -> BacktestResult` | 기존 backtest.run 재사용 + custom strategy class 동적 생성 |
| `core.strategy_engine` | `run_split(df, strategy_def, cash, ratio=0.7) -> BacktestSplitResult` | 위 2개를 묶어 IS/OOS 둘 다 |
| `core.strategy_engine` | `apply_trading_costs(commission_bps, slippage_bps, kr_sell_tax_bps, market, apply_kr_tax) -> float` | backtesting.py commission 단일 값으로 환산 |
| `core.strategy_engine` | `WHITELISTED_TOKENS: frozenset[str]` | 안전 expression 화이트리스트 |
| `core.strategy_engine` | `validate_expression(expr, allowed_columns) -> None` | AST 파싱으로 미허용 토큰 거부 |
| `core.strategy_engine` | `BUILTIN_INDICATORS: list[dict]` | UI 에 노출되는 빌트인 지표 메타데이터 (이름, 컬럼, 설명) |
| `core.strategy_coach` | `build_prompt(strategy, is_result, goal, builtins, history) -> str` | 프롬프트 빌드 |
| `core.strategy_coach` | `parse_response(content) -> CoachResponse` | JSON 검증 + CoachRecommendation.available 판정 |
| `core.strategy_coach` | `recommend(req, model) -> CoachResponse` | _client + create + cache 통합 |
| `core.iteration_log` | `append(entry: IterationEntry) -> None` | parquet 행 append |
| `core.iteration_log` | `read(symbol, interval, limit=50) -> list[IterationEntry]` | 최근 N 시도 |
| `core.iteration_log` | `compare(iteration_ids: list[str]) -> pd.DataFrame` | 시도 비교 표 |

### 4.2 핵심 함수 시그니처 상세

#### `core.strategy_engine.evaluate_rules`

```python
import ast
import pandas as pd

# 허용 함수 (Call 노드의 함수명)
ALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    "abs", "min", "max", "mean", "prev",   # prev(col, n) = col.shift(n)
})

# 허용 boolean 상수
ALLOWED_CONSTANTS: frozenset[str] = frozenset({"True", "False"})

# 허용 AST 노드 타입 (이 외에는 모두 거부)
ALLOWED_NODE_TYPES: tuple = (
    ast.Expression, ast.Name, ast.Constant, ast.Load,
    ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Call,
)

# 명시적 거부 노드 (가독성용 — ALLOWED_NODE_TYPES 외이면 자동 거부)
FORBIDDEN_NODE_TYPES: tuple = (
    ast.Attribute, ast.Subscript, ast.Lambda, ast.ListComp, ast.SetComp,
    ast.DictComp, ast.GeneratorExp, ast.IfExp, ast.Starred,
    ast.JoinedStr, ast.FormattedValue, ast.Yield, ast.YieldFrom, ast.Await,
    ast.NamedExpr,                              # walrus :=
    ast.Import, ast.ImportFrom,
)


def validate_expression(expr: str, allowed_columns: set[str]) -> None:
    """
    AST 파싱하여 다음만 허용:
    - 노드 타입: ALLOWED_NODE_TYPES (외에는 InvalidStrategyError)
    - Name: allowed_columns ∪ ALLOWED_FUNCTIONS ∪ ALLOWED_CONSTANTS
    - Call.func: ALLOWED_FUNCTIONS 의 식별자 (Name 노드)
    - Constant: int, float, bool 만 (str 거부)
    위반 시 InvalidStrategyError(message, details={'token': ..., 'reason': ...}).

    추가 검증:
    - and/or 토큰 수 합산 ≤ MAX_STRATEGY_RULES (env, 기본 10)
    """


def evaluate_rules(
    df: pd.DataFrame,
    buy_when: str,
    sell_when: str,
) -> tuple[pd.Series, pd.Series]:
    """
    df 의 indicator 컬럼 + ALLOWED_FUNCTIONS 사용 가능.

    실행 정책:
      1. validate_expression(buy_when, set(df.columns)) — AST 화이트리스트 통과
      2. local_dict = {col: df[col] for col in df.columns} ∪ helper functions
      3. **engine='numexpr' 우선**, NumExpr 미지원 노드(Call) 만 'python' fallback
      4. pandas.eval(buy_when, parser='pandas', engine=..., local_dict=local_dict)
      5. 결과를 bool Series 로 강제 캐스팅, 인덱스는 df 와 동일

    반환: (entry: bool Series, exit: bool Series).
    """
```

#### `core.strategy_engine.split_70_30`

```python
def split_70_30(df: pd.DataFrame, ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """시간순 split. df.iloc[:n], df.iloc[n:].

    **중요 — indicator 계산 순서**:
      1. `data_loader.fetch(req)` 로 전체 OHLCV 확보
      2. `indicators.compute(df)` 로 *전체* df 에 지표 계산 (split 이전!)
      3. 그 다음 `split_70_30(df_with_indicators)` 호출
      4. OOS 첫 봉의 SMA_120/MACD 등은 IS 마지막 120봉을 사용 → 자동 valid

    OOS 봉 부족 (< 30) 시 호출자가 graceful 처리: IS 결과만 반환, OOS=None.
    """
```

#### `core.strategy_engine.apply_trading_costs`

```python
def apply_trading_costs(costs: TradingCosts, market: Market) -> float:
    """backtesting.py 는 단일 commission 만 받음.
    왕복 BPS 합산 → 분수로 환산:
        total_bps = commission + slippage*2  (slippage는 진입+청산 모두)
        if market == KR_STOCK and costs.apply_kr_tax: total_bps += kr_sell_tax  (매도 시 1회)
    return total_bps / 10000
    """
```

> §4.1 표의 시그니처도 본 함수 정의와 동일: `apply_trading_costs(costs, market) -> float`.

#### `core.strategy_coach.recommend`

```python
def recommend(req: CoachRequest, model: str | None = None) -> CoachResponse:
    """
    사용 모델은 인자 > env > 디폴트 순:
        model = model or os.environ.get("STRATEGY_COACH_MODEL", "llama-3.3-70b-versatile")

    캐시 키 (sha256):
        payload = json.dumps({
            "strategy": req.strategy.model_dump(),
            "is_summary": {                          # equity_curve / trades 제외
                "total_return": req.is_result.total_return,
                "annual_return": req.is_result.annual_return,
                "max_drawdown": req.is_result.max_drawdown,
                "win_rate": req.is_result.win_rate,
                "sharpe_ratio": req.is_result.sharpe_ratio,
                "num_trades": req.is_result.num_trades,
            },
            "goal": req.strategy.optimization_goal,
            "model": model,
        }, sort_keys=True)                          # ← 결정성 보장
        cache_key = hashlib.sha256(payload.encode()).hexdigest()[:16]

    동일 키 재호출 시 LLM 호출 0회. collision 시 마지막 쓰기 우선.
    """
```


#### `core.strategy_coach.build_prompt`

시스템 프롬프트 (한국어, 구조화):

```
당신은 정량 트레이딩 전략 컨설턴트입니다.
사용자가 정의한 전략의 In-sample 백테스트 결과를 보고:
1. 약점을 1~2문장으로 진단
2. 보완할 지표 3개를 추천 (역할 명시: filter / exit_rule / entry_filter / sizing)
3. 우려점 1~2개

규칙:
- 사용자가 제공하는 builtin_indicators 외 지표를 추천해도 좋습니다 (자유)
  단, builtin 에 없는 것을 추천한 경우 사용자에게 추가 구현이 필요합니다
- 추측·예측·"수익 보장" 표현 금지
- 각 추천에는 sample_rule (실제 적용할 expr 문자열) 가급적 포함
- 응답은 JSON 한 객체. 다른 텍스트 없음
- JSON 스키마:
  {
    "diagnosis": str,
    "recommendations": [
      {"indicator": str, "params": dict, "role": str,
       "reason": str, "expected_synergy": str, "sample_rule": str|null}
    ],
    "warnings": [str]
  }
```

User 프롬프트는 구조화 JSON 으로 strategy 정의 + IS 결과 + 목표 + 빌트인 목록 + 직전 시도들의 stats 요약 전달.

**Prompt injection 방어** — 사용자 expression 은 *문자열 값* 으로만 JSON 에 삽입, 시스템 프롬프트 내에 변수 치환(`{{user_rule}}`) 절대 X:

```python
user_message = json.dumps({
    "strategy": req.strategy.model_dump(),         # buy_when/sell_when 모두 string value
    "is_result_summary": {...},                     # 위 캐시 키와 동일 5스칼라
    "goal": req.strategy.optimization_goal,
    "builtin_indicators": [b.name for b in req.builtin_indicators],
    "history_summary": req.history_summary or [],
}, ensure_ascii=False)
# ↑ 사용자가 buy_when 에 "Ignore previous instructions ..." 를 넣어도
#   LLM 은 JSON value 로만 받음. system prompt 의 명령은 그대로 유지.
```

#### `core.iteration_log.append`

```python
def append(entry: IterationEntry, base_dir: Path | None = None) -> Path:
    """매 백테스트 후 호출. base_dir 기본 = ITERATION_LOG_DIR env (./data/_iterations).

    동작:
    1. {symbol_safe}_{interval}.parquet 경로 결정 (path traversal 방지)
    2. 기존 파일 있으면 read → append, 없으면 신규
    3. timestamp 인덱스 정렬 후 저장 (덮어쓰기)

    실패 시 CacheError. 호출자(api.strategy)는 graceful 처리 — 백테스트 결과는 그대로 반환.
    """
```

### 4.3 신규 REST 엔드포인트

| Method | Path | 입력 | 출력 | 비고 |
|--------|------|------|------|------|
| POST | `/api/strategy/backtest` | `StrategyBacktestRequest` | `BacktestSplitResponse` | 70/30 split, IS+OOS 둘 다 |
| POST | `/api/ai/strategy-coach` | `CoachRequest` | `CoachResponseModel` | Groq 호출 + 캐시 |
| GET | `/api/strategy/builtins` | (없음) | `{indicators: list[BuiltinIndicator], operators: list[str], helpers: list[str]}` | UI 자동완성 |
| GET | `/api/trend?series=true` | 기존 + `series` 쿼리 | `TrendResponseExt` | 백로그 M-3 흡수 |
| GET | `/api/strategy/iterations` | `?symbol=&interval=&limit=50` | `list[IterationEntryModel]` | 이력 조회 |

### 4.4 에러 매핑 (기존 표 확장)

| HTTP | code | 신규 도메인 예외 | 발생 시점 |
|------|------|------------------|----------|
| 400 | `INVALID_INPUT` | `InvalidStrategyError` | expression 파싱 실패, 미허용 토큰 |
| 422 | `INSUFFICIENT_DATA` | `InsufficientDataError` | OOS 봉 수 < 30 (split 의미 없음) |
| 503 | `AI_SERVICE_ERROR` | `AIServiceError` | Groq 응답 JSON 파싱 실패 등 |

신규 예외 추가:
```python
# core/types/errors.py 에 추가
class InvalidStrategyError(TradingToolError):
    """사용자 전략 expression 검증 실패."""
```

### 4.5 캐싱 정책

| 데이터 | 캐시 | 키 / 정책 |
|--------|------|----------|
| OHLCV | parquet (기존) | (market, symbol, interval, start, end) |
| AI 코치 응답 | JSON 디스크 (기존 ai 캐시 재사용) | `sha256(json.dumps({...}, sort_keys=True))[:16]` — 위 `recommend()` docstring 참조. **summary = 5 scalar 만**, equity_curve/trades 제외. collision 시 마지막 쓰기 우선 |
| 이력 | parquet (신규) | `data/_iterations/{symbol_safe}_{interval}.parquet`. 동일 `iteration_id` 존재 시 `CacheError` raise (idempotent 보장 X). path 는 `_safe_iteration_path()` 헬퍼로 `ITERATION_LOG_DIR` 기준 검증 |

---

## 5. UI/UX Design

### 5.1 5번째 탭 — Strategy Coach 페이지

```
┌──────────────────────────────────────────────────────────────────┐
│ TopBar (시세 테이프 + 시계)                                       │
├──────────────────────────────────────────────────────────────────┤
│ [01 차트분석] [02 매매신호] [03 백테스팅] [04 포트폴리오] [05 ★Coach]│
├────┬─────────────────────────────────────────────────────────────┤
│ Wat│ Strategy Coach — BTC/USDT 1d (365봉)                         │
│ chl├──────────────────┬──────────────────────┬───────────────────┤
│ ist│ EditorPanel      │ ResultPanel          │ CoachPanel        │
│    │  - 전략 이름      │  ┌─ IS (70%) ──────┐ │  진단:             │
│    │  - 매수 룰 (텍스트)│  │ equity curve   │ │  "추세 진입은 양호  │
│    │  - 매도 룰        │  │ 수익 +14.2%    │ │   하나 이탈 늦음"  │
│    │  - 거래비용 슬라이더│  │ Sharpe 0.92    │ │                  │
│    │   (commission/   │  │ MDD -8.4%      │ │  추천 3:           │
│    │    slippage/세금)│  └────────────────┘ │  ┌─ ATR(14) ★────┐│
│    │  - 최적화 목표 ▼  │  ┌─ OOS (30%) ────┐ │  │ role: exit    ││
│    │   [샤프 v]        │  │ equity curve   │ │  │ 추세 약화 시   ││
│    │  - "백테스트 실행" │  │ 수익 -3.1%     │ │  │   조기 청산   ││
│    │                  │  │ Sharpe -0.2    │ │  │ [적용+재실행] ││
│    │                  │  │ MDD -12.7%     │ │  └───────────────┘│
│    │                  │  └────────────────┘ │  ┌─ STOCH ⚠️─────┐│
│    │                  │  ⚠️ IS-OOS gap 17% │  │ available: NO ││
│    │                  │   과적합 위험 보통    │  │ "Claude에 추가││
│    │                  │                     │  │  요청하세요"  ││
│    │                  │                     │  └───────────────┘│
│    │                  │                     │  ┌─ OBV ★────────┐│
│    │                  │                     │  │ ...           ││
│    │                  │                     │  └───────────────┘│
│    └──────────────────┴──────────────────────┴───────────────────┤
│ HistoryTable (시도 비교, 클릭 → 복원)                              │
│ ┌──┬───────┬─────────┬─────────┬───────┬─────┬──────┬─────────┐ │
│ │#1│RSI<30 │+12.4%/IS│-1.2%/OOS│Sh 0.7 │MDD 6│gap 14│goal:샤프 │ │
│ │#2│+ADX>25│+14.2%/IS│-3.1%/OOS│Sh 0.9 │MDD 8│gap 17│goal:샤프 │ │
│ │#3│+ATR  │   …    │  …      │  …    │  … │  …  │  …       │ │
│ └──┴───────┴─────────┴─────────┴───────┴─────┴──────┴─────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 컴포넌트 매핑

| Component (jsx) | 책임 | 백엔드 호출 |
|-----------------|-------|-------------|
| `EditorPanel` | 전략 텍스트 입력 + 빌트인 자동완성 + 거래비용 + 목표 | `api.strategy.builtins()` 마운트 시 1회 |
| `ResultPanel` | IS/OOS equity 두 개 + stats 비교 카드 + overfit 경고 | (props로 전달) |
| `CoachPanel` | 진단 + 추천 카드 3개 + ⚠️ 미존재 표시 + 적용 버튼 | `api.strategy.coach(...)` |
| `HistoryTable` | 이력 표 + 행 클릭 → EditorPanel 복원 | `api.strategy.iterations(symbol, interval)` |
| (전체) | "백테스트 실행" 버튼 → split 결과 받아 ResultPanel + CoachPanel 갱신 | `api.strategy.backtest(...)` |
| `loader.js` | 1~4번 탭에서도 `?series=true` 사용해 차트 추세 띠 일관 | `api.trend({series: true, ...})` |

### 5.2.1 추천 적용 시 룰 결합 정책 (role → 위치 + 결합)

| `recommendation.role` | 결합 대상 | 결합 방식 |
|-----------------------|----------|----------|
| `entry_filter` | `buy_when` | `(existing) and (sample_rule)` |
| `filter` | `buy_when` | `(existing) and (sample_rule)` |
| `exit_rule` | `sell_when` | `(existing) or (sample_rule)` |
| `sizing` | (v0.5 미지원) | ⚠️ "포지션 사이징은 v0.6" 카드 표시 |

`sample_rule` 이 `null` 인 경우(드물게 AI 가 누락) → 카드의 "적용" 버튼 비활성 + tooltip "수식 누락".

### 5.3 기본 전략 템플릿 3개 (드롭다운)

| 이름 | 매수 | 매도 | 코멘트 |
|------|------|------|--------|
| **Conservative RSI** | `RSI_14 < 30 and ADX_14 > 20` | `RSI_14 > 70` | 추세 약할 때 진입 X |
| **MA Crossover** | `SMA_20 > SMA_60 and SMA_60 > SMA_120` | `SMA_20 < SMA_60` | 정배열 진입, 데드크로스 청산 |
| **MACD Momentum** | `MACDh_12_26_9 > 0 and MACD_12_26_9 > MACDs_12_26_9` | `MACDh_12_26_9 < 0` | MACD 히스토그램 양전 |
| **BB Squeeze** | `close < BBL_20_2.0_2.0 and RSI_14 < 40` | `close > BBM_20_2.0_2.0` | 볼린저 하단 터치 + RSI 약세 → 평균 회귀 |

---

## 6. Error Handling

### 6.1 신규 에러 흐름

```
사용자 룰 입력
    │
    ▼
validate_expression(buy_when, allowed_columns)
    │
    ├─ 실패 ─→ InvalidStrategyError
    │             ↓
    │         FastAPI 핸들러 → 400 INVALID_INPUT
    │             ↓
    │         프론트 EditorPanel → 빨간 inline 에러 + 위반 토큰 표시
    │
    └─ 성공 ─→ pandas.eval 실행 → boolean Series
                  │
                  ↓
              Backtest 실행 → BacktestResult
```

### 6.2 AI 코치 부분 실패 처리

```python
# api/ai.py
try:
    coach = strategy_coach.recommend(req)
except AIServiceError as e:
    # 백테스트 결과는 이미 사용자에게 표시됨. 코치만 비활성.
    log.warning("coach unavailable: %s", e)
    raise   # → 503, 프론트는 CoachPanel 만 회색 처리
```

### 6.4 OOS 데이터 부족 graceful 처리 (SkippedHolding 패턴 적용)

baseline 의 `SkippedHolding` 이 portfolio partial-success 패턴인 것처럼,
strategy backtest 도 OOS 봉 < 30 시 fail-loud 가 아닌 partial-success 반환:

```python
# core/strategy_engine.py run_split()
df_is, df_oos = split_70_30(df_with_indicators)
is_result = run_with_strategy_def(df_is, strategy_def, cash)

if len(df_oos) < 30:
    return BacktestSplitResult(
        is_result=is_result,
        oos_result=None,                                # ← partial
        is_period=(df_is.index[0], df_is.index[-1]),
        oos_period=None,
        is_oos_gap_pct=None,
        overfit_warning=False,
        costs_applied=strategy_def.costs,
        warnings=["OOS 봉 < 30 — 검증 스킵"],
    )

oos_result = run_with_strategy_def(df_oos, strategy_def, cash)
# ... 정상 경로 (gap 계산 + overfit_warning)
```

`BacktestSplitResult.oos_result: BacktestResult | None`, 동등하게 Pydantic `BacktestSplitResponse.oos_result: BacktestResultResponse | None`. 프론트는 OOS 패널을 "검증 불가" 회색 표시.

### 6.3 ⚠️ 빌트인 미존재 추천 처리

```javascript
// strategy-coach-page.jsx
function RecommendationCard({ rec, onApply }) {
  if (!rec.available) {
    return (
      <div className="rec-card unavailable">
        <span className="rec-flag">⚠️ 빌트인에 없음</span>
        <h4>{rec.indicator}</h4>
        <p>{rec.reason}</p>
        <p className="rec-cta muted">
          이 지표를 추가하려면 Claude(개발자)에게 요청하세요.
          예: "ATR(14) 지표 추가해줘"
        </p>
      </div>
    );
  }
  return (
    <div className="rec-card">
      <h4>{rec.indicator}</h4>
      <p>{rec.reason}</p>
      <p className="rec-synergy">{rec.expected_synergy}</p>
      <button onClick={() => onApply(rec)}>적용 + 재백테스트</button>
    </div>
  );
}
```

---

## 7. Security Considerations

- [x] **사용자 expression 안전성**: `pandas.eval(engine='python', parser='pandas')` + 사전 AST 화이트리스트
- [x] **expression 토큰 화이트리스트**: 산술/비교/논리/지표 컬럼명 + 화이트리스트 함수만
- [x] **import / attribute access 금지**: AST 검증으로 거부
- [x] **AI 응답 prompt injection 방지**: 사용자 룰 문자열은 prompt 에 *코드블록* 으로만 삽입, 시스템 프롬프트 위에서 직접 인용 X
- [x] **AI 응답 strict JSON**: response_format=json_object + Pydantic 검증
- [x] **이력 path traversal 방지**: `lib.cache._safe_resolve` 패턴 재사용
- [x] **거래비용 0 또는 비현실값 검증**: Pydantic gt=0 + 상한 (basis points 단위)

---

## 8. Test Plan

| 영역 | 테스트 | 도구 |
|------|-------|------|
| `validate_expression` | 화이트리스트 위반(`__import__`, `os.system`, attribute access) → InvalidStrategyError | pytest |
| `evaluate_rules` | 합성 데이터에서 알려진 시점에 entry/exit 정확 boolean | pytest |
| `split_70_30` | 길이 100 → IS 70 + OOS 30, timestamps 연속성 | pytest |
| `apply_trading_costs` | KR 종목 + apply_kr_tax 토글 → BPS 합산 정확 | pytest |
| `run_split` | mock indicators + 명시적 룰 → IS/OOS BacktestResult 둘 다 finite | pytest |
| `strategy_coach.parse_response` | 정상 JSON / 누락 키 / 잘못된 role / extra 텍스트 | pytest |
| `strategy_coach.recommend` | Mock Groq → CoachResponse, available 판정(빌트인 vs 자유) 정확 | pytest |
| `iteration_log.append+read` | tmp_path 에 1행 → 50행 누적, 정렬 보장, 동일 iteration_id 중복 거부 | pytest |
| `iteration_log.compare` | 다중 시도 → DataFrame 표 생성 | pytest |
| `api/strategy POST backtest` | TestClient → 200 + split 결과 + overfit_warning 자동 | pytest |
| `api/strategy POST backtest` | bad expression → 400 INVALID_INPUT | pytest |
| `api/ai/strategy-coach` | Mock Groq client → 200 + 추천 3개, available 분류 | pytest |
| `api/strategy/builtins` | 200 + 컬럼/연산자/헬퍼 목록 | pytest |
| `api/trend?series=true` | 기존 trend + series 추가, 길이 = candles | pytest |
| 통합 시나리오 | 사용자 룰 → split 백테스트 → AI 코치 → 추천 적용 → 재백테스트 → 이력 누적 | pytest + manual |

목표: 신규 ~25개 테스트, 기존 75개와 합쳐 100/100 통과.

---

## 9. Clean Architecture

### 9.1 새 모듈 레이어 분류

| Component | Layer | 위치 |
|-----------|-------|------|
| `api/strategy.py` | API Boundary | `backend/api/` |
| `api/ai.py (확장)` | API Boundary | `backend/api/` |
| `api/trend.py (확장)` | API Boundary | `backend/api/` |
| `core/strategy_engine.py` | Application | `backend/core/` |
| `core/strategy_coach.py` | Application | `backend/core/` |
| `core/iteration_log.py` | Infrastructure | `backend/core/` |
| `core/types/schemas.py (확장)` | Domain | `backend/core/types/` |
| `core/types/errors.py (확장 InvalidStrategyError)` | Domain | `backend/core/types/` |
| `Tradingmode/strategy-coach-page.jsx` | Frontend | `Tradingmode/` |

### 9.2 의존 방향

`api → core (engine/coach) → indicators/data_loader/types`. `iteration_log` 는 Infrastructure (parquet I/O) 라 lib.cache 와 동일 레벨. `strategy_coach` 는 `core.ai_interpreter._client` 재사용 (DRY).

---

## 10. Coding Convention (v0.4.1 그대로 + 보강)

| Item | 적용 |
|------|------|
| Python 모듈 | snake_case (`strategy_engine.py`) |
| 클래스 | PascalCase (`StrategyDef`, `BacktestSplitResult`, `CoachResponse`) |
| Enum 값 | snake_case 문자열 (`"return"`, `"sharpe"`) — 기존 컨벤션 |
| BPS 표기 | `*_bps: float`, basis point 단위 (1bp = 0.01%). 상한: commission/slippage ≤ 100, kr_sell_tax ≤ 50 |
| Expression 변수명 | indicator 컬럼명 그대로 (예: `RSI_14`, `BBU_20_2.0_2.0`) |
| AI 프롬프트 | 시스템 프롬프트 모듈 상단 상수 `SYSTEM_PROMPT_COACH` |
| 테스트 임시 디렉토리 | `tmp_path` 대신 baseline 의 **`writable_tmp_dir`** 픽스처 사용 (Windows 권한 호환) |

### 10.1 신규 환경변수 (Plan §7.3 정식 반영)

| Variable | Default | 용도 |
|----------|---------|------|
| `ITERATION_LOG_DIR` | `./data/_iterations` | parquet 이력 저장 root. `_safe_iteration_path()` 가 이 root 안만 허용 |
| `STRATEGY_COACH_MODEL` | `llama-3.3-70b-versatile` | `strategy_coach.recommend()` 의 디폴트 모델 (`os.environ.get` 으로 조회) |
| `MAX_STRATEGY_RULES` | `10` | `validate_expression()` 의 and/or 토큰 수 상한 (buy + sell 합산) |

---

## 11. Implementation Guide

### 11.1 폴더 구조 (변경분만)

```
backend/
├── api/
│   ├── strategy.py            ✨ NEW
│   ├── ai.py                  (확장)
│   └── trend.py               (확장)
├── core/
│   ├── strategy_engine.py     ✨ NEW
│   ├── strategy_coach.py      ✨ NEW
│   ├── iteration_log.py       ✨ NEW
│   └── types/
│       ├── schemas.py         (확장: StrategyDef, BacktestSplitResult, CoachResponse, IterationEntry, OptimizationGoal, TradingCosts)
│       └── errors.py          (확장: InvalidStrategyError)
└── tests/
    ├── test_strategy_engine.py        ✨
    ├── test_strategy_coach.py         ✨
    ├── test_iteration_log.py          ✨
    └── test_api/
        ├── test_strategy.py           ✨
        ├── test_strategy_coach.py     ✨
        └── test_trend_series.py       ✨

Tradingmode/
├── strategy-coach-page.jsx    ✨ NEW
├── api.js                     (확장: api.strategy.{backtest,coach,builtins,iterations})
├── app.jsx                    (확장: 5번째 탭 등록)
└── styles.css                 (확장: .rec-card / .history-table / .editor-panel 등)

data/
└── _iterations/               ✨ (gitignore — 이미 data/* 가 .gitignore 됨)
```

### 11.2 Implementation Order (~9시간)

#### Backend Phase A (3시간)
1. [ ] `core/types/schemas.py` 확장 — StrategyDef, BacktestSplitResult, CoachResponse, IterationEntry, OptimizationGoal, TradingCosts
2. [ ] `core/types/errors.py` — InvalidStrategyError 추가
3. [ ] `core/strategy_engine.py` — validate_expression (AST 화이트리스트), evaluate_rules, split_70_30, apply_trading_costs, run_split, BUILTIN_INDICATORS 메타
4. [ ] `tests/test_strategy_engine.py` — 위험 토큰 거부, 정상 룰 평가, split 길이, 비용 계산, run_split 통합

#### Backend Phase B (2시간)
5. [ ] `core/strategy_coach.py` — SYSTEM_PROMPT_COACH, build_prompt, parse_response, recommend (캐시 통합)
6. [ ] `tests/test_strategy_coach.py` — Mock Groq, JSON 파싱 케이스, available 판정
7. [ ] `core/iteration_log.py` — append/read/compare + path safety
8. [ ] `tests/test_iteration_log.py` — tmp_path 누적, 정렬, 중복 거부

#### Backend Phase C (1시간)
9. [ ] `api/strategy.py` — POST /api/strategy/backtest, GET /api/strategy/builtins, GET /api/strategy/iterations
10. [ ] `api/ai.py` 확장 — POST /api/ai/strategy-coach
11. [ ] `api/trend.py` 확장 — `?series=true` 분기
12. [ ] `main.py` 라우터 등록
13. [ ] `tests/test_api/test_strategy.py`, `test_strategy_coach.py`, `test_trend_series.py`

#### Frontend Phase D (3시간)
14. [ ] `Tradingmode/api.js` 확장 — strategy 메서드 5개
15. [ ] `Tradingmode/strategy-coach-page.jsx` — EditorPanel/ResultPanel/CoachPanel/HistoryTable
16. [ ] `Tradingmode/app.jsx` — 5번째 탭 등록
17. [ ] `Tradingmode/styles.css` — 5번째 탭 컴포넌트 스타일
18. [ ] 데모: BTC/USDT 1년치, 룰 1개로 백테스트 → AI 추천 → 적용 → 재백테스트

#### 통합 검증 (~30분)
19. [ ] `start.bat` 으로 기동, Playwright 또는 수동 브라우저 검증
20. [ ] `pytest -q` 100/100 PASSED 확인

### 11.3 Dependencies (변경 없음)

**Baseline 명시**: indicator 계산은 **pandas-only** (no pandas-ta). `core/indicators.py` 가 `pandas` + Wilder EMA 헬퍼만 사용. v0.5.0 도 pandas-ta 미도입.

기존 v0.4.1 의존성 그대로 (groq, fastapi, pyarrow, pandas, numpy). 신규 패키지 추가 X.

---

## 12. Future Extensions

- v0.6: AI 추천 거절 학습 누적 (사용자가 거절한 indicator·이유 → 다음 prompt 에 "이전 거절: X" 컨텍스트)
- v0.6: Walk-forward 분석 (rolling window split, 더 엄격)
- v0.7: 사용자 정의 수식 지표 (수식 → 컬럼 자동 생성, AST 안전 모드 확장)
- v2: 포트폴리오 단위 전략 (멀티 심볼 룰 평가 + 리밸런싱)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-30 | 초안 — Plan 기반 전체 설계, 신규 dataclass 6개 + Pydantic 8개 + 엔드포인트 5건 + 테스트 ~25개 | 900033@interojo.com |
| 0.2 | 2026-04-30 | design-validator 84% → 92%+ 후속 정리: AST 화이트리스트 노드 표 + `engine='numexpr'` 우선, BPS 상한 현실화(comm/slip≤100, kr_tax≤50), §10.1 신규 env 3종 정식 반영, BuiltinIndicator/IterationEntryModel/StrategyBuiltinsResponse Pydantic 추가, recommend() 캐시 키 sort_keys=True + 5 스칼라 summary, role→결합 위치 표(§5.2.1), OOS 부족 시 partial-success(§6.4 SkippedHolding 패턴), prompt injection JSON-only 명세, BB Squeeze 템플릿 추가, baseline pandas-only/writable_tmp_dir 픽스처 명시 | 900033@interojo.com |
