"""Production run manifest and advisory-only quality-gate helpers."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

MANIFEST_SCHEMA_VERSION = "production_run_manifest.v1"
SAFETY_BOUNDARY = {
    "advisory_only": True,
    "automatic_trading": False,
    "automatic_selling": False,
    "allocation_change": False,
    "score_rewrite": False,
}
QUALITY_LABELS = {
    "pass": "Production audit completed",
    "warn": "Production audit completed with warnings",
    "fail": "Production audit incomplete",
}
QUALITY_ICONS = {"pass": "✅", "warn": "⚠️", "fail": "❌"}


def _read_json(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def git_metadata(cwd: str | Path | None = None) -> dict[str, Any]:
    """Return best-effort Git provenance without ever blocking manifest creation."""
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() or None

    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current") or run("rev-parse", "--abbrev-ref", "HEAD")
    status = run("status", "--porcelain")
    return {"commit": commit or "unknown", "branch": branch or "unknown", "is_dirty": None if status is None else bool(status)}


def evaluate_quality_gate(
    market: Mapping[str, Any] | None,
    audit: Mapping[str, Any] | None,
    parallax: Mapping[str, Any] | None,
    *,
    warnings: Sequence[Any] = (),
    safety: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate artifact completeness only; never change investment/context decisions."""
    completeness = audit.get("audit_completeness", {}) if audit else {}
    failed = list(completeness.get("failed_adapters", []) or [])
    degraded = list(completeness.get("degraded_adapters", []) or [])
    price_status = completeness.get("price_data_status")
    fred_status = completeness.get("fred_data_status")
    effective_safety = dict(safety or (parallax or {}).get("safety") or SAFETY_BOUNDARY)
    safety_ok = all(effective_safety.get(key) == value for key, value in SAFETY_BOUNDARY.items())

    reasons: list[str] = []
    for name, payload in (("Market Amedas JSON", market), ("El Shaddai JSON", audit), ("Parallax JSON", parallax)):
        if not payload:
            reasons.append(f"{name} is missing")
    if price_status != "OK":
        reasons.append(f"price_data_status is {price_status or 'unknown'}")
    if fred_status != "OK":
        reasons.append(f"fred_data_status is {fred_status or 'unknown'}")
    if failed:
        reasons.append(f"failed_adapters is not empty: {', '.join(map(str, failed))}")
    if not safety_ok:
        reasons.append("advisory-only safety boundary is not intact")

    warning_items = list(dict.fromkeys(str(item) for item in warnings if item))
    if reasons:
        status = "fail"
    elif warning_items or degraded:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "label": QUALITY_LABELS[status],
        "reasons": reasons,
        "checks": {
            "market_amedas": "OK" if market else "MISSING",
            "el_shaddai": "OK" if audit else "MISSING",
            "parallax": "OK" if parallax else "MISSING",
            "price_data_status": price_status or "unknown",
            "fred_data_status": fred_status or "unknown",
            "fred_provider": completeness.get("fred_provider") or "unknown",
            "degraded_adapters": degraded,
            "failed_adapters": failed,
            "safety": "OK" if safety_ok else "NG",
        },
    }


def render_quality_gate(gate: Mapping[str, Any], output_dir: str | Path) -> str:
    checks = gate.get("checks", {})
    status = str(gate.get("status", "fail"))
    return "\n".join([
        "=" * 60,
        "PRODUCTION QUALITY GATE",
        "=" * 60,
        f"Status : {QUALITY_ICONS.get(status, '❌')} {gate.get('label', QUALITY_LABELS['fail'])}",
        f"Market Amedas : {checks.get('market_amedas', 'MISSING')}",
        f"El Shaddai    : {checks.get('el_shaddai', 'MISSING')}",
        f"Parallax      : {checks.get('parallax', 'MISSING')}",
        f"Price data    : {checks.get('price_data_status', 'unknown')}",
        f"FRED data     : {checks.get('fred_data_status', 'unknown')} via {checks.get('fred_provider', 'unknown')}",
        f"Failed adapters : {checks.get('failed_adapters', [])}",
        f"Warnings count  : {gate.get('warnings_count', 0)}",
        "Safety        : advisory_only / no automatic trading / no automatic selling / no allocation change",
        f"Output dir    : {Path(output_dir).resolve()}",
        "=" * 60,
    ])


def _input_summary(path: str | Path | None, payload: Mapping[str, Any] | None, kind: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"available": bool(payload), "path": str(Path(path).resolve()) if path else None}
    if not payload:
        return summary
    summary["schema_version"] = payload.get("schema_version")
    if kind == "market":
        regime = payload.get("regime", {})
        summary.update({"dominant_air_mass": regime.get("dominant_air_mass"), "secondary_air_mass": regime.get("secondary_air_mass")})
    elif kind == "audit":
        completeness = payload.get("audit_completeness", {})
        for key in ("price_data_status", "fred_data_status", "fred_provider", "degraded_adapters", "failed_adapters"):
            summary[key] = completeness.get(key)
    else:
        report_summary = payload.get("summary", {})
        summary.update({"report_version": payload.get("engine_version"), "parallax_state": report_summary.get("parallax_state"), "high_attention_assets": report_summary.get("high_attention_assets", [])})
    return summary


def build_manifest(
    output_dir: str | Path,
    *,
    market_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    parallax_path: str | Path | None = None,
    warnings: Sequence[Any] = (),
    base: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    destination = Path(output_dir).resolve()
    market, audit, parallax = _read_json(market_path), _read_json(audit_path), _read_json(parallax_path)
    warning_items = list(dict.fromkeys(str(item) for item in warnings if item))
    gate = evaluate_quality_gate(market, audit, parallax, warnings=warning_items, safety=(parallax or {}).get("safety") or SAFETY_BOUNDARY)
    gate["warnings_count"] = len(warning_items)
    generated = [
        {"name": path.name, "path": str(path.resolve()), "size_bytes": path.stat().st_size}
        for path in sorted(destination.glob("*")) if path.is_file() and path.name != "production_run_manifest.json"
    ]
    manifest = dict(base or {})
    manifest.update({
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "git": git_metadata(),
        "inputs": {
            "market_amedas_snapshot": _input_summary(market_path, market, "market"),
            "el_shaddai_audit": _input_summary(audit_path, audit, "audit"),
            "parallax_report": _input_summary(parallax_path, parallax, "parallax"),
        },
        "outputs": {"generated_files": generated},
        "warnings": warning_items,
        "warning_summary": {"count": len(warning_items), "items": warning_items},
        "quality_gate": gate,
        "safety": dict(SAFETY_BOUNDARY),
    })
    return manifest


def write_manifest(output_dir: str | Path, **kwargs: Any) -> Path:
    path = Path(output_dir).resolve() / "production_run_manifest.json"
    path.write_text(json.dumps(build_manifest(output_dir, **kwargs), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
