"""Machine-readable JSON representation of the canonical L.U.M.U.S.-8 audit."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .integrated_audit import ROLE_GROUPS

SCHEMA_VERSION = "el_shaddai_lumus8_audit.v1"
REPORT_TITLE = "EL SHADDAI 統合監査報告書 v2.0"
ROLE_GROUP_KEYS = {
    "成長・攻撃": "growth_attack",
    "景気後退防衛": "recession_defense",
    "インフレ防衛": "inflation_defense",
    "実物資産・利回り": "real_asset_yield",
    "危機時退避": "crisis_refuge",
}


def _json_safe(value: Any) -> Any:
    """Convert supported model values to strict-JSON-safe built-in values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]

    # numpy scalar values expose item(), while ordinary application objects do not.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _score_by_asset(scores: Any) -> dict[str, Any]:
    if isinstance(scores, Mapping):
        return {str(asset): score for asset, score in scores.items()}
    return {str(score.asset): score for score in scores or []}


def _role_groups_for(asset: str) -> list[str]:
    return [ROLE_GROUP_KEYS.get(label, label) for label, assets in ROLE_GROUPS.items() if asset in assets]


def _adapter_status(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "source": getattr(result, "source", None),
        "degraded": getattr(result, "degraded", False),
        "stale_days": getattr(result, "stale_days", None),
    }


def _asset_payload(row: Mapping[str, Any], score: Any, adapter_result: Any) -> dict[str, Any]:
    asset = str(row.get("asset", ""))
    engine = row.get("audit_engine")
    status = row.get("display_status")
    oracle_target = engine == "O.R.A.C.L.E."
    return {
        "asset": asset,
        "adapter": engine,
        "score": row.get("asset_health_score"),
        "price_score": getattr(score, "price_score", None),
        "role_score": getattr(score, "role_score", None),
        "final_score": getattr(score, "el_shaddai_score", None),
        "status": status,
        "injury_type": row.get("injury_type"),
        "one_line_summary": row.get("one_line_summary"),
        "recommended_action": row.get("recommended_action"),
        "role_groups": _role_groups_for(asset),
        "is_injured": bool(row.get("wound_level", 0) > 0 and not oracle_target),
        "is_opportunity": bool(oracle_target or status == "追加買い候補"),
        "price_metrics": dict(getattr(getattr(score, "price_details", None), "components", {}) or {}),
        "role_metrics": dict(getattr(getattr(score, "role_details", None), "components", {}) or {}),
        "oracle_details": getattr(score, "oracle_details", None),
        "adapter_status": _adapter_status(adapter_result),
        "warnings": list(getattr(adapter_result, "warnings", []) or []),
    }


def build_integrated_audit_json(
    integrated: Mapping[str, Any],
    scores: Any,
    adapter_results: Mapping[str, Any] | None = None,
    warnings: Any = None,
    generated_at: datetime | str | None = None,
    data_date: date | str | None = None,
) -> dict[str, Any]:
    """Build the canonical audit JSON directly from structured audit data."""
    adapter_results = adapter_results or {}
    by_asset = _score_by_asset(scores)
    assets = [
        _asset_payload(row, by_asset.get(str(row.get("asset", ""))), adapter_results.get(str(row.get("asset", ""))))
        for row in integrated.get("asset_health_rank", [])
    ]
    completeness = integrated.get("data_completeness", {})
    role_groups = {}
    for label, diagnosis in integrated.get("role_group_diagnosis", {}).items():
        normalized_diagnosis = dict(diagnosis)
        if "label" in normalized_diagnosis:
            normalized_diagnosis["health_label"] = normalized_diagnosis.pop("label")
        role_groups[ROLE_GROUP_KEYS.get(label, label)] = {"label": label, **normalized_diagnosis}
    generated_at = generated_at or datetime.now(timezone.utc)
    summary = {
        "sanctuary_health_score": integrated.get("sanctuary_health_score"),
        "internal_role_health_score": integrated.get("internal_sanctuary_health_score"),
        "overall_state": integrated.get("global_judgment_label"),
        "recommended_operation": integrated.get("action_label"),
        "injured_asset_count": len(integrated.get("wounded_assets", [])),
        "opportunity_count": len(integrated.get("opportunity_judgments", [])),
        "injury_breakdown": integrated.get("injury_breakdown", {}),
        "degraded_adapter_count": len(completeness.get("degraded_adapters", [])),
        "failed_adapter_count": len(completeness.get("failed_adapters", [])),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_date": data_date,
        "report_title": REPORT_TITLE,
        "audit_completeness": completeness,
        "data_integrity": {
            "components": integrated.get("components", {}),
            "opening_caveats": integrated.get("opening_caveats", []),
        },
        "summary": summary,
        "actions": {
            "recommended": integrated.get("recommended_actions", []),
            "not_recommended": integrated.get("not_recommended_actions", []),
        },
        "assets": assets,
        "injured_assets": [asset for asset in assets if asset["is_injured"]],
        "opportunities": [asset for asset in assets if asset["is_opportunity"]],
        "role_groups": role_groups,
        "market_context": integrated.get("market_context", {}),
        "correlation_context": {
            "available": completeness.get("correlation_available", False),
            "integrity_score": integrated.get("correlation_integrity_score"),
            "diagnosis": integrated.get("correlation_diagnosis"),
        },
        "next_audit_items": integrated.get("next_checkpoints", []),
        "warnings": list(warnings or []),
        "safety": {"advisory_only": True, "automatic_trading": False},
    }
    return _json_safe(payload)


def write_integrated_audit_json(payload: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write a strict UTF-8 JSON audit while preserving Japanese text."""
    path = Path(output_path)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
