"""El Shaddai v2.0 日本語統合監査レポート。"""

from __future__ import annotations

from typing import Any, Mapping

from .market_context_adapter import MARKET_CONTEXT_FLAG_LABELS_JA
from .text_sanitizer import sanitize_output_text

REQUIRED_SECTIONS = (
    "結論サマリー", "データ完全性", "注意点", "総合診断", "要約", "今回推奨する行動", "今回推奨しない行動", "八騎士 健全度順位", "負傷アセット", "機会判定",
    "役割グループ診断", "市場文脈", "相関構造診断", "次回監査で確認すること", "最終メッセージ",
)

def _bullets(items: list[str]) -> list[str]:
    return [f"・{item}" for item in items] or ["・該当なし"]


def _injury_breakdown_text(result: Mapping[str, Any]) -> str:
    breakdown = result.get("injury_breakdown", {})
    return "、".join(f"{name} {count}件" for name, count in breakdown.items()) if breakdown else "該当なし"


def _table_cell(value: Any) -> str:
    return str(value).replace("|", "／").replace("\n", " ")


def _asset_list(items: list[str]) -> str:
    return "、".join(items) if items else "なし"


def _audit_integrity_lines(result: Mapping[str, Any]) -> list[str]:
    completeness = result["data_completeness"]
    reasons = completeness["audit_integrity_reasons"]
    lines = [
        f"監査完全性：{completeness['audit_integrity']}（{completeness['audit_context_status']}）",
        f"データ接続：FRED {completeness['fred_data_status']} / degraded adapters {_asset_list(completeness['degraded_adapters'])} / failed adapters {_asset_list(completeness['failed_adapters'])}",
    ]
    if reasons:
        lines += [
            f"理由：{' / '.join(reasons)}",
            f"今回の総合状態は、{'および'.join(reason.removesuffix('未入力') for reason in reasons)}が未入力のため、文脈未接続の暫定判定です。",
            "総合状態と推奨運用判断は、文脈未接続の参考判定として確認してください。",
            "暫定判定は自動売買・自動売却を意味しません。",
        ]
    else:
        lines.append("Market Amedasおよび相関構造を接続した通常の統合監査です。")
    return lines


def _data_completeness_lines(result: Mapping[str, Any]) -> list[str]:
    completeness = result["data_completeness"]
    fred_provider = completeness.get("fred_provider")
    fred_suffix = f"（provider: {fred_provider}）" if fred_provider else ""
    return [
        "【データ完全性】",
        f"・価格データ：{completeness['price_data_status']}",
        f"・FREDデータ：{completeness['fred_data_status']}{fred_suffix}",
        f"・Market Amedas：{'入力あり' if completeness['market_amedas_available'] else '未入力'}",
        f"・相関構造：{'入力あり' if completeness['correlation_available'] else '未入力'}",
        f"・degraded adapters：{_asset_list(completeness['degraded_adapters'])}",
        f"・failed adapters：{_asset_list(completeness['failed_adapters'])}",
    ]


def sanitize_report_text(text: str) -> str:
    """端末UI由来のメタ文字列を、保存・表示前の報告書から除去する。"""
    return sanitize_output_text(text)


