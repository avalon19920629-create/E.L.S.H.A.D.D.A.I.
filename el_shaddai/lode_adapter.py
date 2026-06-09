"""L.O.D.E. adapter for generating TLT Role proxies from FRED data.

L.O.D.E. = Leading Observatory of Debt & Economic-health.  The adapter keeps
all transformations transparent: raw FRED series are converted into
TLT-direction-adjusted -2..+2 Role proxies, where +2 is favorable for TLT's
role as recession cushion / long-duration Treasury exposure / equity hedge.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS
from .fred_data import (
    DEFAULT_FRED_PAUSE, DEFAULT_FRED_RETRY_COUNT, DEFAULT_FRED_TIMEOUT,
    fetch_fred_series_rows, load_fred_cache, save_fred_cache,
)

FRED_SERIES: Mapping[str, str] = {
    "T10Y2Y": "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity",
    "DFII10": "10-Year Treasury Inflation-Indexed Security, Constant Maturity",
    "GFDEGDQ188S": "Federal Debt: Total Public Debt as Percent of GDP",
    "A091RC1Q027SBEA": "Federal government current expenditures: Interest payments",
    "W006RC1Q027SBEA": "Federal government current receipts: Tax receipts",
    "FDHBFIN": "Federal Debt Held by Foreign and International Investors",
    "GFDEBTN": "Federal Debt: Total Public Debt",
}

TLT_LODE_COMPONENTS: Sequence[str] = (
    "recession_pressure",
    "us_10y_yield",
    "us_30y_yield",
    "yield_curve",
    "real_rate",
    "debt_sustainability",
    "interest_burden",
    "foreign_demand",
)


@dataclass(frozen=True)
class LodeResult:
    """Result of attempting to generate TLT Role inputs from L.O.D.E."""

    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_lode: bool
    degraded: bool = False
    stale_days: Optional[int] = None


def _to_float(value: str) -> Optional[float]:
    if value in {"", ".", "nan", "NaN", "None"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clamp(value: float, low: float = -2.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _scale(value: float, center: float, half_width: float) -> float:
    if half_width == 0:
        return 0.0
    return _clamp((value - center) / half_width * 2.0)


def _range_position(values: Sequence[float]) -> float:
    clean = [float(value) for value in values if value is not None]
    if len(clean) < 2:
        return 0.5
    low = min(clean)
    high = max(clean)
    if high == low:
        return 0.5
    return (clean[-1] - low) / (high - low)


def _trend(values: Sequence[float], lookback: int = 252) -> float:
    clean = [float(value) for value in values if value is not None]
    if len(clean) < 2:
        return 0.0
    previous = clean[-min(lookback, len(clean))]
    return clean[-1] - previous


def fetch_lode_fred_data(
    start: str | date | None = None, end: str | date | None = None, *,
    retry_count: int = DEFAULT_FRED_RETRY_COUNT, pause: float = DEFAULT_FRED_PAUSE,
    timeout: float = DEFAULT_FRED_TIMEOUT, provider: str = "pandas_datareader",
) -> List[Dict[str, float | str | None]]:
    """Fetch required L.O.D.E. series through the shared FRED foundation."""
    end_date = end or date.today()
    start_date = start or (date.today() - timedelta(days=365 * 20))
    return fetch_fred_series_rows(list(FRED_SERIES), start_date, end_date, retry_count=retry_count, pause=pause, timeout=timeout, provider=provider)


def compute_lode_components(df: Iterable[Mapping[str, float | str | None]]) -> List[Dict[str, float | str]]:
    """Compute normalized L.O.D.E. components from raw FRED rows."""

    components: List[Dict[str, float | str]] = []
    for row in df:
        try:
            interest_payments = float(row["A091RC1Q027SBEA"])
            tax_receipts = float(row["W006RC1Q027SBEA"])
            foreign_holdings = float(row["FDHBFIN"])
            total_debt = float(row["GFDEBTN"])
            if tax_receipts == 0 or total_debt == 0:
                continue
            components.append({
                "date": str(row.get("date", "unknown")),
                "yield_curve_spread": float(row["T10Y2Y"]),
                "real_rate": float(row["DFII10"]),
                "debt_gdp": float(row["GFDEGDQ188S"]),
                "interest_to_tax": interest_payments / tax_receipts * 100.0,
                # FDHBFIN is in billions while GFDEBTN is in millions.
                "foreign_ratio": foreign_holdings * 1000.0 / total_debt * 100.0,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return components


def compute_tlt_role_proxies(df: Iterable[Mapping[str, float | str | None]]) -> LodeResult:
    """Convert L.O.D.E. data into TLT direction-adjusted Role proxies.

    The returned proxy values are not raw macro values.  They are normalized to
    -2..+2 in TLT Role direction: +2 favors TLT's recession-cushion / Treasury
    hedge role, while -2 impairs it.
    """

    components = compute_lode_components(df)
    if not components:
        warning = "warning: L.O.D.E. data had no complete rows; neutral TLT Role proxy fallback applied."
        neutral = {name: 0.0 for name in TLT_LODE_COMPONENTS}
        return LodeResult({"TLT": neutral}, neutral, {}, [warning], "unknown", "L.O.D.E. FRED", False)

    latest = components[-1]
    spreads = [float(row["yield_curve_spread"]) for row in components]
    real_rates = [float(row["real_rate"]) for row in components]
    debt_gdp = [float(row["debt_gdp"]) for row in components]
    interest_to_tax = [float(row["interest_to_tax"]) for row in components]
    foreign_ratio = [float(row["foreign_ratio"]) for row in components]

    latest_spread = float(latest["yield_curve_spread"])
    latest_real_rate = float(latest["real_rate"])
    latest_debt_gdp = float(latest["debt_gdp"])
    latest_interest_to_tax = float(latest["interest_to_tax"])
    latest_foreign_ratio = float(latest["foreign_ratio"])

    debt_position = _range_position(debt_gdp)
    interest_position = _range_position(interest_to_tax)
    foreign_position = _range_position(foreign_ratio)
    foreign_trend = _trend(foreign_ratio)
    real_position = _range_position(real_rates)

    yield_curve_proxy = _clamp(-latest_spread / 0.75)
    recession_proxy = _clamp((-latest_spread / 0.75) + (0.5 if latest_spread < 0 else -0.25))
    # Higher real rates are a price headwind but can create future easing room.
    # Middle-to-high range is favorable; extreme highs are capped by debt/fiscal proxies.
    real_rate_proxy = _clamp((real_position - 0.35) * 4.0)
    # We only fetch DFII10 for rates in v1.1. These two proxies are therefore
    # transparent approximations of duration/rate-pressure backdrop, not raw
    # nominal 10Y/30Y yields.
    us_10y_proxy = _clamp(real_rate_proxy * 0.75)
    us_30y_proxy = _clamp(real_rate_proxy * 0.60 + yield_curve_proxy * 0.20)
    debt_proxy = _clamp(2.0 - debt_position * 4.0)
    interest_proxy = _clamp(2.0 - interest_position * 4.0)
    foreign_proxy = _clamp((foreign_position - 0.5) * 3.0 + _scale(foreign_trend, 0.0, 3.0))

    proxies = {
        "recession_pressure": round(recession_proxy, 3),
        "us_10y_yield": round(us_10y_proxy, 3),
        "us_30y_yield": round(us_30y_proxy, 3),
        "yield_curve": round(yield_curve_proxy, 3),
        "real_rate": round(real_rate_proxy, 3),
        "debt_sustainability": round(debt_proxy, 3),
        "interest_burden": round(interest_proxy, 3),
        "foreign_demand": round(foreign_proxy, 3),
    }
    reasons = {
        "recession_pressure": f"10Y-2Y spread {latest_spread:.2f}%; deeper inversion raises TLT hedge demand.",
        "yield_curve": f"10Y-2Y spread {latest_spread:.2f}%; negative spread is positive for recession-insurance demand.",
        "real_rate": f"DFII10 real-rate range position {real_position:.1%}; middle/high real rates imply future easing room but are capped elsewhere.",
        "us_10y_yield": "Approximated from DFII10 real-rate range because v1.1 L.O.D.E. fetch list does not include nominal 10Y yield.",
        "us_30y_yield": "Approximated from DFII10 real-rate range plus yield-curve inversion because v1.1 L.O.D.E. fetch list does not include nominal 30Y yield.",
        "debt_sustainability": f"Debt/GDP {latest_debt_gdp:.1f}% at {debt_position:.1%} of sample range; higher range position impairs Treasury role.",
        "interest_burden": f"Interest payments/tax receipts {latest_interest_to_tax:.1f}% at {interest_position:.1%} of sample range; higher burden impairs role.",
        "foreign_demand": f"Foreign holdings ratio {latest_foreign_ratio:.1f}% at {foreign_position:.1%} of range with trend {foreign_trend:+.2f}pp.",
    }
    return LodeResult({"TLT": proxies}, proxies, reasons, [], str(latest["date"]), "L.O.D.E. FRED", True)


def load_lode_csv(path: str) -> List[Dict[str, float | str | None]]:
    """Load manual L.O.D.E. rows from CSV.

    Expected columns are date plus the raw FRED IDs used by ``FRED_SERIES``:
    T10Y2Y, DFII10, GFDEGDQ188S, A091RC1Q027SBEA, W006RC1Q027SBEA,
    FDHBFIN, and GFDEBTN. Values are forwarded to the same proxy pipeline as
    live FRED data.
    """

    rows: List[Dict[str, float | str | None]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: Dict[str, float | str | None] = {"date": raw.get("date", "unknown")}
            for series_id in FRED_SERIES:
                row[series_id] = _to_float(raw.get(series_id, ""))
            rows.append(row)
    return rows


def tlt_role_inputs_from_csv(path: str) -> LodeResult:
    """Generate TLT Role inputs from a manual L.O.D.E. CSV."""

    result = compute_tlt_role_proxies(load_lode_csv(path))
    if result.used_lode:
        return LodeResult(result.role_inputs, result.proxies, result.reasons, result.warnings, result.data_date, f"manual L.O.D.E. CSV: {path}", True)
    return LodeResult(result.role_inputs, result.proxies, result.reasons, result.warnings, result.data_date, f"manual L.O.D.E. CSV: {path}", False)


def latest_tlt_role_inputs(
    start: str | date | None = None, end: str | date | None = None, *,
    retry_count: int = DEFAULT_FRED_RETRY_COUNT, pause: float = DEFAULT_FRED_PAUSE,
    timeout: float = DEFAULT_FRED_TIMEOUT, cache_dir: str | None = None,
    fred_provider: str = "pandas_datareader",
) -> LodeResult:
    """Use live FRED, then last-successful cache, then neutral fallback."""
    try:
        rows = fetch_lode_fred_data(start, end, retry_count=retry_count, pause=pause, timeout=timeout, provider=fred_provider)
        result = compute_tlt_role_proxies(rows)
        if result.used_lode and cache_dir:
            save_fred_cache(cache_dir, "lode", rows)
        return result
    except Exception as exc:  # noqa: BLE001 - provider failure must not stop an audit.
        if cache_dir:
            try:
                rows, stale_days, path = load_fred_cache(cache_dir, "lode")
                result = compute_tlt_role_proxies(rows)
                if result.used_lode:
                    warning = f"warning: live L.O.D.E. FRED fetch failed ({exc}); using last successful cache {path} ({stale_days} stale days)."
                    return LodeResult(result.role_inputs, result.proxies, result.reasons, result.warnings + [warning], result.data_date, "cache", True, True, stale_days)
            except Exception:
                pass
        neutral = {name: float(DEFAULT_ROLE_INPUTS["TLT"].get(name, 0.0)) for name in TLT_LODE_COMPONENTS}
        warning = f"warning: failed to fetch L.O.D.E. FRED data ({exc}); no usable cache; neutral TLT Role proxy fallback applied."
        return LodeResult({"TLT": neutral}, neutral, {}, [warning], "unknown", "L.O.D.E. FRED", False, True, None)
