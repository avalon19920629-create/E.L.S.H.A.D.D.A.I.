"""I.N.F.E.R.N.O. adapter for TIP Role proxies.

I.N.F.E.R.N.O. = Inflation Navigation Framework for Evaluating Real-rate
Neutralization Operations.  It converts inflation, breakeven, real-rate, and
macro pressure data into TIP-direction-adjusted -2..+2 proxies, where +2 is
favorable for TIP's purchasing-power-defense role.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .config import DEFAULT_ROLE_INPUTS

INFERNO_FRED_SERIES: Mapping[str, str] = {
    "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
    "CPILFESL": "Core CPI",
    "PCEPI": "PCE Price Index",
    "PCEPILFE": "Core PCE Price Index",
    "T5YIE": "5-Year Breakeven Inflation Rate",
    "T10YIE": "10-Year Breakeven Inflation Rate",
    "DFII10": "10-Year TIPS real yield",
    "UNRATE": "Unemployment Rate",
    "DTWEXBGS": "Nominal Broad U.S. Dollar Index",
}

TIP_INFERNO_COMPONENTS: Sequence[str] = (
    "inflation_threat",
    "inflation_expectation_gap",
    "purchasing_power_protection",
    "stagflation_pressure",
    "inflation_regime_strength",
    "real_rate_shock",
    "deflation_pressure",
    "macro_submission",
)


INFERNO_CSV_COLUMN_MAP: Mapping[str, str] = {
    "cpi": "CPI_YOY",
    "core_cpi": "CORE_CPI_YOY",
    "pce": "PCE_YOY",
    "core_pce": "CORE_PCE_YOY",
    "cpi_yoy": "CPI_YOY",
    "core_cpi_yoy": "CORE_CPI_YOY",
    "pce_yoy": "PCE_YOY",
    "core_pce_yoy": "CORE_PCE_YOY",
    "breakeven_5y": "T5YIE",
    "breakeven_10y": "T10YIE",
    "dfii10": "DFII10",
    "unrate": "UNRATE",
    "broad_dollar": "DTWEXBGS",
    "tip_close": "TIP",
    "tlt_close": "TLT",
    "dbc_close": "DBC",
}


@dataclass(frozen=True)
class InfernoResult:
    role_inputs: Mapping[str, Mapping[str, float]]
    proxies: Mapping[str, float]
    reasons: Mapping[str, str]
    warnings: List[str]
    data_date: str
    source: str
    used_inferno: bool
    inflation_regime_interpretation: str
    applied_caps: List[str]


def _to_float(value: str | None) -> Optional[float]:
    if value in {None, "", ".", "nan", "NaN", "None"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clamp(value: float, low: float = -2.0, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _neutral_result(warnings: List[str], source: str = "I.N.F.E.R.N.O. FRED") -> InfernoResult:
    neutral = {name: float(DEFAULT_ROLE_INPUTS["TIP"].get(name, 0.0)) for name in TIP_INFERNO_COMPONENTS}
    return InfernoResult({"TIP": neutral}, neutral, {}, warnings, "unknown", source, False, "neutral fallback", [])


def _fred_csv_url(series_id: str, start: str, end: str) -> str:
    params = urllib.parse.urlencode({"id": series_id, "cosd": start, "coed": end})
    return f"https://fred.stlouisfed.org/graph/fredgraph.csv?{params}"


def _fetch_one_series(series_id: str, start: str, end: str) -> Dict[str, Optional[float]]:
    with urllib.request.urlopen(_fred_csv_url(series_id, start, end), timeout=20) as response:
        text = response.read().decode("utf-8")
    return {row["observation_date"]: _to_float(row[series_id]) for row in csv.DictReader(io.StringIO(text))}


def fetch_inferno_fred_data(start: str | date | None = None, end: str | date | None = None) -> List[Dict[str, float | str | None]]:
    end_date = end or date.today()
    start_date = start or (date.today() - timedelta(days=365 * 10))
    start_text = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
    end_text = end_date.isoformat() if isinstance(end_date, date) else str(end_date)
    series_data = {series_id: _fetch_one_series(series_id, start_text, end_text) for series_id in INFERNO_FRED_SERIES}
    all_dates = sorted({row_date for values in series_data.values() for row_date in values})
    latest_values: Dict[str, Optional[float]] = {series_id: None for series_id in INFERNO_FRED_SERIES}
    rows: List[Dict[str, float | str | None]] = []
    for row_date in all_dates:
        row: Dict[str, float | str | None] = {"date": row_date}
        for series_id, observations in series_data.items():
            if row_date in observations and observations[row_date] is not None:
                latest_values[series_id] = observations[row_date]
            row[series_id] = latest_values[series_id]
        rows.append(row)
    return rows


def load_inferno_csv(path: str) -> List[Dict[str, float | str | None]]:
    """Load manual I.N.F.E.R.N.O. CSV rows for offline TIP role proxy generation.

    The preferred CSV uses human-friendly lower-case columns such as ``cpi``,
    ``breakeven_5y``, ``dfii10``, ``tip_close``, and ``dbc_close``. Inflation
    columns are interpreted as YoY rates so reviewers can provide transparent
    scenario data without reconstructing index levels. FRED-style column names
    are also accepted for live-export compatibility.
    """

    rows: List[Dict[str, float | str | None]] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            normalized = {str(key).strip(): value for key, value in raw_row.items() if key is not None}
            lower_lookup = {key.lower(): key for key in normalized}
            row: Dict[str, float | str | None] = {"date": normalized.get(lower_lookup.get("date", "date"), "unknown")}
            for csv_name, target_name in INFERNO_CSV_COLUMN_MAP.items():
                source_name = lower_lookup.get(csv_name)
                if source_name is not None:
                    row[target_name] = _to_float(normalized.get(source_name))
            for fred_name in INFERNO_FRED_SERIES:
                if fred_name in normalized:
                    row[fred_name] = _to_float(normalized.get(fred_name))
            for price_name in ("TIP", "TLT", "BNDX", "DBC"):
                if price_name in normalized:
                    row[price_name] = _to_float(normalized.get(price_name))
            rows.append(row)
    return rows


def _latest_float(row: Mapping[str, float | str | None], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _pct_change(first: float, latest: float) -> float:
    if first == 0:
        return 0.0
    return latest / first - 1.0


def compute_inferno_components(df: Iterable[Mapping[str, float | str | None]]) -> List[Dict[str, float | str]]:
    rows = list(df)
    if not rows:
        return []
    components: List[Dict[str, float | str]] = []
    first = rows[0]
    first_values = {name: _latest_float(first, name) for name in set(INFERNO_FRED_SERIES) | {"TIP", "TLT", "BNDX", "DBC"}}
    for row in rows:
        cpi_yoy = _latest_float(row, "CPI_YOY", default=_pct_change(first_values.get("CPIAUCSL", 0.0), _latest_float(row, "CPIAUCSL")) * 100.0)
        core_cpi_yoy = _latest_float(row, "CORE_CPI_YOY", default=_pct_change(first_values.get("CPILFESL", 0.0), _latest_float(row, "CPILFESL")) * 100.0)
        pce_yoy = _latest_float(row, "PCE_YOY", default=_pct_change(first_values.get("PCEPI", 0.0), _latest_float(row, "PCEPI")) * 100.0)
        core_pce_yoy = _latest_float(row, "CORE_PCE_YOY", default=_pct_change(first_values.get("PCEPILFE", 0.0), _latest_float(row, "PCEPILFE")) * 100.0)
        breakeven = (_latest_float(row, "T5YIE") + _latest_float(row, "T10YIE")) / 2.0
        tip_rel = _pct_change(first_values.get("TIP", 0.0), _latest_float(row, "TIP")) - _pct_change(first_values.get("TLT", 0.0), _latest_float(row, "TLT")) if first_values.get("TIP") and first_values.get("TLT") else 0.0
        dbc_trend = _pct_change(first_values.get("DBC", 0.0), _latest_float(row, "DBC")) if first_values.get("DBC") else 0.0
        real_rate = _latest_float(row, "DFII10")
        real_rate_start = first_values.get("DFII10", 0.0)
        dollar_trend = _pct_change(first_values.get("DTWEXBGS", 0.0), _latest_float(row, "DTWEXBGS")) if first_values.get("DTWEXBGS") else 0.0
        unrate = _latest_float(row, "UNRATE")
        unrate_start = first_values.get("UNRATE", unrate)
        inflation_avg = (cpi_yoy + core_cpi_yoy + pce_yoy + core_pce_yoy) / 4.0
        components.append({
            "date": str(row.get("date", "unknown")),
            "inflation_avg": inflation_avg,
            "breakeven_avg": breakeven,
            "expectation_gap": inflation_avg - breakeven,
            "tip_relative_strength": tip_rel,
            "dbc_trend": dbc_trend,
            "real_rate": real_rate,
            "real_rate_change": real_rate - real_rate_start,
            "unemployment_change": unrate - unrate_start,
            "dollar_trend": dollar_trend,
        })
    return components


def compute_tip_role_proxies(df: Iterable[Mapping[str, float | str | None]]) -> InfernoResult:
    components = compute_inferno_components(df)
    if not components:
        return _neutral_result(["warning: I.N.F.E.R.N.O. data had no complete rows; neutral TIP Role proxy fallback applied."])
    latest = components[-1]
    inflation = float(latest["inflation_avg"])
    breakeven = float(latest["breakeven_avg"])
    gap = float(latest["expectation_gap"])
    tip_rel = float(latest["tip_relative_strength"])
    dbc_trend = float(latest["dbc_trend"])
    real_rate = float(latest["real_rate"])
    real_change = float(latest["real_rate_change"])
    unemp_change = float(latest["unemployment_change"])
    dollar_trend = float(latest["dollar_trend"])

    proxies = {
        "inflation_threat": round(_clamp((inflation - 2.0) / 1.5), 3),
        "inflation_expectation_gap": round(_clamp(gap / 1.0), 3),
        "purchasing_power_protection": round(_clamp(tip_rel * 20.0), 3),
        "stagflation_pressure": round(_clamp((inflation - 2.0) / 2.0 + unemp_change / 1.0), 3),
        "inflation_regime_strength": round(_clamp(dbc_trend * 10.0 + (inflation - 2.0) / 4.0), 3),
        "real_rate_shock": round(_clamp(-((real_rate - 1.0) / 1.0 + real_change / 0.75)), 3),
        "deflation_pressure": round(_clamp(-((1.5 - inflation) / 1.5 + max(0.0, 2.0 - breakeven) / 1.0)), 3),
        "macro_submission": round(_clamp(-(max(0.0, dollar_trend) * 20.0 + max(0.0, real_change) / 0.75)), 3),
    }
    severe = [name for name in ("real_rate_shock", "deflation_pressure", "macro_submission") if proxies[name] <= -1.0]
    warnings = [f"warning: I.N.F.E.R.N.O. severe penalty proxy detected: {name}" for name in severe]
    if inflation >= 4.0 and gap > 1.0:
        interpretation = "inflation underpricing / purchasing-power defense regime"
    elif proxies["real_rate_shock"] <= -1.0:
        interpretation = "real-rate shock regime; TIP bond duration risk dominates"
    elif proxies["deflation_pressure"] <= -1.0:
        interpretation = "deflation / Winter pressure regime"
    elif proxies["macro_submission"] <= -1.0:
        interpretation = "traditional macro submission regime"
    else:
        interpretation = "mixed inflation regime"
    reasons = {
        "inflation_threat": f"Average CPI/Core CPI/PCE/Core PCE inflation {inflation:.2f}%; higher inflation supports TIP magic resistance.",
        "inflation_expectation_gap": f"Inflation {inflation:.2f}% vs breakeven {breakeven:.2f}% => gap {gap:+.2f}pp; positive gap means market underprices inflation.",
        "purchasing_power_protection": f"TIP/TLT relative strength differential {tip_rel:+.2%}; positive relative strength shows purchasing-power protection working.",
        "stagflation_pressure": f"Inflation {inflation:.2f}% with unemployment change {unemp_change:+.2f}pp; high inflation plus weaker growth is favorable for TIP role.",
        "inflation_regime_strength": f"DBC trend {dbc_trend:+.2%} and inflation {inflation:.2f}% indicate Summer/inflation-regime strength.",
        "real_rate_shock": f"DFII10 {real_rate:.2f}% with change {real_change:+.2f}pp; high/rising real rates impair TIP prices.",
        "deflation_pressure": f"Inflation {inflation:.2f}% and breakeven {breakeven:.2f}%; low/falling inflation expectations impair TIP role.",
        "macro_submission": f"Dollar trend {dollar_trend:+.2%} and real-rate change {real_change:+.2f}pp; strong dollar/real-rate dominance reduces TIP-specific edge.",
    }
    return InfernoResult({"TIP": proxies}, proxies, reasons, warnings, str(latest["date"]), "I.N.F.E.R.N.O. FRED", True, interpretation, [])


def tip_role_inputs_from_csv(path: str) -> InfernoResult:
    """Generate TIP role inputs from a manual I.N.F.E.R.N.O. CSV before trying live FRED."""

    try:
        result = compute_tip_role_proxies(load_inferno_csv(path))
        return InfernoResult(
            result.role_inputs,
            result.proxies,
            result.reasons,
            result.warnings,
            result.data_date,
            f"manual I.N.F.E.R.N.O. CSV: {path}",
            result.used_inferno,
            result.inflation_regime_interpretation,
            result.applied_caps,
        )
    except Exception as exc:  # noqa: BLE001 - manual route must not crash the CLI.
        return _neutral_result(
            [f"warning: failed to load manual I.N.F.E.R.N.O. CSV ({exc}); neutral TIP Role proxy fallback applied."],
            source=f"manual I.N.F.E.R.N.O. CSV: {path}",
        )


def latest_tip_role_inputs(start: str | date | None = None, end: str | date | None = None) -> InfernoResult:
    try:
        result = compute_tip_role_proxies(fetch_inferno_fred_data(start, end))
        return result
    except Exception as exc:  # noqa: BLE001 - CLI must continue on provider issues.
        return _neutral_result([f"warning: failed to fetch I.N.F.E.R.N.O. FRED data ({exc}); neutral TIP Role proxy fallback applied."])