def render_integrated_report(result: Mapping[str, Any]) -> str:
    """構造化監査結果を、日本語の運用監査報告書として描画する。"""
    wounded = len(result["wounded_assets"])
    opportunities = len(result.get("opportunity_judgments", []))
    degraded = len(result["data_completeness"]["degraded_adapters"])
    failed = len(result["data_completeness"]["failed_adapters"])
    breakdown = _injury_breakdown_text(result)
    lines = [
        "=" * 60, "EL SHADDAI 統合監査報告書 v2.0", "=" * 60, "",
        "【結論サマリー】",
        *_audit_integrity_lines(result),
        f"総合状態：{result['global_judgment_label']} / 推奨運用判断：{result['action_label']}（助言のみ・自動売買なし）",
        f"負傷アセットは{wounded}件（内訳：{breakdown}）。",
        f"機会判定は{opportunities}件 / degraded adaptersは{degraded}件 / failed adaptersは{failed}件。",
        "低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。",
        "", *_data_completeness_lines(result),
        "", "【注意点】", *_bullets(result.get("opening_caveats", [])),
        "", "【総合診断】",
        f"聖域健全度スコア：{result['sanctuary_health_score']:.1f} / 100",
        f"内部役割健全度スコア：{result['internal_sanctuary_health_score']:.1f} / 100",
        f"総合状態：{result['global_judgment_label']}",
        f"推奨運用判断：{result['action_label']}（助言のみ・自動売買なし）",
    ]
    if result.get("hysteresis_note"):
        lines.append(f"継続判定：{result['hysteresis_note']}")

    watch_groups = [group for group, diagnosis in result["role_group_diagnosis"].items() if diagnosis["level"] <= 3]
    summary = [
        f"L.U.M.U.S.-8の総合状態を監査し、負傷アセットは{wounded}件（内訳：{breakdown}）、機会判定は{opportunities}件と判定した。",
        f"データ接続状態は degraded adapters {degraded}件、failed adapters {failed}件。",
    ]
    if not wounded and watch_groups:
        summary.append(f"個別アセットに明確な役割負傷はないが、{'・'.join(watch_groups)}グループは相対的に弱く、次回監査で確認する。")
    summary.append("低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。")
    lines += ["", "【要約】", *summary, "", "【今回推奨する行動】", *_bullets(result["recommended_actions"])]
    lines += ["", "【今回推奨しない行動】", *_bullets(result["not_recommended_actions"])]

    lines += [
        "", "【八騎士 健全度順位】",
        "総合状態と負傷タイプは別判定であり、市場文脈だけでは負傷扱いにしない。O.R.A.C.L.E.対象は機会判定として表示する。",
        "| asset | adapter | score | status | injury_type | one_line_summary | recommended_action |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for asset in result["asset_health_rank"]:
        cells = (
            asset["asset"], asset["audit_engine"], f"{asset['asset_health_score']:.1f}", asset["display_status"],
            asset["injury_type"], asset["one_line_summary"], asset["recommended_action"],
        )
        lines.append("| " + " | ".join(_table_cell(cell) for cell in cells) + " |")

    lines += ["", "【負傷アセット】", f"判定件数：{wounded}件（内訳：{breakdown}）"]
    if not result["wounded_assets"]:
        lines.append("・明確な負傷アセットなし。価格変動や市場文脈だけでは役割負傷と判定しない。")
    else:
        for asset in result["wounded_assets"]:
            lines.append(f"・{asset['asset']}：{asset['injury_type']} / {asset['one_line_summary']} / {asset['recommended_action']}")
            lines.extend(f"  - {note}" for note in asset.get("interpretation_notes", []))
    lines.append("詳細なproxy理由・指標値は詳細ログおよびasset reportを参照する。")

    lines += ["", "【機会判定】", f"判定件数：{opportunities}件"]
    if not result.get("opportunity_judgments"):
        lines.append("・O.R.A.C.L.E.による機会判定なし。")
    else:
        for asset in result["opportunity_judgments"]:
            lines.append(f"・{asset['asset']}：{asset['injury_type']} / {asset['one_line_summary']} / {asset['recommended_action']}")

    lines += ["", "【役割グループ診断】"]
    for group, diagnosis in result["role_group_diagnosis"].items():
        lines.append(f"・{group}：{diagnosis['label']}（平均 {diagnosis['score']:.1f}）")

    context = result["market_context"]
    lines += ["", "【市場文脈】", context["market_context_summary"], *context["market_narratives"]]
    if context["air_mass_ratios"]:
        if context.get("air_mass_measure") == "ratio":
            lines.append("主要気団の比率（合計100%の構成比）：" + "、".join(f"{name} {value:.1f}%" for name, value in context["air_mass_ratios"].items()))
        else:
            lines.append("主要気団の強度（各気団の独立スコア）：" + "、".join(f"{name} {value:.1f} / 100" for name, value in context["air_mass_ratios"].items()))
        lines.append("主要気団の強弱（内部正規化後）：" + "、".join(f"{name} {strength}" for name, strength in context["air_mass_strengths"].items()))
    if context["top_updrafts"]:
        lines.append("主要な上昇流：" + "、".join(f"{flow['name']} {flow['observed_value']:+.2f}" for flow in context["top_updrafts"]))
    if context["top_downdrafts"]:
        lines.append("主要な下降流：" + "、".join(f"{flow['name']} {flow['observed_value']:+.2f}" if flow['observed_value'] else f"{flow['name']} 0.00" for flow in context["top_downdrafts"]))
    if context["btc_sensor_summary"]:
        lines.append(f"BTCセンサー：{context['btc_sensor_summary']}")
    if context["btc_divergence_note"]:
        lines.append(f"BTC注意：{context['btc_divergence_note']}")
    lines += _bullets([f"文脈フラグ：{MARKET_CONTEXT_FLAG_LABELS_JA.get(flag, flag)}" for flag in context["market_context_flags"]])
    lines += _bullets([f"{asset}：{note}" for asset, note in context["asset_context_notes"].items()]) if context["asset_context_notes"] else []
    if result.get("market_context_safety_note"):
        lines.append(f"安全制約：{result['market_context_safety_note']}")
    lines += ["Market Amedas単独では売却・配分変更を正当化しない。"]

    lines += ["", "【相関構造診断】", result["correlation_diagnosis"]]
    lines += ["", "【次回監査で確認すること】", *_bullets(result["next_checkpoints"])]
    lines += ["", "【最終メッセージ】", "市場の空を確認し、装備の役割を点検する。空模様だけで装備を捨てない。"]
    return sanitize_report_text("\n".join(lines) + "\n")
