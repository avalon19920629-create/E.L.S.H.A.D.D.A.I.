"""El Shaddai 統合監査層の公開入力・文脈モデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetAuditInput:
    asset: str
    audit_engine: str
    role_health_score: float
    raw_score: float | None = None
    health_level: int | None = None
    wound_level: int | None = None
    confidence_level: int | None = None
    role_tags: list[str] = field(default_factory=list)
    diagnosis_summary: str = ""
    risk_flags: list[str] = field(default_factory=list)
    supporting_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketAmedasInput:
    air_mass: dict[str, float]
    atmospheric_conditions: dict[str, str]
    updrafts: dict[str, float]
    downdrafts: dict[str, float]
    btc_sensor: str | None = None


@dataclass
class PortfolioInput:
    target_weights: dict[str, float]
    current_weights: dict[str, float] = field(default_factory=dict)
    previous_action_level: int | None = None
    previous_global_judgment_level: int | None = None
    previous_sanctuary_health_score: float | None = None
    rebalance_thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class MarketContext:
    market_context_summary: str
    market_context_flags: list[str]
    role_group_priority: dict[str, str]
    regime_relevance_adjustments: dict[str, float]
    asset_context_notes: dict[str, str]
