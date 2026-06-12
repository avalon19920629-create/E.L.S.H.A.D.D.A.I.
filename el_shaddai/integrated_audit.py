"""L.U.M.U.S.-8 の白箱型・助言専用統合監査層 v2.0。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping

from .labels import ACTION_LABELS_JA, CONFIDENCE_LABELS_JA, GLOBAL_JUDGMENT_LABELS_JA, HEALTH_LABELS_JA, WOUND_TYPE_LABELS_JA
from .market_context_adapter import adapt_market_context
from .models import AssetAuditInput, MarketAmedasInput, PortfolioInput
from .report_renderer import render_integrated_report
from .text_sanitizer import safe_print, sanitize_output_text

ROLE_GROUPS = {
    "成長・攻撃": ["VT", "BTC"], "景気後退防衛": ["TLT", "BNDX"], "インフレ防衛": ["TIP", "DBC", "GLDM"],
    "実物資産・利回り": ["XLRE", "GLDM", "DBC"], "危機時退避": ["GLDM", "BNDX", "TLT", "BTC"],
}
STRUCTURAL_FLAGS = {"role_impairment", "correlation_breakdown", "systemic_contagion", "safe_haven_failure", "inflation_hedge_failure", "growth_divergence", "credit_stress"}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def health_level_for(score: float) -> int:
    return 5 if score >= 90 else 4 if score >= 75 else 3 if score >= 60 else 2 if score >= 45 else 1 if score >= 30 else 0


def global_level_for(score: float) -> int:
    return 5 if score >= 85 else 4 if score >= 75 else 3 if score >= 65 else 2 if score >= 55 else 1 if score >= 45 else 0


def normalized_confidence_level(level: int | None) -> int:
    """欠損値を通常、範囲外値を公開ラベルの 1..5 に正規化する。"""
    return max(1, min(5, int(level if level is not None else 3)))


def confidence_multiplier(level: int | None) -> float:
    return {5: 1.05, 4: 1.02, 3: 1.0, 2: 0.92, 1: 0.85}[normalized_confidence_level(level)]


def penalty_multiplier(flags: Iterable[str], explicit_wound: int | None) -> float:
    flags = set(flags)
    if explicit_wound == 3 or "systemic_contagion" in flags: return 0.50
    if explicit_wound == 2 or len(flags & STRUCTURAL_FLAGS) >= 2: return 0.75
    if explicit_wound == 1 or flags & STRUCTURAL_FLAGS: return 0.90
    return 1.0


def classify_wound(score: float, risk_flags: Iterable[str], explicit: int | None = None) -> int:
    if explicit is not None: return max(0, min(3, explicit))
    flags = set(risk_flags)
    structural = bool(flags & STRUCTURAL_FLAGS)
    if score >= 75: return 0
    if score >= 60: return 1 if structural else 0
    if score >= 45: return 2 if structural else 1
    if score >= 30: return 2
    return 3


def _numeric_metric(metrics: Mapping[str, Any], name: str) -> float | None:
    value = metrics.get(name)
    return float(value) if isinstance(value, (int, float)) else None


def _injury_type(audit: AssetAuditInput, wound_level: int) -> str:
    """価格・役割・構造の証拠から、負傷の原因をwound_levelとは独立に分類する。"""
    if audit.audit_engine == "O.R.A.C.L.E.":
        return "追加買い判定" if wound_level > 0 else "機会判定"
    if wound_level == 0:
        return "負傷なし"

    metrics = audit.supporting_metrics
    price_score = _numeric_metric(metrics, "price_score")
    role_score = _numeric_metric(metrics, "role_score")
    final_score = _numeric_metric(metrics, "final_score")
    structural = bool(set(audit.risk_flags) & STRUCTURAL_FLAGS)
    if structural or wound_level == 3 or (final_score is not None and final_score < 30):
        return "構造負傷"

    # classify_woundと同じ60点を、価格・役割の単独/複合要因を分ける境界に使う。
    if price_score is not None and role_score is not None:
        price_low = price_score < 60
        role_low = role_score < 60
        if price_low and role_low:
            return "複合負傷"
        if price_low:
            return "価格負傷"
        if role_low:
            return "役割負傷"

    # supporting_metricsを持たない既存入力との互換性を維持する。
    return {1: "価格負傷", 2: "役割負傷", 3: "構造負傷"}[wound_level]


def _one_line_summary(text: str, injury_type: str) -> str:
    """詳細なproxy理由文を統合報告書用の一行へ縮約する。"""
    cleaned = " ".join(sanitize_output_text(text).split()).strip(" ;")
    if not cleaned:
        return "追加買い機会を継続確認" if injury_type in {"機会判定", "追加買い判定"} else "継続監査対象"
    # 診断ログの列挙はasset report側に残し、統合報告書では先頭の論点だけを示す。
    summary = cleaned.split(";", 1)[0].split("。", 1)[0]
    return summary if len(summary) <= 72 else summary[:69].rstrip() + "..."


def _display_status(audit_engine: str, wound_level: int, health_label: str, injury_type: str) -> str:
    """機会・負傷表示を、別系統の役割健全度ラベルから分離する。"""
    if audit_engine == "O.R.A.C.L.E.":
        return "追加買い候補" if wound_level > 0 else "機会中立"
    return injury_type if injury_type == "価格負傷" else health_label


def _recommended_action(injury_type: str) -> str:
    if injury_type == "追加買い判定":
        return "既存ルール内で追加買い機会を確認"
    if injury_type in {"価格負傷", "役割負傷", "複合負傷", "構造負傷"}:
        return "次回監査で重点確認"
    return "固定比率と既存ルールを維持"


def _xlre_price_warning_interpretation(audit: AssetAuditInput) -> dict[str, Any] | None:
    """高値圏によるXLREの低スコアを、構造崩壊とは分けて表示する。"""
    if audit.asset != "XLRE" or audit.audit_engine != "A.R.C.A.D.I.A.":
        return None
    metrics = audit.supporting_metrics
    price_score = metrics.get("price_score")
    role_score = metrics.get("role_score")
    final_score = metrics.get("final_score", audit.role_health_score)
    core_score = metrics.get("core_score")
    role_components = metrics.get("role_components", {})
    price_components = metrics.get("price_components", {})
    role_components = role_components if isinstance(role_components, Mapping) else {}
    price_components = price_components if isinstance(price_components, Mapping) else {}
    rental_cashflow = metrics.get("rental_cashflow", role_components.get("rental_cashflow"))
    numeric = (price_score, role_score, final_score, core_score, rental_cashflow)
    if not all(isinstance(value, (int, float)) for value in numeric):
        return None

    # Price component scores are opportunity scores: low values mean high/overheated prices.
    elevated_price_signals = [
        name for name, threshold in {
            "range_52w_position": 25.0, "z_score": 25.0, "weekly_drawdown": 25.0, "range_5y_position": 40.0,
        }.items()
        if isinstance(price_components.get(name), (int, float)) and float(price_components[name]) <= threshold
    ]
    price_is_driver = float(price_score) <= float(role_score) and abs(float(price_score) - float(final_score)) <= 0.01
    core_function_remains = float(rental_cashflow) >= 60.0 and float(core_score) >= 50.0
    if not (price_is_driver and core_function_remains and len(elevated_price_signals) >= 2):
        return None

    return {
        "display_status": "構造逆風",
        "injury_type": "価格警戒＋役割逆風",
        "one_line_summary": "高値圏で追加買い妙味は低いが、地代機能は残存。金利・信用・REIT相対強度を重点確認。",
        "recommended_action": "売却ではなく、次回監査で金利・信用・REIT相対強度を重点確認",
        "interpretation_notes": [
            "価格警戒：高値圏 / 追加買い非推奨",
            "役割逆風：金利・信用・相対劣後",
            "中核機能：地代キャッシュフロー機能は残存",
            "構造崩壊ではなく、価格警戒と外部環境逆風の複合判定",
            "低スコアは自動売却を意味しない",
        ],
        "next_checkpoint": "XLREは売却ではなく、次回監査で金利・信用・REIT相対強度を重点確認する。",
    }


def _next_checkpoint(row: dict[str, Any]) -> str:
    """機会判定と本物の負傷判定を混同せず、次回監査項目を作る。"""
    if row.get("next_checkpoint"):
        return row["next_checkpoint"]
    if row["injury_type"] == "追加買い判定":
        return f"{row['asset']}の追加買い候補判定が継続するか確認する。"
    if row["injury_type"] == "機会判定":
        return f"{row['asset']}の機会判定が継続するか確認する。"
    return f"{row['asset']}の{row['injury_type']}が継続するか確認する。"


def _correlation_integrity(audits: list[AssetAuditInput]) -> tuple[float, bool]:
    values = [float(a.supporting_metrics["correlation_integrity_score"]) for a in audits if "correlation_integrity_score" in a.supporting_metrics]
    return (clamp(mean(values)), True) if values else (100.0, False)


def _role_diagnosis(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """役割グループを、資産全体の健全度ではなく役割証拠で診断する。"""
    by_asset = {row["asset"]: row for row in rows}
    result = {}
    for group, assets in ROLE_GROUPS.items():
        scores = [by_asset[a]["role_evidence_score"] for a in assets if a in by_asset]
        score = mean(scores) if scores else 0.0
        level = health_level_for(score)
        result[group] = {"score": round(score, 1), "level": level, "label": HEALTH_LABELS_JA[level], "assets": assets}
    return result


FRED_ASSETS = {"TLT", "TIP"}


def _data_completeness(
    *, market_amedas_available: bool, correlation_available: bool, runtime: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize non-secret runtime status for the human-readable audit report."""
    runtime = runtime or {}
    degraded = sorted({str(asset) for asset in runtime.get("degraded_assets", [])})
    failed = sorted({str(asset) for asset in runtime.get("failed_adapters", [])})
    if FRED_ASSETS.intersection(failed):
        fred_status = "failed"
    elif FRED_ASSETS.intersection(degraded):
        fred_status = "degraded"
    else:
        fred_status = "OK"
    missing_context = []
    if not market_amedas_available:
        missing_context.append("Market Amedas未入力")
    if not correlation_available:
        missing_context.append("相関構造未入力")
    return {
        "price_data_status": "OK",
        "fred_data_status": fred_status,
        "fred_provider": runtime.get("fred_provider"),
        "market_amedas_available": market_amedas_available,
        "correlation_available": correlation_available,
        "audit_integrity": "暫定監査" if missing_context else "統合監査",
        "audit_context_status": "文脈未接続監査" if missing_context else "文脈接続済み",
        "audit_integrity_reasons": missing_context,
        "degraded_adapters": degraded,
        "failed_adapters": failed,
    }


