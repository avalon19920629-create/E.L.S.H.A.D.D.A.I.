"""A.T.L.A.S. adapter for generating BNDX Role proxies.

A.T.L.A.S. = Advanced Tracker for Liquidity And Sovereign-health.  The
adapter evaluates whether BNDX still functions as the L.U.M.U.S.-8 "Winter
Shield": a currency-hedged global sovereign-bond stability layer.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from math import log, sqrt
from typing import Dict, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS

BNDX_ATLAS_COMPONENTS: Sequence[str] = (
    "sovereign_trust",
    "currency_order",
    "liquidity_flow",
    "diversification_integrity",
    "fx_hedge_value",
    "global_bond_trend",
    "sovereign_stability",
    "hedge_cost_pressure",
    "global_credit_stress",
    "sovereign_stress",
)

ATLAS_TICKERS: Mapping[str, str] = {
    "BNDX": "Vanguard Total International Bond ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "HYG": "iShares iBoxx High Yield Corporate Bond ETF",
    "UUP": "Invesco DB US Dollar Index Bullish Fund",
    "BWX": "SPDR Bloomberg International Treasury Bond ETF",
}


@dataclass(frozen=True)
class AtlasResult:
    """Result of attempting to generate BNDX Role inputs from A.T.L.A.S."""

    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_atlas: bool
    raw_metrics: Mapping[str, float]
    failed_pillars: List[str]
    structural_status: str
    winter_shield_interpretation: str
    applied_caps: List[str]


def _clamp(value: float, low: float = -2.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _to_float(value: object) -> Optional[float]:
    if value in {"", ".", "nan", "NaN", "None", None}:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _pct_change(prices: Sequence[float]) -> float:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    if len(values) < 2 or values[0] == 0:
        return 0.0
    return values[-1] / values[0] - 1.0


def _returns(prices: Sequence[float]) -> List[float]:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    return [log(cur / prev) for prev, cur in zip(values[:-1], values[1:])]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _volatility(prices: Sequence[float], window: int = 60) -> float:
    rets = _returns(prices)[-window:]
    if len(rets) < 2:
        return 0.0
    avg = _mean(rets)
    return sqrt(sum((value - avg) ** 2 for value in rets) / (len(rets) - 1)) * sqrt(252.0)


def _correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = sqrt(sum((value - left_mean) ** 2 for value in left)) * sqrt(sum((value - right_mean) ** 2 for value in right))
    if denominator == 0:
        return None
    return numerator / denominator


def _latest_date(price_data: Mapping[str, Sequence[float] | Sequence[str]]) -> str:
    dates = price_data.get("__dates__")
    if dates:
        return str(list(dates)[-1])
    return str(date.today())


def _neutral_result(warnings: List[str], source: str = "A.T.L.A.S. yfinance") -> AtlasResult:
    neutral = {name: float(DEFAULT_ROLE_INPUTS["BNDX"].get(name, 0.0)) for name in BNDX_ATLAS_COMPONENTS}
    return AtlasResult(
        role_inputs={"BNDX": neutral},
        proxies=neutral,
        reasons={name: "neutral fallback" for name in neutral},
        warnings=warnings,
        data_date="unknown",
        source=source,
        used_atlas=False,
        raw_metrics={},
        failed_pillars=[],
        structural_status="Atlas Standing",
        winter_shield_interpretation="Winter blanket remains intact.",
        applied_caps=[],
    )


def atlas_structure_from_pillars(pillar_scores: Mapping[str, float]) -> tuple[str, str, List[str], List[str]]:
    """Classify Atlas geometry from 0..100 pillar scores."""

    pillar_names = ["sovereign_trust", "currency_order", "liquidity_flow", "diversification_integrity"]
    failed = [name for name in pillar_names if pillar_scores.get(name, 50.0) <= 25.0]
    failed_set = set(failed)
    caps: List[str] = []
    if len(failed) >= 4:
        return "Atlas Fallen", "Systemic breakdown. The world supported by Atlas has collapsed.", failed, ["Atlas four-pillar failure cap: Role Score capped at 0"]
    if len(failed) == 3:
        return "Atlas Fallen", "Global sovereign-bond structure is no longer functioning properly.", failed, ["Atlas three-pillar failure cap: Role Score capped at 20"]
    if len(failed) == 2:
        adjacent_pairs = [
            {"sovereign_trust", "currency_order"},
            {"currency_order", "liquidity_flow"},
            {"liquidity_flow", "diversification_integrity"},
            {"diversification_integrity", "sovereign_trust"},
        ]
        if any(failed_set == pair for pair in adjacent_pairs):
            caps.append("Atlas adjacent-pillar failure cap: Role Score capped at 35")
            return "Atlas Cannot Hold", "Adjacent pillar collapse detected. Blanket integrity compromised.", failed, caps
        caps.append("Atlas diagonal-pillar failure cap: Role Score capped at 50")
        return "Atlas Kneeling", "Structural stress detected. Winter protection reduced.", failed, caps
    if len(failed) == 1:
        return "Atlas Strained", "One pillar weakened. Monitor carefully.", failed, caps
    return "Atlas Standing", "Winter blanket remains intact.", failed, caps


def compute_bndx_role_proxies(price_data: Mapping[str, Sequence[float] | Sequence[str]], window: int = 60) -> AtlasResult:
    """Convert market proxies into direction-adjusted -2..+2 BNDX Role inputs."""

    numeric = {ticker: [float(value) for value in price_data.get(ticker, [])] for ticker in ATLAS_TICKERS}
    required = ["BNDX", "TLT", "HYG", "UUP"]
    missing = [ticker for ticker in required if len(numeric.get(ticker, [])) < 3]
    if missing:
        return _neutral_result([f"warning: A.T.L.A.S. data insufficient for {', '.join(missing)}; neutral BNDX Role proxy fallback applied."])

    bndx = numeric["BNDX"]
    tlt = numeric["TLT"]
    hyg = numeric["HYG"]
    uup = numeric["UUP"]
    bnd = numeric.get("BND", [])
    bwx = numeric.get("BWX", [])

    bndx_trend = _pct_change(bndx)
    tlt_trend = _pct_change(tlt)
    hyg_trend = _pct_change(hyg)
    uup_trend = _pct_change(uup)
    bnd_trend = _pct_change(bnd) if bnd else 0.0
    bwx_trend = _pct_change(bwx) if bwx else bndx_trend
    bndx_vol = _volatility(bndx, window)
    tlt_vol = _volatility(tlt, window)

    aligned = min(len(_returns(bndx)), len(_returns(tlt)), window)
    corr_bndx_tlt = _correlation(_returns(bndx)[-aligned:], _returns(tlt)[-aligned:]) if aligned >= 2 else 0.5
    corr_bndx_tlt = 0.5 if corr_bndx_tlt is None else corr_bndx_tlt

    sovereign_proxy = _clamp((bndx_trend * 10.0) + (bwx_trend * 4.0) + (hyg_trend * 3.0))
    currency_proxy = _clamp((-uup_trend * 10.0) + (0.5 if abs(uup_trend) < 0.04 else 0.0))
    liquidity_proxy = _clamp((hyg_trend * 8.0) - (bndx_vol * 8.0))
    diversification_proxy = _clamp(((1.0 - corr_bndx_tlt) * 2.0 - 0.5) + ((bndx_trend - tlt_trend) * 4.0))
    fx_hedge_proxy = _clamp((-abs(uup_trend) * 8.0) + 0.75)
    global_bond_trend_proxy = _clamp((bndx_trend * 12.0) + (bnd_trend * 4.0))
    sovereign_stability_proxy = _clamp(1.0 - bndx_vol * 10.0 + min(hyg_trend * 4.0, 0.75))
    hedge_cost_proxy = _clamp(1.0 - abs(uup_trend) * 12.0)
    credit_stress_proxy = _clamp(hyg_trend * 10.0 - bndx_vol * 5.0)
    sovereign_stress_proxy = _clamp((bndx_trend * 8.0) - bndx_vol * 8.0)

    proxies = {
        "sovereign_trust": round(sovereign_proxy, 3),
        "currency_order": round(currency_proxy, 3),
        "liquidity_flow": round(liquidity_proxy, 3),
        "diversification_integrity": round(diversification_proxy, 3),
        "fx_hedge_value": round(fx_hedge_proxy, 3),
        "global_bond_trend": round(global_bond_trend_proxy, 3),
        "sovereign_stability": round(sovereign_stability_proxy, 3),
        "hedge_cost_pressure": round(hedge_cost_proxy, 3),
        "global_credit_stress": round(credit_stress_proxy, 3),
        "sovereign_stress": round(sovereign_stress_proxy, 3),
    }
    raw_metrics = {
        "bndx_trend": bndx_trend,
        "tlt_trend": tlt_trend,
        "hyg_trend": hyg_trend,
        "uup_trend": uup_trend,
        "bndx_volatility": bndx_vol,
        "tlt_volatility": tlt_vol,
        "bndx_tlt_correlation": corr_bndx_tlt,
    }
    pillar_scores = {name: 50.0 + proxies[name] * 25.0 for name in ("sovereign_trust", "currency_order", "liquidity_flow", "diversification_integrity")}
    status, interpretation, failed_pillars, caps = atlas_structure_from_pillars(pillar_scores)
    reasons = {
        "sovereign_trust": f"BNDX trend {bndx_trend:+.2%}, BWX trend {bwx_trend:+.2%}, and HYG trend {hyg_trend:+.2%} proxy sovereign confidence.",
        "currency_order": f"UUP trend {uup_trend:+.2%}; a stable/weaker dollar supports currency-hedged order.",
        "liquidity_flow": f"HYG trend {hyg_trend:+.2%} and BNDX volatility {bndx_vol:.2%} proxy bond-market plumbing.",
        "diversification_integrity": f"BNDX/TLT correlation {corr_bndx_tlt:+.2f}; lower correlation preserves global diversification.",
        "fx_hedge_value": f"Absolute UUP move {abs(uup_trend):.2%}; smaller FX disruption supports hedge usefulness.",
        "global_bond_trend": f"BNDX trend {bndx_trend:+.2%} and BND trend {bnd_trend:+.2%} proxy global bond trend.",
        "sovereign_stability": f"BNDX volatility {bndx_vol:.2%} and HYG trend {hyg_trend:+.2%} proxy sovereign-bond stability.",
        "hedge_cost_pressure": f"Absolute UUP move {abs(uup_trend):.2%}; larger currency pressure impairs hedge-cost backdrop.",
        "global_credit_stress": f"HYG trend {hyg_trend:+.2%} and BNDX volatility {bndx_vol:.2%} proxy global credit stress.",
        "sovereign_stress": f"BNDX trend {bndx_trend:+.2%} and volatility {bndx_vol:.2%} proxy sovereign stress.",
    }
    return AtlasResult({"BNDX": proxies}, proxies, reasons, [], _latest_date(price_data), "A.T.L.A.S. yfinance", True, raw_metrics, failed_pillars, status, interpretation, caps)


def fetch_atlas_price_data(period: str = "2y", tickers: Sequence[str] | None = None) -> Dict[str, List[float] | List[str]]:
    """Fetch A.T.L.A.S. prices with yfinance."""

    import yfinance as yf  # type: ignore[import-not-found]

    selected = list(tickers or ATLAS_TICKERS.keys())
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
        except Exception:
            continue
    return prices


def load_atlas_csv(path: str) -> Dict[str, List[float] | List[str]] | List[Dict[str, float | str | None]]:
    """Load manual A.T.L.A.S. CSV.

    Supported formats:
    * Direct proxy columns: date plus any BNDX_ATLAS_COMPONENTS values in -2..+2.
    * Long prices: date,ticker,close.
    * Wide prices: date plus ticker columns such as BNDX,TLT,HYG,UUP,BND,BWX.
    """

    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
    if fields & set(BNDX_ATLAS_COMPONENTS):
        proxy_rows: List[Dict[str, float | str | None]] = []
        for raw in rows:
            row: Dict[str, float | str | None] = {"date": raw.get("date", "unknown")}
            for name in BNDX_ATLAS_COMPONENTS:
                row[name] = _to_float(raw.get(name, ""))
            proxy_rows.append(row)
        return proxy_rows
    prices: Dict[str, List[float] | List[str]] = {"__dates__": []}
    if {"date", "ticker", "close"}.issubset(fields):
        dates_seen: List[str] = []
        for raw in rows:
            ticker = str(raw.get("ticker", "")).strip().upper()
            value = _to_float(raw.get("close"))
            if ticker and value is not None:
                prices.setdefault(ticker, []).append(value)  # type: ignore[union-attr]
                row_date = str(raw.get("date", "unknown"))
                if row_date not in dates_seen:
                    dates_seen.append(row_date)
        prices["__dates__"] = dates_seen
        return prices
    tickers = fields & set(ATLAS_TICKERS)
    for raw in rows:
        prices["__dates__"].append(str(raw.get("date", "unknown")))  # type: ignore[union-attr]
        for ticker in tickers:
            value = _to_float(raw.get(ticker))
            if value is not None:
                prices.setdefault(ticker, []).append(value)  # type: ignore[union-attr]
    return prices


def compute_bndx_role_proxies_from_direct_rows(rows: Sequence[Mapping[str, float | str | None]], source: str = "manual A.T.L.A.S. CSV") -> AtlasResult:
    complete = [row for row in rows if any(_to_float(row.get(name)) is not None for name in BNDX_ATLAS_COMPONENTS)]
    if not complete:
        return _neutral_result(["warning: A.T.L.A.S. CSV had no usable proxy rows; neutral BNDX Role proxy fallback applied."], source)
    latest = complete[-1]
    proxies = {name: round(_clamp(float(_to_float(latest.get(name)) or 0.0)), 3) for name in BNDX_ATLAS_COMPONENTS}
    pillar_scores = {name: 50.0 + proxies[name] * 25.0 for name in ("sovereign_trust", "currency_order", "liquidity_flow", "diversification_integrity")}
    status, interpretation, failed_pillars, caps = atlas_structure_from_pillars(pillar_scores)
    reasons = {name: f"manual A.T.L.A.S. proxy {proxies[name]:+.3f}" for name in proxies}
    raw_metrics = {f"pillar_score_{name}": score for name, score in pillar_scores.items()}
    return AtlasResult({"BNDX": proxies}, proxies, reasons, [], str(latest.get("date", "unknown")), source, True, raw_metrics, failed_pillars, status, interpretation, caps)


def bndx_role_inputs_from_csv(path: str) -> AtlasResult:
    """Generate BNDX Role inputs from a manual A.T.L.A.S. CSV."""

    loaded = load_atlas_csv(path)
    source = f"manual A.T.L.A.S. CSV: {path}"
    if isinstance(loaded, list):
        result = compute_bndx_role_proxies_from_direct_rows(loaded, source)
    else:
        result = compute_bndx_role_proxies(loaded)
    return AtlasResult(result.role_inputs, result.proxies, result.reasons, result.warnings, result.data_date, source, result.used_atlas, result.raw_metrics, result.failed_pillars, result.structural_status, result.winter_shield_interpretation, result.applied_caps)


def latest_bndx_role_inputs() -> AtlasResult:
    """Fetch market data and return latest BNDX Role proxy inputs.

    Any provider failure returns neutral BNDX inputs and warnings so reports are
    still generated normally.
    """

    try:
        result = compute_bndx_role_proxies(fetch_atlas_price_data())
        return result
    except Exception as exc:  # noqa: BLE001 - CLI must not fail on data-provider issues.
        neutral = {name: float(DEFAULT_ROLE_INPUTS["BNDX"].get(name, 0.0)) for name in BNDX_ATLAS_COMPONENTS}
        warning = f"warning: failed to fetch A.T.L.A.S. market data ({exc}); neutral BNDX Role proxy fallback applied."
        return AtlasResult({"BNDX": neutral}, neutral, {name: "neutral fallback" for name in neutral}, [warning], "unknown", "A.T.L.A.S. yfinance", False, {}, [], "Atlas Standing", "Winter blanket remains intact.", [])
