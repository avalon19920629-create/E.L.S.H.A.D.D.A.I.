"""G.A.I.A. adapter for DBC commodity-regime Role proxies.

G.A.I.A. (Global Asset Intelligence for Inflationary Abundance) audits DBC as
El Shaddai's commodity-regime anchor.  Actual operations may hold SBI-available
commodity funds such as eMAXIS commodity products, but the audit target remains
DBC / Commodity Regime so the role check stays product-independent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from math import log, sqrt
from typing import Dict, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS

GAIA_TICKERS: Mapping[str, str] = {
    "DBC": "Commodity-regime audit anchor",
    "USO": "Oil / energy sub-sector",
    "UNG": "Natural gas / energy sub-sector",
    "GLD": "Gold / metals sub-sector",
    "CPER": "Copper / industrial metals sub-sector",
    "DBA": "Agriculture sub-sector",
    "SPY": "Growth / equities",
    "UUP": "US dollar headwind",
    "TIP": "Inflation-protected Treasury line",
    "GLDM": "Gold inflation-defense line",
    "TLT": "Duration / winter air mass",
    "BNDX": "Global bond / winter air mass",
}

DBC_GAIA_COMPONENTS: Sequence[str] = (
    "commodity_trend",
    "inflation_firepower",
    "resource_shock_response",
    "summer_regime_strength",
    "energy_leadership",
    "metals_leadership",
    "agriculture_leadership",
    "tip_gldm_alignment",
    "deflation_drag",
    "dollar_headwind",
    "growth_collapse",
    "commodity_noise",
)

_COLUMN_ALIASES: Mapping[str, str] = {
    "dbc_close": "DBC", "dbc": "DBC",
    "uso_close": "USO", "uso": "USO",
    "ung_close": "UNG", "ung": "UNG",
    "gld_close": "GLD", "gld": "GLD",
    "cper_close": "CPER", "cper": "CPER",
    "dba_close": "DBA", "dba": "DBA",
    "spy_close": "SPY", "spy": "SPY",
    "uup_close": "UUP", "uup": "UUP",
    "tip_close": "TIP", "tip": "TIP",
    "gldm_close": "GLDM", "gldm": "GLDM",
    "tlt_close": "TLT", "tlt": "TLT",
    "bndx_close": "BNDX", "bndx": "BNDX",
}


@dataclass(frozen=True)
class GaiaResult:
    """Result of generating DBC Role inputs from G.A.I.A."""

    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_gaia: bool
    raw_metrics: Mapping[str, float]
    applied_caps: List[str]
    commodity_regime_interpretation: str


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
    denominator = sqrt(sum(value * value for value in left_diffs)) * sqrt(sum(value * value for value in right_diffs))
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(left_diffs, right_diffs)) / denominator


def _pct_change(prices: Sequence[float]) -> float:
    values = [float(value) for value in prices if value is not None and float(value) > 0]
    if len(values) < 2 or values[0] == 0:
        return 0.0
    return values[-1] / values[0] - 1.0


def _latest_date(price_data: Mapping[str, Sequence[float] | Sequence[str]]) -> str:
    dates = price_data.get("__dates__")
    if dates:
        return str(list(dates)[-1])
    return str(date.today())


def _neutral_result(warnings: List[str], source: str = "G.A.I.A. yfinance") -> GaiaResult:
    neutral = {name: float(DEFAULT_ROLE_INPUTS["DBC"].get(name, 0.0)) for name in DBC_GAIA_COMPONENTS}
    return GaiaResult(
        role_inputs={"DBC": neutral},
        proxies=neutral,
        reasons={name: "neutral fallback" for name in neutral},
        warnings=warnings,
        data_date="unknown",
        source=source,
        used_gaia=False,
        raw_metrics={},
        applied_caps=[],
        commodity_regime_interpretation="Gaia Dormant - Commodity role is neutral or inactive.",
    )


def fetch_gaia_price_data(period: str = "2y", tickers: Sequence[str] | None = None) -> Dict[str, List[float] | List[str]]:
    """Fetch G.A.I.A. prices with yfinance; failures are handled by callers."""

    import yfinance as yf  # type: ignore[import-not-found]

    selected = list(tickers or GAIA_TICKERS.keys())
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
        except Exception:  # noqa: BLE001
            continue
    return prices


def compute_dbc_role_proxies(price_data: Mapping[str, Sequence[float] | Sequence[str]], window: int = 60) -> GaiaResult:
    """Convert commodity market proxies into direction-adjusted -2..+2 DBC Role inputs."""

    numeric = {ticker: [float(value) for value in price_data.get(ticker, [])] for ticker in GAIA_TICKERS}
    required = ["DBC", "USO", "UNG", "GLD", "CPER", "DBA", "SPY", "UUP", "TIP", "GLDM"]
    missing = [ticker for ticker in required if len(numeric.get(ticker, [])) < 3]
    if missing:
        return _neutral_result([f"warning: G.A.I.A. data insufficient for {', '.join(missing)}; neutral DBC Role proxy fallback applied."])

    dbc = numeric["DBC"]
    uso = numeric["USO"]
    ung = numeric["UNG"]
    gld = numeric["GLD"]
    cper = numeric["CPER"]
    dba = numeric["DBA"]
    spy = numeric["SPY"]
    uup = numeric["UUP"]
    tip = numeric["TIP"]
    gldm = numeric["GLDM"]
    tlt = numeric.get("TLT", [])
    bndx = numeric.get("BNDX", [])

    dbc_trend = _pct_change(dbc)
    uso_trend = _pct_change(uso)
    ung_trend = _pct_change(ung)
    gld_trend = _pct_change(gld)
    cper_trend = _pct_change(cper)
    dba_trend = _pct_change(dba)
    spy_trend = _pct_change(spy)
    uup_trend = _pct_change(uup)
    tip_trend = _pct_change(tip)
    gldm_trend = _pct_change(gldm)
    tlt_trend = _pct_change(tlt) if tlt else 0.0
    bndx_trend = _pct_change(bndx) if bndx else 0.0

    aligned_tip = min(len(_returns(dbc)), len(_returns(tip)), window)
    dbc_tip_corr = _correlation(_returns(dbc)[-aligned_tip:], _returns(tip)[-aligned_tip:]) if aligned_tip >= 2 else None
    aligned_gldm = min(len(_returns(dbc)), len(_returns(gldm)), window)
    dbc_gldm_corr = _correlation(_returns(dbc)[-aligned_gldm:], _returns(gldm)[-aligned_gldm:]) if aligned_gldm >= 2 else None
    if dbc_tip_corr is None or dbc_gldm_corr is None:
        return _neutral_result(["warning: G.A.I.A. could not compute TIP/GLDM alignment correlations; neutral DBC Role proxy fallback applied."])

    energy_trend = (uso_trend + ung_trend) / 2.0
    metals_trend = (gld_trend + cper_trend) / 2.0
    sub_breadth = sum(1 for trend in (uso_trend, ung_trend, gld_trend, cper_trend, dba_trend) if trend > 0.01) / 5.0
    sub_avg = (uso_trend + ung_trend + gld_trend + cper_trend + dba_trend) / 5.0
    winter_trend = max(tlt_trend, bndx_trend)

    proxies = {
        "commodity_trend": round(_clamp(dbc_trend * 10.0), 3),
        "inflation_firepower": round(_clamp(dbc_trend * 8.0 + max(0.0, tip_trend) * 4.0 + max(0.0, gldm_trend) * 4.0 + (dbc_tip_corr + dbc_gldm_corr) * 0.35), 3),
        "resource_shock_response": round(_clamp(sub_avg * 10.0 + (sub_breadth - 0.4) * 2.0), 3),
        "summer_regime_strength": round(_clamp((dbc_trend - spy_trend) * 8.0 + (dbc_trend - winter_trend) * 6.0 + sub_avg * 4.0), 3),
        "energy_leadership": round(_clamp(energy_trend * 12.0), 3),
        "metals_leadership": round(_clamp(metals_trend * 12.0), 3),
        "agriculture_leadership": round(_clamp(dba_trend * 12.0), 3),
        "tip_gldm_alignment": round(_clamp((dbc_tip_corr + dbc_gldm_corr) * 0.75 + (tip_trend + gldm_trend) * 4.0), 3),
        "deflation_drag": round(_clamp(-dbc_trend * 8.0 + max(0.0, tip_trend) * 4.0 + max(0.0, winter_trend) * 8.0) * -1.0 if dbc_trend < 0 and (tip_trend > 0 or winter_trend > 0) else _clamp(dbc_trend * 4.0 - max(0.0, winter_trend) * 4.0), 3),
        "dollar_headwind": round(_clamp(-uup_trend * 20.0), 3),
        "growth_collapse": round(_clamp((spy_trend + dbc_trend) * 8.0) if spy_trend < -0.08 and dbc_trend < 0 else _clamp(max(dbc_trend, spy_trend) * 3.0), 3),
        "commodity_noise": round(_clamp(-2.0 if dbc_trend > 0.03 and sub_breadth <= 0.2 else (sub_breadth - 0.4) * 2.5), 3),
    }

    applied_caps: List[str] = []
    if proxies["dollar_headwind"] <= -1.0:
        applied_caps.append("dollar_headwind severe => Role Score cap 60")
    if proxies["dollar_headwind"] <= -1.0 and proxies["deflation_drag"] <= -1.0:
        applied_caps.append("dollar_headwind severe + deflation_drag severe => Role Score cap 45")
    if proxies["growth_collapse"] <= -1.0 and proxies["commodity_noise"] <= -1.0:
        applied_caps.append("growth_collapse severe + commodity_noise severe => Role Score cap 40")
    if proxies["dollar_headwind"] <= -1.0 and proxies["deflation_drag"] <= -1.0 and proxies["growth_collapse"] <= -1.0:
        applied_caps.append("dollar_headwind severe + deflation_drag severe + growth_collapse severe => Role Score cap 30")

    penalty_choked = proxies["dollar_headwind"] <= -1.0 or proxies["deflation_drag"] <= -1.0 or proxies["growth_collapse"] <= -1.0
    core_avg = _mean([proxies[name] for name in ("commodity_trend", "inflation_firepower", "resource_shock_response", "summer_regime_strength")])
    if any("cap 30" in cap for cap in applied_caps) or core_avg <= -1.0:
        interpretation = "Gaia Extinguished - Commodity regime is structurally impaired."
    elif penalty_choked:
        interpretation = "Gaia Choked - Dollar/deflation/growth collapse suppresses commodity role."
    elif core_avg >= 1.0 and sub_breadth >= 0.6:
        interpretation = "Gaia Ignited - Commodity fire is active; Summer regime is dominant."
    elif core_avg > 0.2:
        interpretation = "Gaia Smoldering - Commodity role evidence exists but is not yet dominant."
    else:
        interpretation = "Gaia Dormant - Commodity role is neutral or inactive."

    reasons = {
        "commodity_trend": f"DBC trend {dbc_trend:+.3f}; rising DBC supports the commodity-regime anchor.",
        "inflation_firepower": f"DBC {dbc_trend:+.3f}, TIP {tip_trend:+.3f}, GLDM {gldm_trend:+.3f}, correlations TIP {dbc_tip_corr:+.3f}/GLDM {dbc_gldm_corr:+.3f}; measures Summer attack power.",
        "resource_shock_response": f"Sub-sector average {sub_avg:+.3f}, breadth {sub_breadth:.2f}; simultaneous energy/metals/agriculture strength signals resource shock response.",
        "summer_regime_strength": f"DBC/SPY relative {dbc_trend - spy_trend:+.3f}, DBC/Winter relative {dbc_trend - winter_trend:+.3f}; checks commodity-led Summer air mass.",
        "energy_leadership": f"USO trend {uso_trend:+.3f}, UNG trend {ung_trend:+.3f}; energy leadership fuels the role.",
        "metals_leadership": f"GLD trend {gld_trend:+.3f}, CPER trend {cper_trend:+.3f}; precious/industrial metals breadth supports the role.",
        "agriculture_leadership": f"DBA trend {dba_trend:+.3f}; agriculture strength broadens commodity inflation.",
        "tip_gldm_alignment": f"DBC/TIP correlation {dbc_tip_corr:+.3f}, DBC/GLDM correlation {dbc_gldm_corr:+.3f}, TIP {tip_trend:+.3f}, GLDM {gldm_trend:+.3f}; checks inflation-defense-line alignment.",
        "deflation_drag": f"DBC {dbc_trend:+.3f}, TIP {tip_trend:+.3f}, TLT/BNDX winter trend {winter_trend:+.3f}; weak DBC with stronger inflation bonds/duration implies Winter drag.",
        "dollar_headwind": f"UUP trend {uup_trend:+.3f}; stronger dollar is direction-adjusted negative for dollar-priced commodities.",
        "growth_collapse": f"SPY trend {spy_trend:+.3f}, DBC trend {dbc_trend:+.3f}; simultaneous decline implies commodity demand destruction.",
        "commodity_noise": f"DBC trend {dbc_trend:+.3f}, sub-sector breadth {sub_breadth:.2f}; isolated DBC movement without breadth is treated as noise.",
    }
    raw_metrics = {
        "dbc_trend": round(dbc_trend, 6), "uso_trend": round(uso_trend, 6), "ung_trend": round(ung_trend, 6),
        "gld_trend": round(gld_trend, 6), "cper_trend": round(cper_trend, 6), "dba_trend": round(dba_trend, 6),
        "spy_trend": round(spy_trend, 6), "uup_trend": round(uup_trend, 6), "tip_trend": round(tip_trend, 6),
        "gldm_trend": round(gldm_trend, 6), "tlt_trend": round(tlt_trend, 6), "bndx_trend": round(bndx_trend, 6),
        "subsector_breadth": round(sub_breadth, 6), "dbc_tip_corr": round(dbc_tip_corr, 6), "dbc_gldm_corr": round(dbc_gldm_corr, 6),
    }
    return GaiaResult({"DBC": proxies}, proxies, reasons, [], _latest_date(price_data), "G.A.I.A. market proxies", True, raw_metrics, applied_caps, interpretation)


def load_gaia_prices_csv(path: str) -> Dict[str, List[float] | List[str]]:
    """Load manual G.A.I.A. prices from wide CSV or long ``date,ticker,close`` CSV."""

    prices: Dict[str, List[float] | List[str]] = {ticker: [] for ticker in GAIA_TICKERS}
    prices["__dates__"] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        lower_fields = {name.lower(): name for name in fieldnames}
        if {"date", "ticker", "close"}.issubset(set(lower_fields)):
            rows_by_ticker: Dict[str, List[tuple[str, float]]] = {ticker: [] for ticker in GAIA_TICKERS}
            for row in reader:
                ticker = row[lower_fields["ticker"]].strip().upper()
                if ticker in rows_by_ticker and row.get(lower_fields["close"]) not in (None, ""):
                    rows_by_ticker[ticker].append((row.get(lower_fields["date"], ""), float(row[lower_fields["close"]])))
            for ticker, values in rows_by_ticker.items():
                ordered = sorted(values)
                prices[ticker] = [value for _, value in ordered]
            prices["__dates__"] = sorted({row_date for values in rows_by_ticker.values() for row_date, _ in values})
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


def dbc_role_inputs_from_csv(path: str, window: int = 60) -> GaiaResult:
    """Generate DBC Role inputs from a manual G.A.I.A. price CSV."""

    result = compute_dbc_role_proxies(load_gaia_prices_csv(path), window=window)
    return GaiaResult(result.role_inputs, result.proxies, result.reasons, result.warnings, result.data_date, f"manual G.A.I.A. CSV: {path}", result.used_gaia, result.raw_metrics, result.applied_caps, result.commodity_regime_interpretation)


def latest_dbc_role_inputs(period: str = "2y", window: int = 60) -> GaiaResult:
    """Fetch G.A.I.A. prices and return latest DBC Role proxy inputs."""

    try:
        return compute_dbc_role_proxies(fetch_gaia_price_data(period=period), window=window)
    except Exception as exc:  # noqa: BLE001
        warning = f"warning: failed to fetch G.A.I.A. yfinance data ({exc}); neutral DBC Role proxy fallback applied."
        return _neutral_result([warning])