def run_integrated_audit(
    asset_audits: Iterable[AssetAuditInput], portfolio: PortfolioInput, market_amedas: MarketAmedasInput | None = None,
    *, data_runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """8資産の役割監査を集約する。返す運用判断は助言であり、自動執行しない。"""
    audits = list(asset_audits)
    if not audits: raise ValueError("asset_audits は1件以上必要です")
    context = adapt_market_context(market_amedas)
    rows: list[dict[str, Any]] = []
    for audit in audits:
        regime = context.regime_relevance_adjustments.get(audit.asset, 1.0)
        penalty = penalty_multiplier(audit.risk_flags, audit.wound_level)
        confidence_level = normalized_confidence_level(audit.confidence_level)
        role_evidence_score = round(clamp(audit.role_health_score * penalty), 2)
        final_score = _numeric_metric(audit.supporting_metrics, "final_score")
        final_score = final_score if final_score is not None else audit.role_health_score
        asset_internal_score = round(clamp(final_score * penalty * confidence_multiplier(confidence_level)), 2)
        asset_health_score = round(clamp(asset_internal_score * regime), 2)
        internal_role_score = round(clamp(role_evidence_score * confidence_multiplier(confidence_level)), 2)
        asset_level = health_level_for(asset_health_score)
        role_level = health_level_for(internal_role_score)
        # 市場気象や低信頼だけでは負傷としない。負傷度はfinal scoreと構造フラグで判定する。
        wound = classify_wound(round(clamp(final_score * penalty), 2), audit.risk_flags, audit.wound_level)
        injury_type = _injury_type(audit, wound)
        row = {
            "asset": audit.asset, "audit_engine": audit.audit_engine, "asset_health_score": asset_health_score, "internal_health_score": asset_internal_score, "role_evidence_score": role_evidence_score, "internal_role_health_score": internal_role_score, "health_level": asset_level,
            "health_label": HEALTH_LABELS_JA[asset_level], "display_status": _display_status(audit.audit_engine, wound, HEALTH_LABELS_JA[asset_level], injury_type), "role_status": HEALTH_LABELS_JA[role_level], "role_health_label": HEALTH_LABELS_JA[role_level], "wound_level": wound, "wound_label": WOUND_TYPE_LABELS_JA[wound], "injury_type": injury_type,
            "confidence_level": confidence_level, "confidence_label": CONFIDENCE_LABELS_JA[confidence_level],
            "diagnosis_summary": audit.diagnosis_summary, "one_line_summary": _one_line_summary(audit.diagnosis_summary, injury_type), "recommended_action": _recommended_action(injury_type),
            "interpretation_notes": [], "risk_flags": list(audit.risk_flags), "multipliers": {"regime_relevance": regime, "confidence": confidence_multiplier(audit.confidence_level), "penalty": penalty},
        }
        xlre_interpretation = _xlre_price_warning_interpretation(audit)
        if xlre_interpretation:
            row.update(xlre_interpretation)
        rows.append(row)
    rows.sort(key=lambda row: row["asset_health_score"], reverse=True)
    opportunity_judgments = [row for row in rows if row["audit_engine"] == "O.R.A.C.L.E."]
    wounded = [row for row in rows if row["wound_level"] > 0 and row["audit_engine"] != "O.R.A.C.L.E."]

    weights = {asset: max(0.0, float(weight)) for asset, weight in portfolio.target_weights.items()}
    total_weight = sum(weights.get(row["asset"], 0) for row in rows)
    weighted_health = (sum(row["asset_health_score"] * weights.get(row["asset"], 0) for row in rows) / total_weight) if total_weight else mean(row["asset_health_score"] for row in rows)
    internal_weighted_health = (sum(row["internal_role_health_score"] * weights.get(row["asset"], 0) for row in rows) / total_weight) if total_weight else mean(row["internal_role_health_score"] for row in rows)
    present = {row["asset"] for row in rows}
    coverage = mean(sum(asset in present for asset in assets) / len(assets) for assets in ROLE_GROUPS.values())
    role_coverage_factor = 0.70 + 0.30 * coverage
    correlation_score, correlation_available = _correlation_integrity(audits)
    correlation_factor = 0.70 + 0.30 * correlation_score / 100
    normalized_weights = [weight / sum(weights.values()) for weight in weights.values()] if sum(weights.values()) else []
    max_weight = max(normalized_weights, default=0)
    concentration_penalty = max(0.80, 1.0 - max(0.0, max_weight - 0.35) * 0.5)
    sanctuary = round(clamp(weighted_health * role_coverage_factor * correlation_factor * concentration_penalty), 1)
    internal_sanctuary = round(clamp(internal_weighted_health * role_coverage_factor * correlation_factor * concentration_penalty), 1)

    global_level = global_level_for(sanctuary)
    internal_global_level = global_level_for(internal_sanctuary)
    severe = [row for row in rows if row["wound_level"] >= 2]
    collapsed = [row for row in rows if row["wound_level"] == 3]
    defense_wounded = sum(next((r["wound_level"] >= 2 for r in rows if r["asset"] == a), False) for a in ("TLT", "BNDX", "GLDM"))
    inflation_wounded = sum(next((r["wound_level"] >= 2 for r in rows if r["asset"] == a), False) for a in ("TIP", "DBC", "GLDM"))
    if len(severe) >= 2:
        global_level = min(global_level, 2)
        internal_global_level = min(internal_global_level, 2)
    if collapsed or correlation_score < 60:
        global_level = min(global_level, 1)
        internal_global_level = min(internal_global_level, 1)
    if defense_wounded >= 2 or inflation_wounded >= 2:
        global_level = min(global_level, 2)
        internal_global_level = min(internal_global_level, 2)
    by_asset = {row["asset"]: row for row in rows}
    growth_strong = all(by_asset.get(asset, {}).get("asset_health_score", 0) >= 75 for asset in ("VT", "BTC"))
    defense_broadly_weak = sum(by_asset.get(asset, {}).get("asset_health_score", 100) < 60 for asset in ("TLT", "BNDX", "GLDM")) >= 2
    if growth_strong and defense_broadly_weak:
        global_level = min(global_level, 2)
        internal_global_level = min(internal_global_level, 2)

    contextual_action_candidate = {5: 0, 4: 0, 3: 1, 2: 2, 1: 3, 0: 4}[global_level]
    raw_action = contextual_action_candidate
    internal_action = {5: 0, 4: 0, 3: 1, 2: 2, 1: 3, 0: 4}[internal_global_level]
    market_context_safety_note = ""
    if raw_action >= 2 and internal_action < 2:
        raw_action = 1
        market_context_safety_note = "市場文脈反映後は補正候補だが、内部役割監査が裏付けていないため監視強化に限定する。"
    average_confidence = mean(row["confidence_level"] for row in rows)
    confidence_note = ""
    if average_confidence <= 2 and raw_action in (2, 3):
        raw_action = 1
        confidence_note = "平均信頼度が低いため、強い補正判断を避けて監視を継続する。"
    action = raw_action
    hysteresis_note = confidence_note
    if raw_action in (2, 3) and (portfolio.previous_action_level is None or portfolio.previous_action_level < 2):
        action = 1
        hysteresis_note = f"{ACTION_LABELS_JA[raw_action]}候補だが、同一警戒判定が2回連続していないため監視継続。"

    role_group_diagnosis = _role_diagnosis(rows)
    watch_groups = [group for group, diagnosis in role_group_diagnosis.items() if diagnosis["level"] <= 3]
    recommended = ["固定比率と既存の乖離ルールを維持する。"]
    if wounded:
        recommended.append("負傷アセットを次回監査で重点確認する。")
    if watch_groups:
        recommended.append(f"{'・'.join(watch_groups)}グループを次回監査で確認する。")
    if context.btc_divergence_note:
        recommended.append(context.btc_divergence_note)
    if action >= 2: recommended.append("継続警戒を確認したうえで、既存ルール内の補正を人間が検討する。")
    elif action == 1: recommended.append("配分変更を急がず、監視頻度を上げる。")
    not_recommended = ["Market Amedasの市場気象のみを理由に売却しない。", "低スコア資産を機械的に売却しない。", "監査結果から自動売買を実行しない。"]
    checkpoints = [_next_checkpoint(row) for row in [*opportunity_judgments, *wounded[:4]]]
    if context.btc_divergence_note: checkpoints.append("BTCが成長気団に再連動するか確認する。")
    if "defense_air_mass_absent" in context.market_context_flags: checkpoints.append("TLTとBNDXが景気後退防衛として機能しているか確認する。")
    if "gold_commodity_weakness" in context.market_context_flags: checkpoints.append("GLDM・DBCの弱さが局面不適合か、役割劣化かを確認する。")
    if not correlation_available: checkpoints.append("VT/TLT、VT/GLDM、VT/BTCの相関構造を確認する。")

    injury_breakdown: dict[str, int] = {}
    for row in wounded:
        injury_breakdown[row["injury_type"]] = injury_breakdown.get(row["injury_type"], 0) + 1
    opening_caveats = []
    if market_amedas is None:
        opening_caveats.append("市場文脈補正なし")
    if not correlation_available:
        opening_caveats.append("危機時分散評価なし")

    result: dict[str, Any] = {
        "sanctuary_health_score": sanctuary, "internal_sanctuary_health_score": internal_sanctuary, "global_judgment_level": global_level, "global_judgment_label": GLOBAL_JUDGMENT_LABELS_JA[global_level],
        "lumus_global_judgment": {"level": global_level, "label": GLOBAL_JUDGMENT_LABELS_JA[global_level]},
        "contextual_action_candidate_level": contextual_action_candidate, "internal_action_level": internal_action,
        "raw_action_level": raw_action, "action_level": action, "action_label": ACTION_LABELS_JA[action],
        "portfolio_adjustment_recommendation": {"level": action, "label": ACTION_LABELS_JA[action], "advisory_only": True},
        "hysteresis_note": hysteresis_note, "market_context_safety_note": market_context_safety_note, "asset_health_rank": rows, "wounded_assets": wounded, "opportunity_judgments": opportunity_judgments, "injury_breakdown": injury_breakdown, "opening_caveats": opening_caveats, "role_group_diagnosis": role_group_diagnosis,
        "market_context": asdict(context), "market_context_summary": context.market_context_summary,
        "recommended_actions": recommended, "not_recommended_actions": not_recommended, "next_checkpoints": checkpoints,
        "data_completeness": _data_completeness(market_amedas_available=market_amedas is not None, correlation_available=correlation_available, runtime=data_runtime),
        "correlation_integrity_score": correlation_score if correlation_available else None,
        "correlation_diagnosis": f"相関健全度：{correlation_score:.1f} / 100。" if correlation_available else "相関データ未提供のため、中立値 1.00 を使用した。今回のスコアには、危機時分散の実測評価は含まれていない。",
        "components": {"weighted_asset_health": round(weighted_health, 2), "internal_weighted_asset_health": round(internal_weighted_health, 2), "role_coverage_factor": round(role_coverage_factor, 3), "correlation_integrity_factor": round(correlation_factor, 3), "concentration_penalty": round(concentration_penalty, 3)},
    }
    result["report_text"] = render_integrated_report(result)
    return result


def _demo_inputs(scenario: str) -> tuple[list[AssetAuditInput], PortfolioInput, MarketAmedasInput]:
    assets = [("VT", "O.R.A.C.L.E.", 84), ("BTC", "O.R.A.C.L.E.", 70), ("TLT", "L.O.D.E.", 62), ("TIP", "I.N.F.E.R.N.O.", 79), ("GLDM", "A.U.R.A.", 88), ("XLRE", "A.R.C.A.D.I.A.", 68), ("BNDX", "A.T.L.A.S.", 76), ("DBC", "G.A.I.A.", 72)]
    audits = [AssetAuditInput(a, e, s, confidence_level=4, diagnosis_summary="デモ用役割監査") for a, e, s in assets]
    portfolio = PortfolioInput({a: 1 / 8 for a, _, _ in assets})
    if scenario == "market_amedas_20260606":
        market = MarketAmedasInput(
            {"yield": 50.2, "growth": 44.7, "defense": 4.4, "inflation": 0.7},
            {"usd_wind": "凪（影響なし）", "junk_oxygen": "正常（健全な上昇）", "smallcap_geothermal": "温暖（景気回復は本物）"},
            {"value": 0.48, "nasdaq": 0.41, "high_dividend": 0.37, "reit": 0.36, "us_equity": 0.33, "smallcap": 0.28, "junk": 0.17, "developed": 0.17, "tlt": 0.13, "emerging": 0.12, "corporate_bond": 0.08, "inflation_linked": 0.02},
            {"cash": 0.00, "commodity": -0.14, "gold": -0.28, "btc": -0.54},
            "デジタルゴールド (Summer) モード",
        )
    else:
        market = MarketAmedasInput({"yield": 60, "growth": 70, "defense": 35, "inflation": 45}, {}, {}, {}, "neutral")
    return audits, portfolio, market


def _demo(scenario: str = "default") -> int:
    audits, portfolio, market = _demo_inputs(scenario)
    result = run_integrated_audit(audits, portfolio, market)
    filename = "el_shaddai_integrated_audit_report.md" if scenario == "default" else f"el_shaddai_integrated_audit_{scenario}.md"
    path = Path("artifacts/demo") / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize_output_text(result["report_text"]), encoding="utf-8")
    safe_print(result["report_text"], end="")
    safe_print(f"保存先: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="El Shaddai v2.0 統合監査")
    parser.add_argument("--demo", action="store_true", help="日本語のサンプル統合監査報告書を生成する")
    parser.add_argument("--scenario", choices=("default", "market_amedas_20260606"), default="default", help="デモで使用する市場シナリオ")
    args = parser.parse_args()
    if args.demo: return _demo(args.scenario)
    parser.error("現在は --demo を指定してください")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
