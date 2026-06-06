"""L.U.M.U.S.-8 の白箱型・助言専用統合監査層 v2.0。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from .labels import ACTION_LABELS_JA, CONFIDENCE_LABELS_JA, GLOBAL_JUDGMENT_LABELS_JA, HEALTH_LABELS_JA, WOUND_TYPE_LABELS_JA
from .market_context_adapter import adapt_market_context
from .models import AssetAuditInput, MarketAmedasInput, PortfolioInput
from .report_renderer import render_integrated_report

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


def _correlation_integrity(audits: list[AssetAuditInput]) -> tuple[float, bool]:
    values = [float(a.supporting_metrics["correlation_integrity_score"]) for a in audits if "correlation_integrity_score" in a.supporting_metrics]
    return (clamp(mean(values)), True) if values else (100.0, False)


def _role_diagnosis(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_asset = {row["asset"]: row for row in rows}
    result = {}
    for group, assets in ROLE_GROUPS.items():
        scores = [by_asset[a]["asset_health_score"] for a in assets if a in by_asset]
        score = mean(scores) if scores else 0.0
        level = health_level_for(score)
        result[group] = {"score": round(score, 1), "level": level, "label": HEALTH_LABELS_JA[level], "assets": assets}
    return result


def run_integrated_audit(asset_audits: Iterable[AssetAuditInput], portfolio: PortfolioInput, market_amedas: MarketAmedasInput | None = None) -> dict[str, Any]:
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
        internal_score = round(clamp(role_evidence_score * confidence_multiplier(confidence_level)), 2)
        score = round(clamp(internal_score * regime), 2)
        level = health_level_for(score)
        # 市場気象や低信頼だけでは負傷としない。負傷は役割証拠と構造フラグで判定する。
        wound = classify_wound(role_evidence_score, audit.risk_flags, audit.wound_level)
        rows.append({
            "asset": audit.asset, "audit_engine": audit.audit_engine, "asset_health_score": score, "internal_health_score": internal_score, "role_evidence_score": role_evidence_score, "health_level": level,
            "health_label": HEALTH_LABELS_JA[level], "wound_level": wound, "wound_label": WOUND_TYPE_LABELS_JA[wound],
            "confidence_level": confidence_level, "confidence_label": CONFIDENCE_LABELS_JA[confidence_level],
            "diagnosis_summary": audit.diagnosis_summary, "risk_flags": list(audit.risk_flags), "multipliers": {"regime_relevance": regime, "confidence": confidence_multiplier(audit.confidence_level), "penalty": penalty},
        })
    rows.sort(key=lambda row: row["asset_health_score"], reverse=True)
    wounded = [row for row in rows if row["wound_level"] > 0]

    weights = {asset: max(0.0, float(weight)) for asset, weight in portfolio.target_weights.items()}
    total_weight = sum(weights.get(row["asset"], 0) for row in rows)
    weighted_health = (sum(row["asset_health_score"] * weights.get(row["asset"], 0) for row in rows) / total_weight) if total_weight else mean(row["asset_health_score"] for row in rows)
    internal_weighted_health = (sum(row["internal_health_score"] * weights.get(row["asset"], 0) for row in rows) / total_weight) if total_weight else mean(row["internal_health_score"] for row in rows)
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
    growth_strong = all(by_asset.get(asset, {}).get("internal_health_score", 0) >= 75 for asset in ("VT", "BTC"))
    defense_broadly_weak = sum(by_asset.get(asset, {}).get("internal_health_score", 100) < 60 for asset in ("TLT", "BNDX", "GLDM")) >= 2
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
    checkpoints = [f"{row['asset']}の{row['wound_label']}が継続するか確認する。" for row in wounded[:4]]
    if context.btc_divergence_note: checkpoints.append("BTCが成長気団に再連動するか確認する。")
    if "defense_air_mass_absent" in context.market_context_flags: checkpoints.append("TLTとBNDXが景気後退防衛として機能しているか確認する。")
    if "gold_commodity_weakness" in context.market_context_flags: checkpoints.append("GLDM・DBCの弱さが局面不適合か、役割劣化かを確認する。")
    if not correlation_available: checkpoints.append("VT/TLT、VT/GLDM、VT/BTCの相関構造を確認する。")

    result: dict[str, Any] = {
        "sanctuary_health_score": sanctuary, "internal_sanctuary_health_score": internal_sanctuary, "global_judgment_level": global_level, "global_judgment_label": GLOBAL_JUDGMENT_LABELS_JA[global_level],
        "lumus_global_judgment": {"level": global_level, "label": GLOBAL_JUDGMENT_LABELS_JA[global_level]},
        "contextual_action_candidate_level": contextual_action_candidate, "internal_action_level": internal_action,
        "raw_action_level": raw_action, "action_level": action, "action_label": ACTION_LABELS_JA[action],
        "portfolio_adjustment_recommendation": {"level": action, "label": ACTION_LABELS_JA[action], "advisory_only": True},
        "hysteresis_note": hysteresis_note, "market_context_safety_note": market_context_safety_note, "asset_health_rank": rows, "wounded_assets": wounded, "role_group_diagnosis": role_group_diagnosis,
        "market_context": asdict(context), "market_context_summary": context.market_context_summary,
        "recommended_actions": recommended, "not_recommended_actions": not_recommended, "next_checkpoints": checkpoints,
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
    path.write_text(result["report_text"], encoding="utf-8")
    print(result["report_text"], end="")
    print(f"保存先: {path}")
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
