"""Role-health scoring for non-permanent El Shaddai assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from .config import DEFAULT_ROLE_INPUTS, ROLE_ASSETS, ROLE_COMPONENT_GROUPS, ROLE_COMPONENT_WEIGHTS, ROLE_GROUP_WEIGHTS
from .price_score import clamp


@dataclass(frozen=True)
class RoleScoreResult:
    asset: str
    score: Optional[float]
    components: Mapping[str, float]
    reasons: List[str]
    raw_weighted_score: Optional[float] = None
    penalty_adjusted_score: Optional[float] = None
    core_score: Optional[float] = None
    support_score: Optional[float] = None
    penalty_score: Optional[float] = None
    applied_caps: List[str] = field(default_factory=list)
    role_interpretation: str = ""


def proxy_to_score(value: float) -> float:
    """Convert a direction-adjusted -2..+2 role proxy into a 0..100 score.

    Role proxy values must be direction-adjusted before scoring. +2 always
    means favorable for that specific asset's role, and -2 always means
    impaired, regardless of whether the raw macro series itself is rising or
    falling. Values outside the range are accepted but clipped.
    """

    return clamp(50.0 + float(value) * 25.0)


def _weighted_average(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = sum(weights.get(name, 0.0) for name in values)
    if total_weight == 0:
        return 50.0
    return sum(values[name] * weights.get(name, 0.0) for name in values) / total_weight


def _group_score(components: Mapping[str, float], weights: Mapping[str, float], groups: Mapping[str, str], group: str) -> Optional[float]:
    selected = {name: value for name, value in components.items() if groups.get(name, "core") == group}
    if not selected:
        return None
    return _weighted_average(selected, weights)


def _structured_score(asset: str, components: Mapping[str, float], weights: Mapping[str, float]) -> tuple[float, Optional[float], Optional[float], Optional[float], List[str], str]:
    groups = ROLE_COMPONENT_GROUPS.get(asset, {name: "core" for name in weights})
    raw = _weighted_average(components, weights)
    group_weights = ROLE_GROUP_WEIGHTS.get(asset)
    core = _group_score(components, weights, groups, "core")
    support = _group_score(components, weights, groups, "support")
    penalty = _group_score(components, weights, groups, "risk_penalty")
    context = _group_score(components, weights, groups, "context")
    caps: List[str] = []

    if not group_weights:
        return raw, core, support, penalty, caps, "Role Score uses component weights; all components are treated as core for v1.5 structure."

    structured = 0.0
    used_group_weight = 0.0
    for group, group_weight in group_weights.items():
        score = {"core": core, "support": support, "risk_penalty": penalty, "context": context}.get(group)
        if score is not None:
            structured += score * group_weight
            used_group_weight += group_weight
    adjusted = structured / used_group_weight if used_group_weight else raw

    if asset == "BNDX":
        pillar_names = ["sovereign_trust", "currency_order", "liquidity_flow", "diversification_integrity"]
        failed = [name for name in pillar_names if components.get(name, 50.0) <= 25.0]
        failed_set = set(failed)
        if len(failed) >= 4:
            adjusted = min(adjusted, 0.0)
            caps.append("Atlas four-pillar failure cap: Role Score capped at 0")
        elif len(failed) == 3:
            adjusted = min(adjusted, 20.0)
            caps.append("Atlas three-pillar failure cap: Role Score capped at 20")
        elif len(failed) == 2:
            adjacent_pairs = [
                {"sovereign_trust", "currency_order"},
                {"currency_order", "liquidity_flow"},
                {"liquidity_flow", "diversification_integrity"},
                {"diversification_integrity", "sovereign_trust"},
            ]
            if any(failed_set == pair for pair in adjacent_pairs):
                adjusted = min(adjusted, 35.0)
                caps.append("Atlas adjacent-pillar failure cap: Role Score capped at 35")
            else:
                adjusted = min(adjusted, 50.0)
                caps.append("Atlas diagonal-pillar failure cap: Role Score capped at 50")

    if asset == "TLT" and penalty is not None:
        penalty_components = [value for name, value in components.items() if groups.get(name) == "risk_penalty"]
        severe_penalty_count = sum(1 for value in penalty_components if value <= 25.0)
        if severe_penalty_count >= 2:
            adjusted = min(adjusted, 55.0)
            caps.append("TLT fiscal/foreign-demand risk cap: >=2 severe penalty components capped Role Score at 55")
        if severe_penalty_count >= 3:
            adjusted = min(adjusted, 45.0)
            caps.append("TLT severe risk cap: all three penalty components severe capped Role Score at 45")

    if asset == "GLDM" and core is not None:
        weak_core_count = sum(1 for name, value in components.items() if groups.get(name) == "core" and value <= 25.0)
        if weak_core_count >= 2:
            adjusted = min(adjusted, 50.0)
            caps.append("GLDM core role impairment cap: >=2 weak core components capped Role Score at 50")

    if asset == "TIP":
        real_rate_severe = components.get("real_rate_shock", 50.0) <= 25.0
        deflation_severe = components.get("deflation_pressure", 50.0) <= 25.0
        macro_severe = components.get("macro_submission", 50.0) <= 25.0
        if real_rate_severe:
            adjusted = min(adjusted, 55.0)
            caps.append("TIP real-rate shock cap: severe real_rate_shock capped Role Score at 55")
        if real_rate_severe and deflation_severe:
            adjusted = min(adjusted, 45.0)
            caps.append("TIP real-rate + deflation cap: severe real_rate_shock and deflation_pressure capped Role Score at 45")
        if real_rate_severe and deflation_severe and macro_severe:
            adjusted = min(adjusted, 35.0)
            caps.append("TIP full penalty cap: all three risk penalties severe capped Role Score at 35")

    if asset == "DBC":
        dollar_severe = components.get("dollar_headwind", 50.0) <= 25.0
        deflation_severe = components.get("deflation_drag", 50.0) <= 25.0
        growth_severe = components.get("growth_collapse", 50.0) <= 25.0
        noise_severe = components.get("commodity_noise", 50.0) <= 25.0
        if dollar_severe:
            adjusted = min(adjusted, 60.0)
            caps.append("DBC dollar headwind cap: severe dollar_headwind capped Role Score at 60")
        if dollar_severe and deflation_severe:
            adjusted = min(adjusted, 45.0)
            caps.append("DBC dollar + deflation cap: severe dollar_headwind and deflation_drag capped Role Score at 45")
        if growth_severe and noise_severe:
            adjusted = min(adjusted, 40.0)
            caps.append("DBC growth-collapse + commodity-noise cap: severe growth_collapse and commodity_noise capped Role Score at 40")
        if dollar_severe and deflation_severe and growth_severe:
            adjusted = min(adjusted, 30.0)
            caps.append("DBC full choking cap: severe dollar_headwind, deflation_drag, and growth_collapse capped Role Score at 30")

    if asset == "XLRE":
        real_rate_severe = components.get("real_rate_shock", 50.0) <= 25.0
        credit_severe = components.get("credit_stress", 50.0) <= 25.0
        equity_severe = components.get("equity_submission", 50.0) <= 25.0
        dollar_severe = components.get("dollar_headwind", 50.0) <= 25.0
        if real_rate_severe:
            adjusted = min(adjusted, 55.0)
            caps.append("XLRE real-rate shock cap: severe real_rate_shock capped Role Score at 55")
        if real_rate_severe and credit_severe:
            adjusted = min(adjusted, 45.0)
            caps.append("XLRE rates + credit cap: severe real_rate_shock and credit_stress capped Role Score at 45")
        if real_rate_severe and credit_severe and equity_severe:
            adjusted = min(adjusted, 35.0)
            caps.append("XLRE full role-failure cap: severe real_rate_shock, credit_stress, and equity_submission capped Role Score at 35")
        if dollar_severe and credit_severe:
            adjusted = min(adjusted, 50.0)
            caps.append("XLRE dollar + credit cap: severe dollar_headwind and credit_stress capped Role Score at 50")

    if asset == "BNDX":
        pillar_names = ["sovereign_trust", "currency_order", "liquidity_flow", "diversification_integrity"]
        failed = [name for name in pillar_names if components.get(name, 50.0) <= 25.0]
        failed_set = set(failed)
        if len(failed) >= 3:
            atlas_status = "Atlas Fallen"
            atlas_message = "The sovereign-credit structure is no longer reliable."
        elif len(failed) == 2:
            adjacent_pairs = [
                {"sovereign_trust", "currency_order"},
                {"currency_order", "liquidity_flow"},
                {"liquidity_flow", "diversification_integrity"},
                {"diversification_integrity", "sovereign_trust"},
            ]
            if any(failed_set == pair for pair in adjacent_pairs):
                atlas_status = "Atlas Cannot Hold"
                atlas_message = "Adjacent pillar collapse detected. Blanket integrity compromised."
            else:
                atlas_status = "Atlas Kneeling"
                atlas_message = "Structural stress detected. Winter protection reduced."
        elif len(failed) == 1:
            atlas_status = "Atlas Strained"
            atlas_message = "One pillar weakened. Monitor carefully."
        else:
            atlas_status = "Atlas Standing"
            atlas_message = "Winter blanket remains intact."
        interpretation = f"{atlas_status}: {atlas_message} Failed pillars: {', '.join(failed) if failed else 'none'}."
    else:
        interpretation = f"raw_weighted={raw:.2f}; structured core/support/context/penalty aggregation applied for {asset}."
    if caps:
        interpretation += " Caps applied: " + " | ".join(caps)
    return adjusted, core, support, penalty, caps, interpretation


def score_role(asset: str, role_inputs: Optional[Mapping[str, Mapping[str, float]]] = None) -> RoleScoreResult:
    if asset not in ROLE_ASSETS:
        return RoleScoreResult(asset, None, {}, ["Role diagnosis is not applied to permanent holding assets."])

    merged: Dict[str, Dict[str, float]] = {name: dict(values) for name, values in DEFAULT_ROLE_INPUTS.items()}
    if role_inputs:
        for input_asset, values in role_inputs.items():
            merged.setdefault(input_asset, {}).update({key: float(value) for key, value in values.items()})

    weights = ROLE_COMPONENT_WEIGHTS[asset]
    asset_inputs = merged.get(asset, {})
    groups = ROLE_COMPONENT_GROUPS.get(asset, {name: "core" for name in weights})
    components = {name: proxy_to_score(asset_inputs.get(name, 0.0)) for name in weights}
    reasons = [f"{name} [{groups.get(name, 'core')}] proxy={asset_inputs.get(name, 0.0):+.2f} => {components[name]:.1f}" for name in weights]

    unknown_inputs = sorted(set(asset_inputs) - set(weights))
    if unknown_inputs:
        reasons.append(f"warning: ignored unknown role input(s): {', '.join(unknown_inputs)}")

    total_weight = sum(weights.values())
    if total_weight == 0:
        reasons.append("warning: role component weights sum to 0; neutral Role Score fallback applied.")
        return RoleScoreResult(asset, 50.0, components, reasons, 50.0, 50.0, None, None, None, ["neutral fallback: zero total role weights"], "Role weights sum to zero; neutral fallback.")

    raw = _weighted_average(components, weights)
    adjusted, core, support, penalty, caps, interpretation = _structured_score(asset, components, weights)
    reasons.extend([
        f"raw_weighted_score={raw:.2f}",
        f"penalty_adjusted_score={adjusted:.2f}",
        f"core_score={'N/A' if core is None else f'{core:.2f}'}",
        f"support_score={'N/A' if support is None else f'{support:.2f}'}",
        f"penalty_score={'N/A' if penalty is None else f'{penalty:.2f}'}",
        f"role_interpretation={interpretation}",
    ])
    for cap in caps:
        reasons.append(f"applied_cap={cap}")

    return RoleScoreResult(
        asset,
        round(adjusted, 2),
        components,
        reasons,
        round(raw, 2),
        round(adjusted, 2),
        None if core is None else round(core, 2),
        None if support is None else round(support, 2),
        None if penalty is None else round(penalty, 2),
        caps,
        interpretation,
    )
