"""Project A.U.R.A. adapter for GLDM Role proxies.

A.U.R.A. observes gold's rolling correlation regime against risk, rates,
inflation, currency, and liquidity anchors.  The adapter converts those
correlations into GLDM-direction-adjusted -2..+2 Role proxies, where +2 is
favorable for gold's stateless store-of-value / currency-hedge / real-asset
protection role.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import log, sqrt
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS

AURA_TICKERS: Mapping[str, str] = {
    "GLD": "Gold proxy",
    "SPY": "Risk / equities",
    "TLT": "Rates / duration",
    "DBC": "Inflation / commodities",
    "UUP": "Currency / US dollar",
    "BTC-USD": "Liquidity / non-fiat asset",
}

AURA_TARGETS: Sequence[str] = ("SPY", "TLT", "DBC", "UUP", "BTC-USD")

GLDM_AURA_COMPONENTS: Sequence[str] = (
    "safe_haven_pressure",
    "real_rate",
    "dxy",
    "central_bank_buying",
    "geopolitical_risk",
    "inflation_regime",
    "currency_hedge",
    "liquidity_regime",
    "macro_independence",
    "dominant_anchor_strength",
)


@dataclass(frozen=True)
class AuraResult:
    """Result of attempting to generate GLDM Role inputs from A.U.R.A."""

    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_aura: bool
    correlations: Mapping[str, float]
    dominant_anchor: str
    dominant_correlation: float
    gri_score: float
    gri_interpretation: str


def _clamp(value: float, low: float = -2.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    left_diffs = [value - left_mean for value in left]
    right_diffs = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(left_diffs, right_diffs))
    left_denominator = sqrt(sum(value * value for value in left_diffs))
    right_denominator = sqrt(sum(value * value for value in right_diffs))
    denominator = left_denominator * right_denominator
    if denominator == 0:
        return None
    return numerator / denominator


def _returns(prices: Sequence[float]) -> List[float]:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    return [log(cur / prev) for prev, cur in zip(values[:-1], values[1:])]


def _neutral_result(warnings: List[str], source: str = "A.U.R.A. yfinance") -> AuraResult:
    neutral = {name: float(DEFAULT_ROLE_INPUTS["GLDM"].get(name, 0.0)) for name in GLDM_AURA_COMPONENTS}
    return AuraResult(
        role_inputs={"GLDM": neutral},
        proxies=neutral,
        reasons={},
        warnings=warnings,
        data_date="unknown",
        source=source,
        used_aura=False,
        correlations={},
        dominant_anchor="N/A",
        dominant_correlation=0.0,
        gri_score=0.0,
        gri_interpretation="neutral fallback",
    )


def fetch_aura_price_data(period: str = "2y", tickers: Sequence[str] | None = None) -> Dict[str, List[float]]:
    """Fetch A.U.R.A. prices with yfinance.

    Importing yfinance inside the function keeps the base CLI usable in minimal
    environments. Missing yfinance/network errors are handled by
    ``latest_gldm_role_inputs`` fallback logic.
    """

    import yfinance as yf  # type: ignore[import-not-found]

    selected = list(tickers or AURA_TICKERS.keys())
    data = yf.download(selected, period=period, progress=False, auto_adjust=False)
    close = data["Close"] if hasattr(data, "__getitem__") else data
    prices: Dict[str, List[float]] = {}
    for ticker in selected:
        series = close[ticker] if len(selected) > 1 else close
        prices[ticker] = [float(value) for value in series.ffill().dropna().tolist()]
    return prices


def compute_gold_correlations(price_data: Mapping[str, Sequence[float]], window: int = 60) -> Dict[str, float]:
    """Compute latest rolling-window correlations of GLD returns vs targets."""

    gold_returns = _returns(price_data.get("GLD", []))
    correlations: Dict[str, float] = {}
    for ticker in AURA_TARGETS:
        target_returns = _returns(price_data.get(ticker, []))
        aligned = min(len(gold_returns), len(target_returns), window)
        if aligned < 2:
            continue
        corr = _correlation(gold_returns[-aligned:], target_returns[-aligned:])
        if corr is not None:
            correlations[ticker] = round(corr, 6)
    return correlations


def compute_gold_regime(correlations: Mapping[str, float]) -> Dict[str, float | str]:
    """Compute dominant anchor and Gold Regime Index (GRI)."""

    if not correlations:
        return {"dominant_anchor": "N/A", "dominant_correlation": 0.0, "gri_score": 0.0, "gri_interpretation": "neutral fallback"}
    dominant_anchor = max(correlations, key=lambda ticker: abs(correlations[ticker]))
    dominant_correlation = float(correlations[dominant_anchor])
    gri_score = (
        float(correlations.get("DBC", 0.0))
        - float(correlations.get("TLT", 0.0))
        - float(correlations.get("UUP", 0.0))
        + float(correlations.get("BTC-USD", 0.0))
    )
    if gri_score > 1.0:
        interpretation = "liquidity/inflation regime"
    elif gri_score < -1.0:
        interpretation = "traditional macro/rates-dollar regime"
    else:
        interpretation = "transition/mixed regime"
    return {
        "dominant_anchor": dominant_anchor,
        "dominant_correlation": round(dominant_correlation, 6),
        "gri_score": round(gri_score, 6),
        "gri_interpretation": interpretation,
    }


def _dominant_anchor_proxy(anchor: str, correlation: float) -> float:
    strength = abs(correlation)
    if anchor == "DBC":
        return _clamp(strength * 2.0)
    if anchor == "UUP":
        return _clamp(-strength * 2.0 if correlation > 0 else strength * 1.0)
    if anchor == "BTC-USD":
        return _clamp(strength * 1.2)
    if anchor == "TLT":
        return _clamp(-strength * 0.8)
    if anchor == "SPY":
        return _clamp(strength * 0.8 if correlation < 0 else -strength * 1.5)
    return 0.0


def compute_gldm_role_proxies(price_data: Mapping[str, Sequence[float]], window: int = 60) -> AuraResult:
    """Convert A.U.R.A. correlations into GLDM direction-adjusted Role proxies."""

    correlations = compute_gold_correlations(price_data, window=window)
    missing = sorted(set(AURA_TARGETS) - set(correlations))
    if missing:
        return _neutral_result([f"warning: A.U.R.A. could not compute correlation(s): {', '.join(missing)}"])

    regime = compute_gold_regime(correlations)
    dominant_anchor = str(regime["dominant_anchor"])
    dominant_correlation = float(regime["dominant_correlation"])
    gri_score = float(regime["gri_score"])
    gri_interpretation = str(regime["gri_interpretation"])

    corr_spy = float(correlations.get("SPY", 0.0))
    corr_tlt = float(correlations.get("TLT", 0.0))
    corr_dbc = float(correlations.get("DBC", 0.0))
    corr_uup = float(correlations.get("UUP", 0.0))
    corr_btc = float(correlations.get("BTC-USD", 0.0))
    macro_dependence = (abs(corr_spy) + abs(corr_tlt) + abs(corr_uup)) / 3.0

    proxies = {
        "safe_haven_pressure": round(_clamp(-corr_spy * 2.0), 3),
        "real_rate": round(_clamp(-corr_tlt * 1.0), 3),
        "dxy": round(_clamp(-corr_uup * 2.0), 3),
        "central_bank_buying": 0.0,
        "geopolitical_risk": 0.0,
        "inflation_regime": round(_clamp(corr_dbc * 2.0), 3),
        "currency_hedge": round(_clamp(-corr_uup * 2.0), 3),
        "liquidity_regime": round(_clamp(corr_btc * 2.0), 3),
        "macro_independence": round(_clamp(2.0 - macro_dependence * 4.0), 3),
        "dominant_anchor_strength": round(_dominant_anchor_proxy(dominant_anchor, dominant_correlation), 3),
    }
    warnings: List[str] = []
    if corr_btc > 0.85:
        warnings.append("warning: GLD/BTC correlation is extremely high; gold may be behaving like an excess-liquidity asset rather than pure store of value.")

    reasons = {
        "safe_haven_pressure": f"GLD/SPY corr {corr_spy:+.3f}; lower/negative equity correlation supports safe-haven role.",
        "real_rate": f"GLD/TLT corr {corr_tlt:+.3f}; strong rates-anchor dependence is treated as neutral-to-negative for independent value storage.",
        "dxy": f"GLD/UUP corr {corr_uup:+.3f}; negative dollar correlation supports currency hedge role.",
        "central_bank_buying": "A.U.R.A. v1.2 does not ingest central-bank buying data; neutral proxy retained.",
        "geopolitical_risk": "A.U.R.A. v1.2 does not ingest geopolitical-risk data; neutral proxy retained.",
        "inflation_regime": f"GLD/DBC corr {corr_dbc:+.3f}; positive commodity correlation supports real-asset inflation regime.",
        "currency_hedge": f"GLD/UUP corr {corr_uup:+.3f}; negative dollar correlation is favorable, positive correlation is mixed/less useful.",
        "liquidity_regime": f"GLD/BTC corr {corr_btc:+.3f}; positive BTC correlation supports non-fiat/liquidity regime but extremes are flagged.",
        "macro_independence": f"Average abs corr to SPY/TLT/UUP is {macro_dependence:.3f}; lower dependence supports stateless value storage.",
        "dominant_anchor_strength": f"Dominant Anchor: {dominant_anchor} ({dominant_correlation:+.3f}); GRI {gri_score:+.3f} = {gri_interpretation}.",
    }
    return AuraResult(
        role_inputs={"GLDM": proxies},
        proxies=proxies,
        reasons=reasons,
        warnings=warnings,
        data_date=str(date.today()),
        source="Project A.U.R.A. yfinance",
        used_aura=True,
        correlations=correlations,
        dominant_anchor=dominant_anchor,
        dominant_correlation=dominant_correlation,
        gri_score=gri_score,
        gri_interpretation=gri_interpretation,
    )


def load_aura_prices_csv(path: str) -> Dict[str, List[float]]:
    """Load manual A.U.R.A. prices from CSV.

    Supports either long format (date,ticker,close) or wide format with a date
    column plus ticker columns. GLD is required and SPY/TLT/DBC/UUP/BTC-USD are
    used as anchors.
    """

    import csv

    prices: Dict[str, List[float]] = {ticker: [] for ticker in AURA_TICKERS}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if {"date", "ticker", "close"}.issubset(set(fieldnames)):
            rows_by_ticker: Dict[str, List[tuple[str, float]]] = {ticker: [] for ticker in AURA_TICKERS}
            for row in reader:
                ticker = row["ticker"].strip()
                if ticker in rows_by_ticker:
                    rows_by_ticker[ticker].append((row.get("date", ""), float(row["close"])))
            return {ticker: [value for _, value in sorted(values)] for ticker, values in rows_by_ticker.items()}
        for row in reader:
            for ticker in AURA_TICKERS:
                value = row.get(ticker)
                if value not in (None, ""):
                    prices[ticker].append(float(value))
    return prices


def gldm_role_inputs_from_csv(path: str, window: int = 60) -> AuraResult:
    """Generate GLDM Role inputs from a manual A.U.R.A. price CSV."""

    result = compute_gldm_role_proxies(load_aura_prices_csv(path), window=window)
    return AuraResult(
        result.role_inputs,
        result.proxies,
        result.reasons,
        result.warnings,
        result.data_date,
        f"manual A.U.R.A. CSV: {path}",
        result.used_aura,
        result.correlations,
        result.dominant_anchor,
        result.dominant_correlation,
        result.gri_score,
        result.gri_interpretation,
    )


def latest_gldm_role_inputs(period: str = "2y", window: int = 60) -> AuraResult:
    """Fetch A.U.R.A. prices and return latest GLDM Role proxy inputs."""

    try:
        price_data = fetch_aura_price_data(period=period)
        result = compute_gldm_role_proxies(price_data, window=window)
        if result.used_aura:
            return result
        return result
    except Exception as exc:  # noqa: BLE001 - CLI must keep running on provider failures.
        warning = f"warning: failed to fetch A.U.R.A. yfinance data ({exc}); neutral GLDM Role proxy fallback applied."
        return _neutral_result([warning])
