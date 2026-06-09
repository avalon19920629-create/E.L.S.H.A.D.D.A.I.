"""Shared, lightweight FRED retrieval and last-successful-data cache support."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_FRED_RETRY_COUNT = 3
DEFAULT_FRED_PAUSE = 1.0
DEFAULT_FRED_TIMEOUT = 60.0


def fetch_fred_series_rows(
    series_ids: Sequence[str],
    start: str | date,
    end: str | date,
    *,
    retry_count: int = DEFAULT_FRED_RETRY_COUNT,
    pause: float = DEFAULT_FRED_PAUSE,
    timeout: float = DEFAULT_FRED_TIMEOUT,
    provider: str = "pandas_datareader",
) -> list[dict[str, Any]]:
    """Fetch and forward-fill FRED series, preferring keyless FredReader.

    ``fredapi`` remains an explicit optional provider and reads its key only
    from the ``FRED_API_KEY`` environment variable.
    """

    start_text = start.isoformat() if isinstance(start, date) else str(start)
    end_text = end.isoformat() if isinstance(end, date) else str(end)
    if provider == "pandas_datareader":
        from pandas_datareader.fred import FredReader

        frame = FredReader(
            list(series_ids), start=start_text, end=end_text,
            retry_count=retry_count, pause=pause, timeout=timeout,
        ).read()
    elif provider == "fredapi":
        from fredapi import Fred

        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            raise RuntimeError("FRED_API_KEY environment variable is required for fredapi mode")
        fred = Fred(api_key=api_key)
        series = {
            series_id: fred.get_series(series_id, observation_start=start_text, observation_end=end_text)
            for series_id in series_ids
        }
        import pandas as pd

        frame = pd.DataFrame(series)
    else:
        raise ValueError(f"unsupported FRED provider: {provider}")

    frame = frame.sort_index().ffill()
    rows: list[dict[str, Any]] = []
    for index, values in frame.iterrows():
        row: dict[str, Any] = {"date": index.date().isoformat() if hasattr(index, "date") else str(index)}
        for series_id in series_ids:
            value = values.get(series_id)
            row[series_id] = None if value is None or value != value else float(value)
        rows.append(row)
    return rows


def cache_path(cache_dir: str | Path, adapter: str) -> Path:
    return Path(cache_dir).expanduser() / f"fred_{adapter.lower()}_last_success.json"


def save_fred_cache(cache_dir: str | Path, adapter: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    """Atomically save a successful FRED response to a local/Drive directory."""

    path = cache_path(cache_dir, adapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "adapter": adapter,
        "cached_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_date": str(rows[-1].get("date", "unknown")) if rows else "unknown",
        "rows": list(rows),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return path


def load_fred_cache(cache_dir: str | Path, adapter: str) -> tuple[list[dict[str, Any]], int, Path]:
    """Load last-successful rows and return their cache age in whole days."""

    path = cache_path(cache_dir, adapter)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(payload["cached_at_utc"].replace("Z", "+00:00"))
    stale_days = max(0, (datetime.now(timezone.utc) - cached_at.astimezone(timezone.utc)).days)
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"empty FRED cache: {path}")
    return rows, stale_days, path
