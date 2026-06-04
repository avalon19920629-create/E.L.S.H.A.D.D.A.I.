"""Combine price and role diagnostics into El Shaddai scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

from .config import ASSETS, PERMANENT_ASSETS
from .price_score import PriceScoreResult, score_price
from .role_score import RoleScoreResult, score_role


@dataclass(frozen=True)
class AssetScore:
    asset: str
    price_score: float
    role_score: Optional[float]
    el_shaddai_score: float
    label: str
    main_reason: str
    data_date: str
    price_details: PriceScoreResult
    role_details: RoleScoreResult


def label_for(asset: str, score: float) -> str:
    if asset in PERMANENT_ASSETS:
        bands = [(80, "Spot Buy Candidate"), (60, "Watch"), (40, "Neutral"), (20, "Not Attractive"), (0, "Avoid Spot Buy")]
    else:
        bands = [(80, "Strong Opportunity"), (60, "Watch"), (40, "Neutral"), (20, "Weak"), (0, "Risk")]
    for threshold, label in bands:
        if score >= threshold:
            return label
    return bands[-1][1]


def score_asset(asset: str, closes: Iterable[float], role_inputs: Mapping[str, Mapping[str, float]], data_date: str) -> AssetScore:
    price = score_price(asset, closes)
    role = score_role(asset, role_inputs)
    combined = price.score if asset in PERMANENT_ASSETS else min(price.score, float(role.score))
    main_reason = "; ".join(price.reasons[:3])
    if role.score is not None:
        main_reason += "; role: " + "; ".join(role.reasons[:2])
    return AssetScore(asset, price.score, role.score, round(combined, 2), label_for(asset, combined), main_reason, data_date, price, role)


def score_all(prices: Mapping[str, Iterable[float]], role_inputs: Mapping[str, Mapping[str, float]], data_date: str) -> List[AssetScore]:
    return [score_asset(asset, prices.get(asset, []), role_inputs, data_date) for asset in ASSETS]


def ranking(scores: Iterable[AssetScore]) -> List[AssetScore]:
    return sorted(scores, key=lambda score: score.el_shaddai_score, reverse=True)
