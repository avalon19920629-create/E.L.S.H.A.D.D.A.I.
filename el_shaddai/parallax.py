"""Rule-based stereoscopic comparison of Market Amedas and El Shaddai JSON."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "parallax_context_report.v1"
ENGINE_VERSION = "0.1.1"
MARKET_SCHEMA_VERSION = "market_amedas_snapshot.v1"
EL_SHADDAI_SCHEMA_VERSION = "el_shaddai_lumus8_audit.v1"
SAFETY_NOTICE = "本レポートはMarket AmedasとEl Shaddaiの出力を照合する補助診断であり、自動売買・自動売却・配分変更を意味しない。"

ASSET_MAP = {
    "VT": {"primary": "growth", "flows": ["us_equity", "developed_equity", "nasdaq", "emerging_equity"]},
    "BTC": {"primary": "growth", "secondary": "inflation", "flows": ["btc"]},
    "TLT": {"primary": "defense", "secondary": "yield", "flows": ["long_bond"]},
    "BNDX": {"primary": "defense", "secondary": "yield", "flows": ["corporate_bond", "long_bond"]},
    "TIP": {"primary": "inflation", "secondary": "defense", "flows": ["tips"]},
    "GLDM": {"primary": "defense", "secondary": "inflation", "flows": ["gold"]},
    "DBC": {"primary": "inflation", "flows": ["commodity"]},
    "XLRE": {"primary": "yield", "secondary": "growth", "flows": ["reit"]},
}
SEVERITIES = ["low", "medium", "high", "critical"]
CONFIDENCES = ["low", "medium", "high"]


def _load_json(path: str | Path | None, expected_schema: str) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, [f"{expected_schema}: input path was not provided"]
    source = Path(path)
    if not source.is_file():
        return None, [f"{source}: input file is missing"]
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{source}: failed to read JSON ({exc})"]
    if not isinstance(payload, dict):
        return None, [f"{source}: JSON root must be an object"]
    warnings = []
    if payload.get("schema_version") != expected_schema:
        warnings.append(f"{source}: expected schema_version={expected_schema}")
    return payload, warnings


def _text_is_positive(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("strong", "positive", "up", "risk_on", "上昇", "強", "優勢", "追い風")) and not _text_is_negative(text)


def _text_is_negative(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("weak", "negative", "down", "risk_off", "下降", "弱", "逆風", "不振"))


def _conditions(market: Mapping[str, Any]) -> Mapping[str, Any]:
    value = market.get("atmospheric_conditions", {})
    if isinstance(value, Mapping):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return {str(item.get("air_mass", item.get("name", ""))): item for item in value if isinstance(item, Mapping)}
    return {}


def _air_state(market: Mapping[str, Any], air_mass: str | None) -> tuple[str, bool, bool]:
    if not air_mass:
        return "不明", False, False
    regime = market.get("regime", {}) if isinstance(market.get("regime"), Mapping) else {}
    condition = _conditions(market).get(air_mass, {})
    if not isinstance(condition, Mapping):
        condition = {"state": condition}
    raw_state = condition.get("state", condition.get("label", condition.get("direction")))
    score = condition.get("score", condition.get("net_air_mass", condition.get("value")))
    strong = regime.get("dominant_air_mass") == air_mass or regime.get("secondary_air_mass") == air_mass
    weak = False
    if isinstance(score, (int, float)):
        strong = strong or score > 0
        weak = score < 0
    strong = strong or _text_is_positive(raw_state)
    weak = weak or _text_is_negative(raw_state)
    if raw_state is not None:
        label = str(raw_state)
    elif strong:
        label = "上昇優勢"
    elif weak:
        label = "下降優勢"
    else:
        label = "中立または不明"
    return label, strong, weak


def _flow_lookup(market: Mapping[str, Any], keys: Sequence[str]) -> tuple[str | None, float | None]:
    flows = market.get("flows", {}) if isinstance(market.get("flows"), Mapping) else {}
    for direction in ("updrafts", "downdrafts"):
        entries = flows.get(direction, [])
        if isinstance(entries, Mapping):
            entries = [{"key": key, "score": value} for key, value in entries.items()]
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, str):
                name, score = entry, None
            elif isinstance(entry, Mapping):
                name = str(entry.get("key", entry.get("flow_key", entry.get("asset", entry.get("name", "")))))
                score = entry.get("score", entry.get("value"))
            else:
                continue
            if name in keys:
                numeric = float(score) if isinstance(score, (int, float)) else None
                return direction, numeric
    return None, None


def _asset_is_weak(asset: Mapping[str, Any]) -> bool:
    status = " ".join(str(asset.get(key, "")) for key in ("status", "role_status", "role_health_label", "injury_type"))
    score = asset.get("final_score", asset.get("score"))
    return bool(asset.get("is_injured")) or _text_is_negative(status) or "負傷" in status or (isinstance(score, (int, float)) and score < 50)


def _role_is_weak(asset: Mapping[str, Any]) -> bool:
    role_score = asset.get("role_score", asset.get("role_evidence_score"))
    text = " ".join(str(asset.get(key, "")) for key in ("role_status", "role_health_label", "injury_type"))
    return (isinstance(role_score, (int, float)) and role_score < 50) or "役割負傷" in text or _text_is_negative(text)


def _has_warning(asset: Mapping[str, Any], *needles: str) -> list[str]:
    warnings = [str(item) for item in asset.get("warnings", []) if item]
    metrics = asset.get("role_metrics", {}) if isinstance(asset.get("role_metrics"), Mapping) else {}
    return [item for item in warnings + list(map(str, metrics.keys())) if any(needle in item.lower() for needle in needles)]


def _lower_confidence(confidence: str) -> str:
    return CONFIDENCES[max(0, CONFIDENCES.index(confidence) - 1)]


def _oracle_uses_fallback(details: Any) -> bool:
    if not isinstance(details, Mapping):
        return "fallback" in str(details or "").lower()
    if details.get("fallback") is True:
        return True
    return any("fallback" in value for value in _status_text_values(details))


def _increase_severity(severity: str) -> str:
    return SEVERITIES[min(len(SEVERITIES) - 1, SEVERITIES.index(severity) + 1)]


def _status_text_values(value: Any) -> list[str]:
    """Return status values without treating field names such as failed_adapters as failures."""
    if isinstance(value, Mapping):
        return [text for item in value.values() for text in _status_text_values(item)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [text for item in value for text in _status_text_values(item)]
    return [str(value).lower()] if isinstance(value, str) else []


def _nonempty_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _status_is_ng(value: Any) -> bool:
    return any(
        any(token in text for token in ("ng", "missing", "failed", "incomplete", "error", "欠損", "未入力", "不完全"))
        for text in _status_text_values(value)
    )


def _global_critical_warnings(market: Mapping[str, Any], audit: Mapping[str, Any], warnings: Sequence[str]) -> list[str]:
    """Return only failures severe enough to reduce every asset to low confidence."""
    critical = list(warnings)
    if not market:
        critical.append("Market Amedas input is missing")
    elif market.get("schema_version") != MARKET_SCHEMA_VERSION:
        critical.append("Market Amedas schema不正")
    if not audit:
        critical.append("El Shaddai input is missing")
    elif audit.get("schema_version") != EL_SHADDAI_SCHEMA_VERSION:
        critical.append("El Shaddai schema不正")

    market_status = market.get("data_status", {})
    completeness = audit.get("audit_completeness", audit.get("data_status", {}))
    if _status_is_ng(market_status):
        critical.append("Market Amedas data_status is not usable")
    if _status_is_ng(completeness.get("status")):
        critical.append("El Shaddai audit completeness is not usable")
    for field in ("price_data_status", "fred_data_status"):
        if field in completeness and _status_is_ng(completeness.get(field)):
            critical.append(f"El Shaddai {field} is not usable")
    failed = _nonempty_list(completeness.get("failed_adapters", [])) if isinstance(completeness, Mapping) else []
    if failed:
        critical.append(f"El Shaddai failed_adapters: {', '.join(map(str, failed))}")
    severe_degraded = [item for item in _nonempty_list(completeness.get("degraded_adapters", [])) if "severe" in str(item).lower() or "critical" in str(item).lower()]
    if severe_degraded:
        critical.append(f"El Shaddai severe degraded_adapters: {', '.join(map(str, severe_degraded))}")
    return list(dict.fromkeys(map(str, critical)))


def _warning_targets(warning: str) -> set[str]:
    """Map known source warnings to the assets whose evidence they qualify."""
    text = warning.lower()
    if "o.r.a.c.l.e." in text:
        if " vt " in f" {text} ":
            return {"VT"}
        if " btc " in f" {text} ":
            return {"BTC"}
        if "live mode uses price/vix only" in text:
            return {"VT", "BTC"}
    if "i.n.f.e.r.n.o." in text and any(token in text for token in ("real_rate_shock", "macro_submission", "severe penalty")):
        return {"TIP"}
    if "inflation_air_mass_negative" in text:
        return {"TIP", "DBC", "GLDM"}
    if "btc_downdraft_under_risk_on_sensor" in text:
        return {"BTC"}
    return set()


def _relevant_warnings(asset: str, source_warnings: Sequence[str], asset_data: Mapping[str, Any]) -> list[str]:
    relevant = [warning for warning in map(str, source_warnings) if asset in _warning_targets(warning)]
    relevant.extend(str(item) for item in _nonempty_list(asset_data.get("warnings", [])) if item)
    return list(dict.fromkeys(relevant))


def _asset_confidence(global_critical: Sequence[str], relevant_warnings: Sequence[str]) -> str:
    if global_critical:
        return "low"
    if relevant_warnings:
        return "medium"
    return "high"


def _classify_asset(asset: Mapping[str, Any], market: Mapping[str, Any], confidence: str, relevant_warnings: Sequence[str] = ()) -> dict[str, Any]:
    name = str(asset.get("asset", ""))
    mapping = ASSET_MAP.get(name)
    if not mapping:
        return _insufficient_asset(asset, "資産と気団の対応関係が未定義である。")
    primary = mapping["primary"]
    secondary = mapping.get("secondary")
    primary_state, primary_strong, primary_weak = _air_state(market, primary)
    secondary_state, secondary_strong, secondary_weak = _air_state(market, secondary)
    flow_direction, flow_score = _flow_lookup(market, mapping["flows"])
    regime = market.get("regime", {}) if isinstance(market.get("regime"), Mapping) else {}
    primary_observed = primary in _conditions(market) or primary in {regime.get("dominant_air_mass"), regime.get("secondary_air_mass")}
    if not primary_observed and flow_direction is None:
        return _insufficient_asset(asset, f"{primary}気団と関連フローが欠損しているため照合できない。")
    weak, role_weak = _asset_is_weak(asset), _role_is_weak(asset)
    up, down = flow_direction == "updrafts", flow_direction == "downdrafts"
    label = "context_supported"
    reason = "資産状態は主要な市場文脈と概ね整合している。"

    if name == "BTC" and str((market.get("btc_sensor") or {}).get("mode", "")).lower() == "risk_on" and (weak or down):
        label, reason = "context_divergence", "BTCセンサーがrisk_onを示す一方、BTCは弱いか下降流にあり、市場文脈と乖離している。"
    elif name == "TLT" and weak:
        if primary_strong:
            label, reason = "role_failure_candidate", "防衛気団が強い局面でTLTが弱く、防衛役割の不全候補である。"
        elif secondary_strong:
            label, reason = "context_explained_weakness", "利回り気団の強さがTLTの弱さを説明している。"
        else:
            label, reason = "role_activation_absent", "防衛気団が弱く、TLTの役割が発動する環境ではない。"
    elif name == "GLDM" and weak and down:
        label, reason = "context_explained_weakness", "金フローが下降しており、GLDMの弱さは市場文脈で説明できる。"
    elif name == "XLRE" and weak and up:
        label, reason = "context_divergence", "REITフローが上昇している一方でXLREが弱く、市場文脈と乖離している。"
    elif name == "BNDX" and weak and primary_strong:
        label, reason = "role_failure_candidate", "防衛気団が強い局面でBNDXが弱く、役割不全候補である。"
    elif name in {"TIP", "DBC"} and weak and primary_strong and role_weak:
        label, reason = "role_failure_candidate", f"{primary}気団が強い局面で役割性能も弱く、役割不全候補である。"
    elif name == "GLDM" and weak and (primary_strong or secondary_strong) and role_weak:
        label, reason = "role_failure_candidate", "防衛またはインフレ気団が強い局面でGLDMの役割性能が弱く、役割不全候補である。"
    elif weak and primary_strong:
        label, reason = "context_divergence", f"{primary}気団が強い一方で{name}が弱く、市場文脈と乖離している。"
    elif weak and (primary_weak or down):
        label, reason = "context_explained_weakness", f"{primary}気団または関連フローの下降が{name}の弱さを説明している。"
    elif weak and not primary_strong:
        label, reason = "role_activation_absent", f"{primary}気団が強くなく、{name}の主要役割が発動する環境ではない。"
    elif primary_strong or up:
        reason = f"{primary}気団または関連フローの強さと{name}の健全性が整合している。"

    severity = "low"
    if weak and label == "context_explained_weakness":
        severity = "medium"
    elif weak and label in {"context_divergence", "role_failure_candidate"}:
        severity = "high"
    elif weak:
        severity = "medium"
    if name == "TLT" and "複合負傷" in str(asset.get("injury_type", "")):
        severity = _increase_severity(severity)

    notes = []
    if asset.get("is_opportunity"):
        notes.append("opportunity_context: El Shaddaiの機会判定を市場文脈と併記する。")
    if name == "BTC" and _oracle_uses_fallback(asset.get("oracle_details", {})):
        confidence = _lower_confidence(confidence)
        notes.append("O.R.A.C.L.E.入力がneutral fallbackを含むためconfidenceを1段階下げた。")
    special = _has_warning(asset, "currency", "order", "real_rate_shock", "macro_submission", "credit_stress", "reit_relative_strength")
    notes.extend(f"確認対象: {item}" for item in special)
    if name == "DBC" and weak and not role_weak:
        notes.append("役割性能は維持されているが、価格が市場文脈に押されている。")

    return {
        "asset": name,
        "context_label": label,
        "severity": severity,
        "confidence": confidence,
        "relevant_warnings": list(relevant_warnings),
        "market_evidence": {
            "primary_air_mass": primary,
            "primary_air_mass_state": primary_state,
            "secondary_air_mass": secondary,
            "secondary_air_mass_state": secondary_state if secondary else None,
            "flow_direction": flow_direction,
            "flow_score": flow_score,
            "market_warnings": list(market.get("market_warnings", []) or []),
        },
        "asset_evidence": {key: asset.get(key) for key in ("score", "price_score", "role_score", "final_score", "status", "role_status", "injury_type", "is_injured", "is_opportunity")},
        "interpretation": reason,
        "notes": notes,
        "next_check": f"次回監査で{primary}気団、関連フロー、{name}の資産状態が再整合するか確認する。",
    }


def _insufficient_asset(asset: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "asset": str(asset.get("asset", "unknown")), "context_label": "insufficient_context", "severity": "medium", "confidence": "low",
        "relevant_warnings": [], "market_evidence": {}, "asset_evidence": dict(asset), "interpretation": reason, "notes": [], "next_check": "不足している入力を補完して再判定する。",
    }


def _group_contexts(audit: Mapping[str, Any], contexts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_asset = {str(item.get("asset")): item for item in contexts}
    groups: dict[str, Any] = {}
    for key, group in (audit.get("role_groups", {}) or {}).items():
        if not isinstance(group, Mapping):
            continue
        assets = [str(asset) for asset in group.get("assets", [])]
        labels = [by_asset[asset]["context_label"] for asset in assets if asset in by_asset]
        group_warnings = list(dict.fromkeys(
            warning
            for asset in assets
            for warning in by_asset.get(asset, {}).get("relevant_warnings", [])
            if key != "inflation_defense" or "i.n.f.e.r.n.o." not in warning.lower()
        ))
        if key == "inflation_defense":
            group_warnings.extend(
                warning for warning in audit.get("warnings", []) or []
                if "i.n.f.e.r.n.o." in str(warning).lower() and warning not in group_warnings
            )
        groups[str(key)] = {"label": group.get("label", key), "assets": assets, "context_labels": labels, "warnings": group_warnings, "high_attention": any(label in {"context_divergence", "role_failure_candidate"} for label in labels)}
    return groups


def build_parallax_report(market: Mapping[str, Any] | None, audit: Mapping[str, Any] | None, *, warnings: Sequence[str] = (), generated_at: datetime | str | None = None) -> dict[str, Any]:
    """Build a Parallax report without rewriting either source system's values."""
    generated_at = generated_at or datetime.now(timezone.utc)
    timestamp = generated_at.isoformat() if isinstance(generated_at, datetime) else str(generated_at)
    all_warnings = list(warnings)
    if market is not None:
        all_warnings.extend(str(item) for item in market.get("market_warnings", []) or [])
    if audit is not None:
        all_warnings.extend(str(item) for item in audit.get("warnings", []) or [])
    all_warnings = list(dict.fromkeys(all_warnings))
    if market is None:
        all_warnings.append("Market Amedas入力が欠損している。")
    if audit is None:
        all_warnings.append("El Shaddai入力が欠損している。")
    market, audit = market or {}, audit or {}
    assets = audit.get("assets", []) if isinstance(audit.get("assets"), list) else []
    source_warnings = list(market.get("market_warnings", []) or []) + list(audit.get("warnings", []) or [])
    global_critical = _global_critical_warnings(market, audit, warnings)
    if audit and not assets:
        global_critical.append("El Shaddai assets are missing; asset_contexts cannot be built")
    if not market:
        contexts = [_insufficient_asset(asset, "Market Amedas入力が欠損しているため照合できない。") for asset in assets]
    else:
        contexts = []
        for asset in assets:
            if not isinstance(asset, Mapping):
                continue
            name = str(asset.get("asset", ""))
            relevant = _relevant_warnings(name, source_warnings, asset)
            confidence = _asset_confidence(global_critical, relevant)
            contexts.append(_classify_asset(asset, market, confidence, relevant))
    regime = market.get("regime", {}) if isinstance(market.get("regime"), Mapping) else {}
    el_summary = audit.get("summary", {}) if isinstance(audit.get("summary"), Mapping) else {}
    by_label = lambda label: [item["asset"] for item in contexts if item["context_label"] == label]
    divergence = by_label("context_divergence")
    failures = by_label("role_failure_candidate")
    insufficient = by_label("insufficient_context")
    if audit == {}:
        insufficient.append("el_shaddai")
    elif not assets:
        insufficient.append("el_shaddai_assets")
    if market == {} and not insufficient:
        insufficient.append("market_amedas")
    critical_candidate = str(el_summary.get("overall_state", "")).startswith("0.") and len(divergence) > 1
    if critical_candidate:
        for item in contexts:
            if item["context_label"] == "context_divergence":
                item["severity"] = "critical"
    summary = {
        "overall_context": f"{regime.get('dominant_air_mass', 'unknown')}_{regime.get('secondary_air_mass', 'unknown')}",
        "dominant_market_regime": regime.get("dominant_air_mass"),
        "secondary_market_regime": regime.get("secondary_air_mass"),
        "el_shaddai_state": el_summary.get("overall_state"),
        "parallax_state": "insufficient_context" if insufficient else ("context_mixed" if divergence or failures else "context_aligned"),
        "high_attention_assets": [item["asset"] for item in contexts if item["severity"] in {"high", "critical"}],
        "explained_weakness_assets": by_label("context_explained_weakness"),
        "divergence_assets": divergence,
        "role_failure_candidates": failures,
        "insufficient_context": insufficient,
    }
    return {
        "schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "generated_at": timestamp,
        "input_versions": {"market_amedas": market.get("schema_version"), "el_shaddai": audit.get("schema_version")},
        "data_status": {"market_amedas_available": bool(market), "el_shaddai_available": bool(audit), "source_market_status": market.get("data_status", {}), "source_audit_completeness": audit.get("audit_completeness", {})},
        "summary": summary, "asset_contexts": contexts, "group_contexts": _group_contexts(audit, contexts),
        "global_critical_warnings": global_critical,
        "market_findings": list(market.get("market_warnings", []) or []), "warnings": all_warnings,
        "next_check_items": list(audit.get("next_audit_items", []) or []),
        "safety": {"advisory_only": True, "automatic_trading": False, "automatic_selling": False, "allocation_change": False, "score_rewrite": False, "notice": SAFETY_NOTICE},
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary, status = report["summary"], report["data_status"]
    lines = [f"# Parallax Context Report v{ENGINE_VERSION}", "", "## 1. 結論サマリー", f"- Parallax状態: {summary['parallax_state']}", f"- 高注意資産: {', '.join(summary['high_attention_assets']) or 'なし'}", "", "## 2. 市場天候の要約", f"- 主気団: {summary.get('dominant_market_regime') or '不明'}", f"- 副気団: {summary.get('secondary_market_regime') or '不明'}", f"- Market Amedas入力: {'あり' if status['market_amedas_available'] else 'なし'}", "", "## 3. El Shaddai状態の要約", f"- 全体状態: {summary.get('el_shaddai_state') or '不明'}", f"- El Shaddai入力: {'あり' if status['el_shaddai_available'] else 'なし'}", "", "## 4. 資産別Parallax判定", "| Asset | Context | Severity | Confidence | Interpretation |", "| --- | --- | --- | --- | --- |"]
    for item in report["asset_contexts"]:
        lines.append(f"| {item['asset']} | {item['context_label']} | {item['severity']} | {item['confidence']} | {item['interpretation']} |")
    lines += ["", "## 5. 役割グループ別Parallax判定"]
    for key, group in report["group_contexts"].items():
        warning_note = f" / 関連warning: {', '.join(group.get('warnings', []))}" if group.get("warnings") else ""
        lines.append(f"- {group['label']} ({key}): {', '.join(group['context_labels']) or '判定なし'}{warning_note}")
    lines += ["", "## 6. 注意点"] + [f"- {item}" for item in report["warnings"] or ["特記事項なし"]]
    lines += ["", "## 7. 次回確認項目"] + [f"- {item}" for item in report["next_check_items"] or ["不足入力と高注意資産を次回監査で確認する。"]]
    lines += ["", "## 8. 安全境界", f"- {SAFETY_NOTICE}", "- スコア、気団比率、負傷分類を書き換えない。", "- 予測リターンの断定や投資助言としての売買推奨を行わない。", ""]
    return "\n".join(lines)


def write_parallax_outputs(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path, md_path = destination / "parallax_context_report.json", destination / "parallax_context_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def run_parallax(market_path: str | Path | None, audit_path: str | Path | None, output_dir: str | Path) -> dict[str, Path]:
    market, market_warnings = _load_json(market_path, MARKET_SCHEMA_VERSION)
    audit, audit_warnings = _load_json(audit_path, EL_SHADDAI_SCHEMA_VERSION)
    return write_parallax_outputs(build_parallax_report(market, audit, warnings=market_warnings + audit_warnings), output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare Market Amedas and El Shaddai JSON without rewriting source scores.")
    parser.add_argument("--market-amedas", default="market_amedas_snapshot.json")
    parser.add_argument("--el-shaddai", default="el_shaddai_lumus8_audit.json")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args(argv)
    for name, path in run_parallax(args.market_amedas, args.el_shaddai, args.output_dir).items():
        print(f"Wrote {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
