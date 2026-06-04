"""Data loading for El Shaddai.

The loader supports auditable local CSV/JSON inputs and deterministic sample data.
No network dependency is required for v1.0, which keeps tests reproducible.
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from math import sin
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

from .config import ASSETS, DEFAULT_ROLE_INPUTS, DataSourceConfig


def load_role_inputs(path: str | None) -> Mapping[str, Mapping[str, float]]:
    if not path:
        return DEFAULT_ROLE_INPUTS
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {asset: {name: float(value) for name, value in values.items()} for asset, values in raw.items()}


def load_prices_csv(path: str) -> Tuple[Dict[str, List[float]], str]:
    """Load prices from a CSV with columns date, asset, close."""

    prices: Dict[str, List[float]] = {asset: [] for asset in ASSETS}
    latest_date = "unknown"
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            asset = row["asset"].strip().upper()
            if asset in prices:
                prices[asset].append(float(row["close"]))
                latest_date = max(latest_date, row.get("date", "unknown")) if latest_date != "unknown" else row.get("date", "unknown")
    return prices, latest_date


def _sample_path(asset_index: int, days: int) -> List[float]:
    base = 100.0 + asset_index * 7.0
    trend = (asset_index - 3.5) * 0.012
    cycle = 4.0 + asset_index * 0.3
    shock = -8.0 + asset_index * 1.8
    values: List[float] = []
    for day in range(days):
        seasonal = sin(day / 19.0 + asset_index) * cycle
        late_shock = shock * max(0.0, (day - (days - 35)) / 35.0)
        value = base + trend * day + seasonal + late_shock
        values.append(max(1.0, round(value, 4)))
    return values


def load_sample_prices(days: int = 320) -> Tuple[Dict[str, List[float]], str]:
    prices = {asset: _sample_path(index, days) for index, asset in enumerate(ASSETS)}
    data_date = (date.today() - timedelta(days=1)).isoformat()
    return prices, data_date


def load_inputs(config: DataSourceConfig) -> Tuple[Dict[str, List[float]], Mapping[str, Mapping[str, float]], str, str]:
    if config.prices_csv:
        prices, data_date = load_prices_csv(config.prices_csv)
        price_source = f"local CSV: {config.prices_csv}"
    else:
        prices, data_date = load_sample_prices(config.sample_days)
        price_source = "deterministic built-in sample price history"
    role_inputs = load_role_inputs(config.role_inputs_json)
    role_source = f"local JSON: {config.role_inputs_json}" if config.role_inputs_json else "neutral built-in role proxy inputs"
    return prices, role_inputs, data_date, f"prices={price_source}; roles={role_source}"
