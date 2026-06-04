"""Transparent price-opportunity scoring."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .config import PRICE_COMPONENT_WEIGHTS


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class PriceScoreResult:
    asset: str
    score: float
    components: Mapping[str, Optional[float]]
    reasons: List[str]


def _mean(values: List[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for prev, cur in zip(closes[-period - 1 : -1], closes[-period:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = _mean(gains)
    avg_loss = _mean(losses)
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _range_position(closes: List[float], lookback: int) -> Optional[float]:
    if len(closes) < 2:
        return None
    window = closes[-min(lookback, len(closes)) :]
    low = min(window)
    high = max(window)
    if high == low:
        return 50.0
    return 100.0 * (window[-1] - low) / (high - low)


def _component_from_rsi(rsi: Optional[float]) -> Optional[float]:
    if rsi is None:
        return None
    # RSI 30 is attractive (oversold), RSI 70 is unattractive (overbought).
    return clamp(100.0 - ((rsi - 30.0) / 40.0) * 100.0)


def _component_from_deviation(deviation: Optional[float]) -> Optional[float]:
    if deviation is None:
        return None
    # -25% below the 200DMA maps to 100; +25% above maps to 0.
    return clamp(50.0 - deviation * 200.0)


def _component_from_position(position: Optional[float]) -> Optional[float]:
    if position is None:
        return None
    return clamp(100.0 - position)


def _component_from_zscore(z_score: Optional[float]) -> Optional[float]:
    if z_score is None:
        return None
    # -2σ maps to 100; +2σ maps to 0.
    return clamp(50.0 - z_score * 25.0)


def _component_from_weekly_return(weekly_return: Optional[float]) -> Optional[float]:
    if weekly_return is None:
        return None
    # A -10% week maps to 100; a +10% week maps to 0.
    return clamp(50.0 - weekly_return * 500.0)


def _weighted_average(components: Mapping[str, Optional[float]], weights: Mapping[str, float]) -> float:
    available = [(name, value) for name, value in components.items() if value is not None]
    if not available:
        return 50.0
    total_weight = sum(weights[name] for name, _ in available)
    return sum(float(value) * weights[name] for name, value in available) / total_weight


def score_price(asset: str, closes: Iterable[float]) -> PriceScoreResult:
    """Return a 0-100 price opportunity score for one asset.

    High scores indicate pessimism/cheapness. Missing lookbacks are ignored and
    remaining components are reweighted, so sparse data still yields a result.
    """

    series = [float(v) for v in closes if v is not None and float(v) > 0]
    if not series:
        return PriceScoreResult(asset, 50.0, {name: None for name in PRICE_COMPONENT_WEIGHTS}, ["No price history; neutral fallback."])

    latest = series[-1]
    rsi_value = _rsi(series)
    dma_200 = _mean(series[-200:]) if len(series) >= 200 else None
    dma_dev = (latest / dma_200 - 1.0) if dma_200 else None
    range_52w = _range_position(series, 252)
    range_5y = _range_position(series, 1260)
    z_window = series[-min(252, len(series)) :]
    z_std = _stdev(z_window)
    z_score = ((latest - _mean(z_window)) / z_std) if z_std else 0.0
    weekly_return = (latest / series[-6] - 1.0) if len(series) >= 6 else None

    components: Dict[str, Optional[float]] = {
        "rsi": _component_from_rsi(rsi_value),
        "dma_200_deviation": _component_from_deviation(dma_dev),
        "range_52w_position": _component_from_position(range_52w),
        "z_score": _component_from_zscore(z_score),
        "weekly_drawdown": _component_from_weekly_return(weekly_return),
        "range_5y_position": _component_from_position(range_5y),
    }
    score = round(_weighted_average(components, PRICE_COMPONENT_WEIGHTS), 2)
    reasons = [
        f"RSI={rsi_value:.1f}" if rsi_value is not None else "RSI unavailable",
        f"200DMA deviation={dma_dev:.1%}" if dma_dev is not None else "200DMA unavailable",
        f"52w range position={range_52w:.1f}" if range_52w is not None else "52w range unavailable",
        f"z-score={z_score:.2f}",
        f"weekly return={weekly_return:.1%}" if weekly_return is not None else "weekly return unavailable",
        f"5y range position={range_5y:.1f}" if range_5y is not None else "5y range unavailable",
    ]
    return PriceScoreResult(asset, score, components, reasons)
