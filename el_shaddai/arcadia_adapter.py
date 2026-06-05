"""A.R.C.A.D.I.A. adapter for XLRE Role proxies.

A.R.C.A.D.I.A. (Asset Real-estate Cycle Analysis & Demand Intelligence
Architecture) audits XLRE as the S&P 500 real-estate sector ETF: a basket of
large listed real-estate companies that should behave like rent/cash-flow,
digital-infrastructure landlord, and yield-air-mass exposure rather than a
plain equity-sector proxy.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from math import log, sqrt
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS

ARCADIA_TICKERS: Mapping[str, str] = {
    "XLRE": "S&P 500 real-estate sector ETF",
    "SPY": "US equity submission anchor",
    "VNQ": "Broad listed REIT comparison",
    "HYG": "Credit oxygen sensor",
    "UUP": "US dollar headwind sensor",
    "DBC": "Commodity / inflation pass-through proxy",
    "TLT": "Duration / rate-shock proxy",
    "^TNX": "US 10-year Treasury yield",
}

XLRE_ARCADIA_COMPONENTS: Sequence[str] = (
    "rental_cashflow",
    "digital_infrastructure_demand",
    "dividend_sustainability",
    "yield_spread_advantage",
    "reit_relative_strength",
    "inflation_pass_through",
    "occupancy_environment",
    "real_rate_shock",
    "credit_stress",
    "dollar_headwind",
    "equity_submission",
)

_COLUMN_ALIASES: Mapping[str, str] = {
    "xlre_close": "XLRE",
    "xlre": "XLRE",
    "spy_close": "SPY",
    "spy": "SPY",
    "vnq_close": "VNQ",
    "vnq": "VNQ",
    "hyg_close": "HYG",
    "hyg": "HYG",
    "uup_close": "UUP",
    "uup": "UUP",
    "dbc_close": "DBC",
    "dbc": "DBC",
    "tlt_close": "TLT",
    "tlt": "TLT",
    "tnx": "^TNX",
    "^tnx": "^TNX",
}


@dataclass(frozen=True)
class ArcadiaResult:
    """Result of generating XLRE Role inputs from A.R.C.A.D.I.A."""

    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_arcadia: bool
    raw_metrics: Mapping[str, float]
    applied_caps: List[str]
    real_estate_regime_interpretation: str


def _clamp(value: float, low: float = -2.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _returns(prices: Sequence[float]) -> List[float]:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    return [log(cur / prev) for prev, cur in zip(values[:-1], values[1:])]


def _correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    left_diffs = [value - left_mean for value in left]
    right_diffs = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(left_diffs, right_diffs))
    denominator = sqrt(sum(value * value for value in left_diffs)) * sqrt(sum(value * value for value in right_diffs))
    if denominator == 0:
        return None
    return numerator / denominator


def _pct_change(prices: Sequence[float]) -> float:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    if len(values) < 2 or values[0] == 0:
        return 0.0
    return values[-1] / values[0] - 1.0


def _drawdown(prices: Sequence[float]) -> float:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    if not values:
        return 0.0
    peak = max(values)
    return values[-1] / peak - 1.0 if peak else 0.0


def _volatility(prices: Sequence[float], window: int) -> float:
    rets = _returns(prices)[-window:]
    if len(rets) < 2:
        return 0.0
    avg = _mean(rets)
    return sqrt(sum((value - avg) ** 2 for value in rets) / (len(rets) - 1)) * sqrt(252.0)


def _latest_date(price_data: Mapping[str, Sequence[float] | Sequence[str]]) -> str:
    dates = price_data.get("__dates__")
    if dates:
        return str(list(dates)[-1])
    return str(date.today())


def _neutral_result(warnings: List[str], source: str = "A.R.C.A.D.I.A. yfinance") -> ArcadiaResult:
    neutral = {name: float(DEFAULT_ROLE_INPUTS["XLRE"].get(name, 0.0)) for name in XLRE_ARCADIA_COMPONENTS}
    return ArcadiaResult(
        role_inputs={"XLRE": neutral},
        proxies=neutral,
        reasons={name: "neutral fallback" for name in neutral},
        warnings=warnings,
        data_date="unknown",
        source=source,
        used_arcadia=False,
        raw_metrics={},
        applied_caps=[],
        real_estate_regime_interpretation="neutral fallback",
    )


def fetch_arcadia_price_data(period: str = "2y", tickers: Sequence[str] | None = None) -> Dict[str, List[float] | List[str]]:
    """Fetch A.R.C.A.D.I.A. prices with yfinance.

    yfinance is imported lazily so the CLI remains usable without optional data
    dependencies. Provider failures are converted to neutral fallbacks by
    ``latest_xlre_role_inputs``.
    """

    import yfinance as yf  # type: ignore[import-not-found]

    selected = list(tickers or ARCADIA_TICKERS.keys())
    data = yf.download(selected, period=period, progress=False, auto_adjust=False)
    close = data["Close"] if hasattr(data, "__getitem__") else data
    prices: Dict[str, List[float] | List[str]] = {}
    for ticker in selected:
        try:
            series = close[ticker] if len(selected) > 1 else close
            cleaned = series.ffill().dropna()
            values = [float(value) for value in cleaned.tolist()]
            if values:
                prices[ticker] = values
                if "__dates__" not in prices:
                    prices["__dates__"] = [str(index.date()) if hasattr(index, "date") else str(index) for index in cleaned.index.tolist()]
        except Exception:  # noqa: BLE001 - missing ticker columns are handled downstream.
            continue
    return prices


def compute_xlre_role_proxies(price_data: Mapping[str, Sequence[float] | Sequence[str]], window: int = 60) -> ArcadiaResult:
    """Convert market proxies into direction-adjusted -2..+2 XLRE Role inputs."""

    numeric = {ticker: [float(value) for value in price_data.get(ticker, [])] for ticker in ARCADIA_TICKERS}
    required = ["XLRE", "SPY", "HYG", "UUP", "DBC", "TLT"]
    missing = [ticker for ticker in required if len(numeric.get(ticker, [])) < 3]
    if missing:
        return _neutral_result([f"warning: A.R.C.A.D.I.A. data insufficient for {', '.join(missing)}; neutral XLRE Role proxy fallback applied."])

    xlre = numeric["XLRE"]
    spy = numeric["SPY"]
    vnq = numeric.get("VNQ", [])
    hyg = numeric["HYG"]
    uup = numeric["UUP"]
    dbc = numeric["DBC"]
    tlt = numeric["TLT"]
    tnx = numeric.get("^TNX", [])

    aligned = min(len(_returns(xlre)), len(_returns(spy)), window)
    corr_xlre_spy = _correlation(_returns(xlre)[-aligned:], _returns(spy)[-aligned:]) if aligned >= 2 else None
    if corr_xlre_spy is None:
        return _neutral_result(["warning: A.R.C.A.D.I.A. could not compute XLRE/SPY correlation; neutral XLRE Role proxy fallback applied."])

    xlre_trend = _pct_change(xlre)
    spy_trend = _pct_change(spy)
    vnq_trend = _pct_change(vnq) if vnq else 0.0
    hyg_trend = _pct_change(hyg)
    uup_trend = _pct_change(uup)
    dbc_trend = _pct_change(dbc)
    tlt_trend = _pct_change(tlt)
    tnx_change = (tnx[-1] - tnx[0]) if len(tnx) >= 2 else 0.0
    tnx_level = tnx[-1] if tnx else 0.0
    xlre_drawdown = _drawdown(xlre)
    xlre_vol = _volatility(xlre, window=window)
    rel_xlre_spy = xlre_trend - spy_trend
    rel_vnq_spy = vnq_trend - spy_trend if vnq else rel_xlre_spy
    hyg_divergence = hyg_trend - spy_trend

    real_rate_proxy = _clamp((-tnx_change * 2.5 if tnx else 0.0) + tlt_trend * 8.0)
    credit_proxy = _clamp(hyg_trend * 12.0 + hyg_divergence * 8.0)
    dollar_proxy = _clamp(-uup_trend * 20.0)
    if corr_xlre_spy >= 0.95:
        equity_proxy = -2.0
    elif corr_xlre_spy >= 0.85:
        equity_proxy = -1.25
    elif corr_xlre_spy >= 0.75:
        equity_proxy = -0.5
    elif corr_xlre_spy <= 0.55:
        equity_proxy = 0.5
    else:
        equity_proxy = 0.0

    proxies = {
        "rental_cashflow": round(_clamp(xlre_trend * 8.0 + xlre_drawdown * 4.0 - max(0.0, xlre_vol - 0.20) * 2.0), 3),
        "digital_infrastructure_demand": 0.0,
        "dividend_sustainability": 0.0,
        "yield_spread_advantage": round(_clamp((-tnx_change * 2.0 - max(0.0, tnx_level - 4.0) * 0.25) if tnx else tlt_trend * 8.0), 3),
        "reit_relative_strength": round(_clamp(((rel_xlre_spy + rel_vnq_spy) / 2.0) * 10.0), 3),
        "inflation_pass_through": round(_clamp(dbc_trend * 4.0 + rel_xlre_spy * 6.0), 3),
        "occupancy_environment": 0.0,
        "real_rate_shock": round(real_rate_proxy, 3),
        "credit_stress": round(credit_proxy, 3),
        "dollar_headwind": round(dollar_proxy, 3),
        "equity_submission": round(equity_proxy, 3),
    }

    applied_caps: List[str] = []
    if proxies["real_rate_shock"] <= -1.0:
        applied_caps.append("real_rate_shock severe => Role Score cap 55")
    if proxies["real_rate_shock"] <= -1.0 and proxies["credit_stress"] <= -1.0:
        applied_caps.append("real_rate_shock severe + credit_stress severe => Role Score cap 45")
    if proxies["real_rate_shock"] <= -1.0 and proxies["credit_stress"] <= -1.0 and proxies["equity_submission"] <= -1.0:
        applied_caps.append("real_rate_shock severe + credit_stress severe + equity_submission severe => Role Score cap 35")
    if proxies["dollar_headwind"] <= -1.0 and proxies["credit_stress"] <= -1.0:
        applied_caps.append("dollar_headwind severe + credit_stress severe => Role Score cap 50")

    if proxies["equity_submission"] <= -1.0:
        interpretation = "XLRE is at risk of degrading into an equity sector wearing a real-estate face."
    elif proxies["real_rate_shock"] <= -1.0 or proxies["credit_stress"] <= -1.0:
        interpretation = "XLRE still has landlord/yield attributes, but the rates-credit weather is hostile."
    elif proxies["reit_relative_strength"] > 0.5 and proxies["rental_cashflow"] >= 0.0:
        interpretation = "XLRE is behaving closer to a digital-society landlord harvesting rent-like cash flows."
    else:
        interpretation = "XLRE is in a mixed real-estate regime; role evidence is present but not dominant."

    reasons = {
        "rental_cashflow": f"XLRE trend {xlre_trend:+.3f}, drawdown {xlre_drawdown:+.3f}, annualized vol {xlre_vol:.3f}; stability/downside resistance proxies rent-like cash-flow durability.",
        "digital_infrastructure_demand": "Direct data-center/tower/logistics demand data is not ingested in v1.6; neutral expansion slot retained.",
        "dividend_sustainability": "Distribution trend data is not ingested in v1.6; neutral proxy retained until yield/distribution history is connected.",
        "yield_spread_advantage": f"TNX change {tnx_change:+.3f}, TNX level {tnx_level:.3f}, TLT trend {tlt_trend:+.3f}; rising Treasury yields reduce XLRE's relative yield-air-mass advantage.",
        "reit_relative_strength": f"XLRE/SPY relative return {rel_xlre_spy:+.3f}; VNQ/SPY relative return {rel_vnq_spy:+.3f}; REIT relative strength supports sector-specific role.",
        "inflation_pass_through": f"DBC trend {dbc_trend:+.3f} with XLRE/SPY relative return {rel_xlre_spy:+.3f}; commodity inflation helps only when XLRE can absorb/pass through it.",
        "occupancy_environment": "Vacancy/occupancy fundamentals are not ingested in v1.6; neutral expansion slot retained.",
        "real_rate_shock": f"TNX change {tnx_change:+.3f} and TLT trend {tlt_trend:+.3f}; rate shocks compress discounted property cash flows.",
        "credit_stress": f"HYG trend {hyg_trend:+.3f}; HYG/SPY divergence {hyg_divergence:+.3f}; weaker high-yield credit raises real-estate refinancing stress.",
        "dollar_headwind": f"UUP trend {uup_trend:+.3f}; strong dollar is treated as a broad risk-asset headwind.",
        "equity_submission": f"XLRE/SPY return correlation {corr_xlre_spy:+.3f}; excessive correlation indicates submission to the equity market rather than independent landlord behavior.",
    }
    raw_metrics = {
        "xlre_trend": round(xlre_trend, 6),
        "spy_trend": round(spy_trend, 6),
        "vnq_trend": round(vnq_trend, 6),
        "hyg_trend": round(hyg_trend, 6),
        "uup_trend": round(uup_trend, 6),
        "dbc_trend": round(dbc_trend, 6),
        "tlt_trend": round(tlt_trend, 6),
        "tnx_change": round(tnx_change, 6),
        "tnx_level": round(tnx_level, 6),
        "xlre_spy_corr": round(corr_xlre_spy, 6),
        "xlre_drawdown": round(xlre_drawdown, 6),
        "xlre_volatility": round(xlre_vol, 6),
    }
    return ArcadiaResult(
        role_inputs={"XLRE": proxies},
        proxies=proxies,
        reasons=reasons,
        warnings=[],
        data_date=_latest_date(price_data),
        source="A.R.C.A.D.I.A. market proxies",
        used_arcadia=True,
        raw_metrics=raw_metrics,
        applied_caps=applied_caps,
        real_estate_regime_interpretation=interpretation,
    )


def load_arcadia_prices_csv(path: str) -> Dict[str, List[float] | List[str]]:
    """Load manual A.R.C.A.D.I.A. prices from long or wide CSV.

    Wide format accepts ``date,xlre_close,spy_close,vnq_close,hyg_close,uup_close,
    dbc_close,tlt_close,tnx``. Long format accepts ``date,ticker,close``.
    """

    prices: Dict[str, List[float] | List[str]] = {ticker: [] for ticker in ARCADIA_TICKERS}
    prices["__dates__"] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        lower_fields = {name.lower(): name for name in fieldnames}
        if {"date", "ticker", "close"}.issubset(set(lower_fields)):
            rows_by_ticker: Dict[str, List[tuple[str, float]]] = {ticker: [] for ticker in ARCADIA_TICKERS}
            date_column = lower_fields["date"]
            ticker_column = lower_fields["ticker"]
            close_column = lower_fields["close"]
            for row in reader:
                ticker = row[ticker_column].strip().upper()
                if ticker == "TNX":
                    ticker = "^TNX"
                if ticker in rows_by_ticker and row.get(close_column) not in (None, ""):
                    rows_by_ticker[ticker].append((row.get(date_column, ""), float(row[close_column])))
            for ticker, values in rows_by_ticker.items():
                ordered = sorted(values)
                prices[ticker] = [value for _, value in ordered]
            all_dates = sorted({row_date for values in rows_by_ticker.values() for row_date, _ in values})
            prices["__dates__"] = all_dates
            return prices
        for row in reader:
            row_date = row.get(lower_fields.get("date", "date"), "")
            if row_date:
                prices["__dates__"].append(row_date)
            row_lower = {key.lower(): value for key, value in row.items() if key is not None}
            for csv_name, ticker in _COLUMN_ALIASES.items():
                value = row_lower.get(csv_name)
                if value not in (None, ""):
                    prices[ticker].append(float(value))
    return prices


def xlre_role_inputs_from_csv(path: str, window: int = 60) -> ArcadiaResult:
    """Generate XLRE Role inputs from a manual A.R.C.A.D.I.A. price CSV."""

    result = compute_xlre_role_proxies(load_arcadia_prices_csv(path), window=window)
    return ArcadiaResult(
        result.role_inputs,
        result.proxies,
        result.reasons,
        result.warnings,
        result.data_date,
        f"manual A.R.C.A.D.I.A. CSV: {path}",
        result.used_arcadia,
        result.raw_metrics,
        result.applied_caps,
        result.real_estate_regime_interpretation,
    )


def latest_xlre_role_inputs(period: str = "2y", window: int = 60) -> ArcadiaResult:
    """Fetch A.R.C.A.D.I.A. prices and return latest XLRE Role proxy inputs."""

    try:
        price_data = fetch_arcadia_price_data(period=period)
        return compute_xlre_role_proxies(price_data, window=window)
    except Exception as exc:  # noqa: BLE001 - CLI must keep running on provider failures.
        warning = f"warning: failed to fetch A.R.C.A.D.I.A. yfinance data ({exc}); neutral XLRE Role proxy fallback applied."
        return _neutral_result([warning])
