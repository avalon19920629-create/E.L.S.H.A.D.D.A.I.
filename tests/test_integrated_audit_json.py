import json
from datetime import datetime, timezone
from types import SimpleNamespace

from el_shaddai.integrated_audit_json import build_integrated_audit_json, write_integrated_audit_json


def _score(asset, price, role, final, *, invalid=False):
    components = {"rsi": float("nan") if invalid else price}
    return SimpleNamespace(
        asset=asset,
        price_score=price,
        role_score=role,
        el_shaddai_score=final,
        price_details=SimpleNamespace(components=components),
        role_details=SimpleNamespace(components={"role": float("inf") if invalid else role}),
        oracle_details=None,
    )


def _integrated():
    rows = [
        {"asset": "TLT", "audit_engine": "L.O.D.E.", "asset_health_score": 45.0, "display_status": "2. 負傷", "wound_level": 1, "injury_type": "価格負傷", "one_line_summary": "金利を確認", "recommended_action": "次回監査で重点確認"},
        {"asset": "VT", "audit_engine": "O.R.A.C.L.E.", "asset_health_score": 40.0, "display_status": "追加買い候補", "wound_level": 2, "injury_type": "機会判定", "one_line_summary": "割安度を確認", "recommended_action": "追加買いを人間が検討"},
    ]
    return {
        "asset_health_rank": rows,
        "wounded_assets": [rows[0]],
        "opportunity_judgments": [rows[1]],
        "sanctuary_health_score": 55.0,
        "internal_sanctuary_health_score": 60.0,
        "global_judgment_label": "警戒",
        "action_label": "監視継続",
        "injury_breakdown": {"価格負傷": 1},
        "role_group_diagnosis": {"景気後退防衛": {"score": 45.0, "level": 2, "label": "負傷", "assets": ["TLT", "BNDX"]}},
        "market_context": {"market_context_summary": "Market Amedas未入力"},
        "data_completeness": {"market_amedas_available": False, "correlation_available": False, "degraded_adapters": ["TLT"], "failed_adapters": []},
        "correlation_integrity_score": None,
        "correlation_diagnosis": "相関データ未提供",
        "components": {"weighted_asset_health": 55.0},
        "opening_caveats": ["市場文脈補正なし"],
        "recommended_actions": ["維持する。"],
        "not_recommended_actions": ["自動売買しない。"],
        "next_checkpoints": ["TLTを確認する。"],
    }


def test_build_json_has_schema_joins_scores_and_preserves_health_rank_order():
    payload = build_integrated_audit_json(
        _integrated(),
        [_score("VT", 41.0, None, 42.0), _score("TLT", 45.0, 63.2, 47.5)],
        generated_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        data_date="2026-06-08",
    )

    expected = {"schema_version", "generated_at", "data_date", "report_title", "audit_completeness", "data_integrity", "summary", "actions", "assets", "injured_assets", "opportunities", "role_groups", "market_context", "correlation_context", "next_audit_items", "warnings", "safety"}
    assert expected <= payload.keys()
    assert [asset["asset"] for asset in payload["assets"]] == ["TLT", "VT"]
    assert payload["assets"][0]["price_score"] == 45.0
    assert payload["assets"][0]["role_score"] == 63.2
    assert payload["assets"][0]["final_score"] == 47.5
    assert payload["assets"][0]["role_groups"] == ["recession_defense", "crisis_refuge"]
    assert isinstance(payload["assets"][0]["role_groups"], list)
    assert payload["assets"][1]["is_injured"] is False
    assert payload["assets"][1]["is_opportunity"] is True
    assert payload["role_groups"]["recession_defense"]["label"] == "景気後退防衛"


def test_build_json_sanitizes_nan_and_infinity_without_parsing_markdown():
    integrated = _integrated()
    integrated["report_text"] = "このMarkdown本文はJSONへ入らない"
    payload = build_integrated_audit_json(integrated, [_score("TLT", 45.0, 63.2, 47.5, invalid=True)])

    encoded = json.dumps(payload, allow_nan=False, ensure_ascii=False)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert "このMarkdown本文はJSONへ入らない" not in encoded
    assert payload["assets"][0]["price_metrics"]["rsi"] is None
    assert payload["assets"][0]["role_metrics"]["role"] is None


def test_write_json_preserves_japanese_utf8(tmp_path):
    path = write_integrated_audit_json({"message": "日本語の監査報告"}, tmp_path / "audit.json")

    raw = path.read_bytes()
    assert "日本語の監査報告".encode("utf-8") in raw
    assert json.loads(raw.decode("utf-8")) == {"message": "日本語の監査報告"}
