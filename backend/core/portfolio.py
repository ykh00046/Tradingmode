"""Portfolio analysis — bulk-analyse a list of holdings.

For each holding we run the existing single-symbol pipeline (fetch → indicators
→ signals → trend) and aggregate the results. FX conversion is applied so all
monetary fields end up in ``portfolio.base_currency``.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pandas as pd

from core import data_loader, signals, trend
from core.types.errors import PortfolioError
from core.types.schemas import (
    FetchRequest,
    FxQuote,
    Holding,
    HoldingAnalysis,
    Interval,
    Market,
    Portfolio,
    PortfolioAnalysis,
    SkippedHolding,
    TrendState,
)
from lib.logger import get_logger

log = get_logger(__name__)


# =============================================================================
# CSV input
# =============================================================================


REQUIRED_COLUMNS = ["market", "symbol", "quantity", "avg_price", "currency"]


def load_holdings_from_csv(path: str | Path) -> Portfolio:
    """Read a CSV file with columns ``market,symbol,quantity,avg_price,currency``."""
    p = Path(path)
    if not p.exists():
        raise PortfolioError(f"CSV not found: {p}", details={"path": str(p)})

    holdings: list[Holding] = []
    with p.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or set(REQUIRED_COLUMNS) - set(reader.fieldnames):
            raise PortfolioError(
                "CSV is missing required columns",
                details={"required": REQUIRED_COLUMNS, "found": reader.fieldnames or []},
            )

        for row_no, row in enumerate(reader, start=2):
            try:
                market = Market(row["market"].strip())
                qty = float(row["quantity"])
                avg = float(row["avg_price"])
                if qty <= 0 or avg <= 0:
                    raise ValueError("quantity and avg_price must be positive")
                currency = row["currency"].strip()
                if currency not in {"KRW", "USD", "USDT"}:
                    raise ValueError(f"unsupported currency: {currency}")
                holdings.append(
                    Holding(
                        market=market,
                        symbol=row["symbol"].strip(),
                        quantity=qty,
                        avg_price=avg,
                        currency=currency,                                   # type: ignore[arg-type]
                    )
                )
            except (KeyError, ValueError) as e:
                raise PortfolioError(
                    f"row {row_no}: {e}",
                    details={"row": row, "row_no": row_no},
                ) from e

    if not holdings:
        raise PortfolioError("CSV contains no holdings")
    return Portfolio(holdings=holdings, base_currency="KRW")


# =============================================================================
# FX
# =============================================================================


def _static_fx_quote(pair: str, rate: float, as_of: pd.Timestamp, source: str = "static") -> FxQuote:
    return FxQuote(pair=pair, rate=rate, as_of=as_of, source=source)


def _invert_fx_quote(base_quote: FxQuote, target_pair: str) -> FxQuote:
    if base_quote.rate <= 0:
        raise PortfolioError(
            f"cannot invert FX rate for {target_pair}",
            details={"pair": base_quote.pair, "rate": base_quote.rate},
        )
    return FxQuote(
        pair=target_pair,
        rate=1.0 / base_quote.rate,
        as_of=base_quote.as_of,
        source=base_quote.source,
    )


def _fetch_fx(pair: str, as_of: pd.Timestamp) -> FxQuote:
    """Fetch a single FX quote via FinanceDataReader.

    Falls back to a sensible fixed rate on failure so the portfolio page can
    still render — failure here should never break the whole analysis.
    """
    if pair in {"USDT/USD", "USD/USDT"}:
        return _static_fx_quote(pair, 1.0, as_of)

    fallback = {
        "USDT/KRW": 1380.0,
        "USD/KRW": 1380.0,
        "KRW/USD": 1 / 1380.0,
    }.get(pair, 1.0)
    try:
        import FinanceDataReader as fdr                                      # type: ignore

        ticker = "USD/KRW" if pair in ("USDT/KRW", "USD/KRW") else pair
        df = fdr.DataReader(ticker, (as_of - pd.Timedelta(days=7)).strftime("%Y-%m-%d"))
        if df is None or df.empty:
            raise RuntimeError("empty fx series")
        latest = df.iloc[-1]
        rate = float(latest.get("Close", latest.get("close", fallback)))
    except Exception as e:                                                   # pragma: no cover
        log.warning("fx fetch failed for %s: %s — using fallback %s", pair, e, fallback)
        rate = fallback
    return FxQuote(pair=pair, rate=rate, as_of=as_of)


def _resolve_fx_pair(pair: str, as_of: pd.Timestamp) -> FxQuote:
    """Return an FX quote for ``pair``, handling synthetic and inverted pairs."""
    if pair == "KRW/USD":
        return _invert_fx_quote(_fetch_fx("USD/KRW", as_of), target_pair=pair)
    return _fetch_fx(pair, as_of)


def _resolve_fx_rates(
    portfolio: Portfolio,
    as_of: pd.Timestamp,
) -> dict[str, FxQuote]:
    """Return FX quotes for every (currency → base_currency) pair we will need."""
    base = portfolio.base_currency
    pairs_needed: set[str] = set()
    for h in portfolio.holdings:
        if h.currency != base:
            pairs_needed.add(f"{h.currency}/{base}")
    return {p: _resolve_fx_pair(p, as_of) for p in pairs_needed}


# =============================================================================
# Single holding
# =============================================================================


def _analyze_holding(
    holding: Holding,
    fx_rates: dict[str, FxQuote],
    base_currency: str,
    lookback_days: int,
    as_of: pd.Timestamp,
) -> HoldingAnalysis:
    """Run the single-symbol pipeline and convert into ``HoldingAnalysis``."""
    fx_pair = f"{holding.currency}/{base_currency}"
    fx_rate = 1.0 if holding.currency == base_currency else fx_rates[fx_pair].rate

    req = FetchRequest(
        market=holding.market,
        symbol=holding.symbol,
        interval=Interval.D1,
        start=as_of - pd.Timedelta(days=lookback_days),
        end=as_of,
    )
    df, _ = data_loader.fetch(req)
    from core import indicators as core_indicators

    df = core_indicators.compute(df)

    last_close_local = float(df["close"].iloc[-1])
    current_price = last_close_local * fx_rate
    market_value = holding.quantity * current_price
    cost_basis = holding.quantity * holding.avg_price * fx_rate
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0

    trend_now = trend.classify(df)
    detected = signals.detect_all(df)
    latest = detected[-5:]                                                   # last 5 signals

    return HoldingAnalysis(
        holding=holding,
        current_price_local=last_close_local,
        current_price=current_price,
        market_value=market_value,
        cost_basis=cost_basis,
        pnl=pnl,
        pnl_pct=pnl_pct,
        weight=0.0,                                                          # filled in aggregate step
        fx_rate=fx_rate,
        trend=trend_now,
        latest_signals=latest,
    )


# =============================================================================
# Aggregation
# =============================================================================


def aggregate_trend(holdings_analysis: list[HoldingAnalysis]) -> dict[TrendState, int]:
    counts = Counter(ha.trend for ha in holdings_analysis)
    return {state: counts.get(state, 0) for state in TrendState}


def analyze(
    portfolio: Portfolio,
    as_of: pd.Timestamp | None = None,
    lookback_days: int = 180,
) -> PortfolioAnalysis:
    """Run the full portfolio pipeline and return a ``PortfolioAnalysis``.

    Failures on individual holdings are logged but do not abort the whole
    analysis — the returned ``holdings_analysis`` may have fewer entries than
    the input portfolio. This keeps a single bad ticker from breaking the page.
    """
    as_of = as_of or pd.Timestamp.now(tz='UTC').normalize()
    fx_rates = _resolve_fx_rates(portfolio, as_of)
    base_currency = portfolio.base_currency

    analyses: list[HoldingAnalysis] = []
    skipped: list[SkippedHolding] = []
    for h in portfolio.holdings:
        try:
            analyses.append(_analyze_holding(h, fx_rates, base_currency, lookback_days, as_of))
        except Exception as e:
            log.warning(
                "skipping holding %s/%s: %s",
                h.market.value,
                h.symbol,
                e,
            )
            skipped.append(
                SkippedHolding(
                    market=h.market,
                    symbol=h.symbol,
                    reason=str(e),
                )
            )

    total_market_value = sum(a.market_value for a in analyses)
    total_cost_basis = sum(a.cost_basis for a in analyses)

    # Replace zero-weight placeholder with real weights now that we have totals.
    if total_market_value > 0:
        analyses = [
            HoldingAnalysis(
                holding=a.holding,
                current_price_local=a.current_price_local,
                current_price=a.current_price,
                market_value=a.market_value,
                cost_basis=a.cost_basis,
                pnl=a.pnl,
                pnl_pct=a.pnl_pct,
                weight=a.market_value / total_market_value,
                fx_rate=a.fx_rate,
                trend=a.trend,
                latest_signals=a.latest_signals,
            )
            for a in analyses
        ]

    total_pnl = total_market_value - total_cost_basis
    total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis else 0.0

    return PortfolioAnalysis(
        portfolio=portfolio,
        holdings_analysis=analyses,
        total_market_value=total_market_value,
        total_cost_basis=total_cost_basis,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        trend_summary=aggregate_trend(analyses),
        base_currency=base_currency,
        fx_rates=fx_rates,
        as_of=as_of,
        skipped_holdings=skipped,
    )
