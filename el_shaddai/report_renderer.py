"""El Shaddai v2.0 日本語統合監査レポート。"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .market_context_adapter import MARKET_CONTEXT_FLAG_LABELS_JA

REQUIRED_SECTIONS = (
    "総合診断", "要約", "今回推奨する行動", "今回推奨しない行動", "八騎士 健全度順位", "負傷アセット",
    "役割グループ診断", "市場文脈", "相関構造診断", "次回監査で確認すること", "最終メッセージ",
)
_CODEX_TERMINAL_CITATION = re.compile(r":codex-terminal-citation(?:\[[^]\r\n]*\])?(?:\{[^\r\n]*\})?", re.IGNORECASE)


def _bullets(items: list[str]) -> list[str]:
    return [f"・{item}" for item in items] or ["・該当なし"]


def sanitize_report_text(text: str) -> str:
    """端末UI由来のメタ文字列を、保存・表示前の報告書から除去する。"""
    return _CODEX_TERMINAL_CITATION.sub("", text)


def render_integrated_report(result: Mapping[str, Any]) -> str:
    """構造化監査結果を、日本語の運用監査報告書として描画する。"""
    lines = ["=" * 60, "EL SHADDAI 統合監査報告書 v2.0", "=" * 60, "", "【総合診断】"]
    lines += [
        f"聖域健全度スコア：{result['sanctuary_health_score']:.1f} / 100", f"内部役割健全度スコア：{result['internal_sanctuary_health_score']:.1f} / 100",
        f"総合診断：{result['global_judgment_label']}", f"推奨運用判断：{result['action_label']}（助言のみ・自動売買なし）",
    ]
    if result.get("hysteresis_note"): lines.append(f"継続判定：{result['hysteresis_note']}")

    wounded = len(result["wounded_assets"])
    watch_groups = [group for group, diagnosis in result["role_group_diagnosis"].items() if diagnosis["level"] <= 3]
    summary = [f"L.U.M.U.S.-8の役割健全性を監査し、負傷アセットは{wounded}件と判定した。"]
    if not wounded and watch_groups:
        summary.append(f"個別アセットに明確な役割負傷はないが、{'・'.join(watch_groups)}グループは相対的に弱く、次回監査で確認する。")
    summary.append("低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。")
    lines += ["", "【要約】", *summary, "", "【今回推奨する行動】", *_bullets(result["recommended_actions"])]
    lines += ["", "【今回推奨しない行動】", *_bullets(result["not_recommended_actions"])]

    lines += ["", "【八騎士 健全度順位】", "文脈健全度ラベルと負傷判定は別判定であり、市場文脈だけでは負傷扱いにしない。"]
    for index, asset in enumerate(result["asset_health_rank"], 1):
        lines.append(f"{index}. {asset['asset']} / {asset['audit_engine']}：文脈反映後 {asset['asset_health_score']:.1f} / 内部 {asset['internal_health_score']:.1f} / 文脈健全度 {asset['health_label']} / 負傷判定 {asset['wound_label']}")

    lines += ["", "【負傷アセット】"]
    if not result["wounded_assets"]: lines.append("・明確な負傷アセットなし。価格変動や市場文脈だけでは役割負傷と判定しない。")
    else:
        for asset in result["wounded_assets"]: lines.append(f"・{asset['asset']}：{asset['wound_label']} / {asset['diagnosis_summary'] or '継続監査対象'}")

    lines += ["", "【役割グループ診断】"]
    for group, diagnosis in result["role_group_diagnosis"].items(): lines.append(f"・{group}：{diagnosis['label']}（平均 {diagnosis['score']:.1f}）")

    context = result["market_context"]
    lines += ["", "【市場文脈】", context["market_context_summary"], *context["market_narratives"]]
    if context["air_mass_ratios"]:
        lines.append("主要気団の比率（Market Amedas観測値）：" + "、".join(f"{name} {ratio:.1f}%" for name, ratio in context["air_mass_ratios"].items()))
        lines.append("主要気団の強弱（内部正規化後）：" + "、".join(f"{name} {strength}" for name, strength in context["air_mass_strengths"].items()))
    if context["top_updrafts"]: lines.append("主要な上昇流：" + "、".join(f"{flow['name']} {flow['observed_value']:+.2f}" for flow in context["top_updrafts"]))
    if context["top_downdrafts"]: lines.append("主要な下降流：" + "、".join(f"{flow['name']} {flow['observed_value']:+.2f}" if flow['observed_value'] else f"{flow['name']} 0.00" for flow in context["top_downdrafts"]))
    if context["btc_sensor_summary"]: lines.append(f"BTCセンサー：{context['btc_sensor_summary']}")
    if context["btc_divergence_note"]: lines.append(f"BTC注意：{context['btc_divergence_note']}")
    lines += _bullets([f"文脈フラグ：{MARKET_CONTEXT_FLAG_LABELS_JA.get(flag, flag)}" for flag in context["market_context_flags"]])
    lines += _bullets([f"{asset}：{note}" for asset, note in context["asset_context_notes"].items()]) if context["asset_context_notes"] else []
    if result.get("market_context_safety_note"): lines.append(f"安全制約：{result['market_context_safety_note']}")
    lines += ["Market Amedas単独では売却・配分変更を正当化しない。"]

    lines += ["", "【相関構造診断】", result["correlation_diagnosis"]]
    lines += ["", "【次回監査で確認すること】", *_bullets(result["next_checkpoints"])]
    lines += ["", "【最終メッセージ】", "市場の空を確認し、装備の役割を点検する。空模様だけで装備を捨てない。"]
    return sanitize_report_text("\n".join(lines) + "\n")
