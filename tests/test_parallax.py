import json
from datetime import datetime, timezone
from pathlib import Path

from el_shaddai.parallax import SAFETY_NOTICE, build_parallax_report, render_markdown, run_parallax, write_parallax_outputs

FIXTURES = Path(__file__).parent / "fixtures" / "parallax"


def _inputs():
    market = json.loads((FIXTURES / "market_amedas_snapshot.json").read_text(encoding="utf-8"))
    audit = json.loads((FIXTURES / "el_shaddai_lumus8_audit.json").read_text(encoding="utf-8"))
    return market, audit


def test_build_report_classifies_required_assets_without_rewriting_scores():
    market, audit = _inputs()
    report = build_parallax_report(market, audit, generated_at=datetime(2026, 6, 12, tzinfo=timezone.utc))
    contexts = {item["asset"]: item for item in report["asset_contexts"]}

    assert report["schema_version"] == "parallax_context_report.v1"
    assert contexts["DBC"]["context_label"] == "context_explained_weakness"
    assert contexts["BTC"]["context_label"] == "context_divergence"
    assert contexts["TLT"]["context_label"] in {"context_explained_weakness", "role_activation_absent"}
    assert contexts["XLRE"]["context_label"] in {"context_divergence", "role_failure_candidate"}
    source_assets = {item["asset"]: item for item in audit["assets"]}
    assert contexts["DBC"]["asset_evidence"]["final_score"] == source_assets["DBC"]["final_score"]
    assert report["safety"]["score_rewrite"] is False


def test_missing_market_and_missing_el_shaddai_return_insufficient_context():
    market, audit = _inputs()
    missing_market = build_parallax_report(None, audit)
    missing_audit = build_parallax_report(market, None)

    assert all(item["context_label"] == "insufficient_context" for item in missing_market["asset_contexts"])
    assert missing_market["summary"]["parallax_state"] == "insufficient_context"
    assert missing_audit["summary"]["parallax_state"] == "insufficient_context"
    assert "el_shaddai" in missing_audit["summary"]["insufficient_context"]


def test_outputs_include_safety_boundary_and_preserve_japanese(tmp_path):
    market, audit = _inputs()
    paths = write_parallax_outputs(build_parallax_report(market, audit), tmp_path)
    raw = paths["json"].read_bytes()
    markdown = paths["markdown"].read_text(encoding="utf-8")

    assert SAFETY_NOTICE.encode("utf-8") in raw
    assert SAFETY_NOTICE in markdown
    assert "## 8. 安全境界" in markdown
    assert json.loads(raw.decode("utf-8"))["safety"]["automatic_trading"] is False


def test_cli_runner_reads_realistic_fixtures_and_tolerates_missing_file(tmp_path):
    paths = run_parallax(FIXTURES / "market_amedas_snapshot.json", FIXTURES / "el_shaddai_lumus8_audit.json", tmp_path / "complete")
    missing_paths = run_parallax(tmp_path / "missing.json", FIXTURES / "el_shaddai_lumus8_audit.json", tmp_path / "missing")

    assert set(paths) == {"json", "markdown"}
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["input_versions"] == {"market_amedas": "market_amedas_snapshot.v1", "el_shaddai": "el_shaddai_lumus8_audit.v1"}
    assert json.loads(missing_paths["json"].read_text(encoding="utf-8"))["summary"]["parallax_state"] == "insufficient_context"


def test_markdown_has_all_required_sections():
    market, audit = _inputs()
    markdown = render_markdown(build_parallax_report(market, audit))
    for number in range(1, 9):
        assert f"## {number}." in markdown


def test_missing_major_market_fields_returns_insufficient_asset_context():
    _, audit = _inputs()
    market = {"schema_version": "market_amedas_snapshot.v1", "data_status": {"status": "incomplete"}}
    report = build_parallax_report(market, audit)

    assert all(item["context_label"] == "insufficient_context" for item in report["asset_contexts"])
    assert all(item["confidence"] == "low" for item in report["asset_contexts"])


def test_full_lumus8_fixture_covers_all_assets_without_insufficient_context():
    market, audit = _inputs()
    report = build_parallax_report(market, audit)
    contexts = {item["asset"]: item for item in report["asset_contexts"]}
    expected_assets = {"VT", "BTC", "TLT", "BNDX", "TIP", "GLDM", "DBC", "XLRE"}

    assert set(contexts) == expected_assets
    assert len(contexts) == 8
    assert all(contexts[asset]["context_label"] != "insufficient_context" for asset in {"BNDX", "TIP", "GLDM"})
    assert contexts["DBC"]["context_label"] == "context_explained_weakness"
    assert contexts["BTC"]["context_label"] == "context_divergence"
    assert all(item["confidence"] != "low" for item in contexts.values())
    assert contexts["TIP"]["relevant_warnings"] == ["inflation_air_mass_negative", "real_rate_shock"]


def test_full_lumus8_outputs_remain_advisory_only(tmp_path):
    market, audit = _inputs()
    paths = write_parallax_outputs(build_parallax_report(market, audit), tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["safety"] == {
        "advisory_only": True,
        "automatic_trading": False,
        "automatic_selling": False,
        "allocation_change": False,
        "score_rewrite": False,
        "notice": SAFETY_NOTICE,
    }
    assert SAFETY_NOTICE in markdown
    forbidden_instructions = [
        "購入してください",
        "売却してください",
        "買い増してください",
        "配分を変更してください",
        "自動売買を実行",
        "自動売却を実行",
    ]
    assert not any(instruction in markdown for instruction in forbidden_instructions)


def test_fred_success_does_not_lower_parallax_confidence_like_fred_failure():
    market, audit = _inputs()
    market["market_warnings"] = []
    market["data_status"] = {"status": "OK"}
    audit["warnings"] = []
    audit["audit_completeness"] = {"fred_data_status": "OK", "fred_provider": "fredapi", "degraded_adapters": [], "failed_adapters": []}
    for asset in audit["assets"]:
        asset["warnings"] = []
        asset["oracle_details"] = {}

    successful = build_parallax_report(market, audit)
    assert all(item["confidence"] == "high" for item in successful["asset_contexts"])

    audit["audit_completeness"] = {"fred_data_status": "failed", "degraded_adapters": ["TLT", "TIP"], "failed_adapters": ["TLT", "TIP"]}
    failed = build_parallax_report(market, audit)
    assert all(item["confidence"] == "low" for item in failed["asset_contexts"])


def _fred_ok_with_clean_asset_warnings(market, audit):
    market["data_status"] = {"status": "OK"}
    audit["audit_completeness"] = {
        "price_data_status": "OK",
        "fred_data_status": "OK",
        "fred_provider": "fredapi",
        "degraded_adapters": [],
        "failed_adapters": [],
    }
    for asset in audit["assets"]:
        asset["warnings"] = []
        asset["oracle_details"] = {}


def test_fred_ok_and_scoped_warnings_do_not_make_all_assets_low():
    market, audit = _inputs()
    _fred_ok_with_clean_asset_warnings(market, audit)
    market["market_warnings"] = ["inflation_air_mass_negative", "btc_downdraft_under_risk_on_sensor"]
    audit["warnings"] = [
        "warning: O.R.A.C.L.E. live mode uses price/VIX only in v1.7; unavailable fields use neutral fallback.",
        "warning: O.R.A.C.L.E. BTC value inputs unavailable; neutral 50 fallback applied.",
        "warning: I.N.F.E.R.N.O. severe penalty proxy detected: real_rate_shock",
    ]

    contexts = {item["asset"]: item for item in build_parallax_report(market, audit)["asset_contexts"]}

    assert contexts["TLT"]["confidence"] == "high"
    assert contexts["BNDX"]["confidence"] == "high"
    assert contexts["XLRE"]["confidence"] == "high"
    assert contexts["DBC"]["confidence"] == "medium"
    assert contexts["GLDM"]["confidence"] == "medium"
    assert any(item["confidence"] != "low" for item in contexts.values())


def test_oracle_warnings_are_scoped_to_vt_and_btc():
    market, audit = _inputs()
    _fred_ok_with_clean_asset_warnings(market, audit)
    market["market_warnings"] = []
    audit["warnings"] = [
        "warning: O.R.A.C.L.E. live mode uses price/VIX only in v1.7; unavailable fields use neutral fallback.",
        "warning: O.R.A.C.L.E. VT value inputs unavailable; neutral 50 fallback applied.",
        "warning: O.R.A.C.L.E. BTC cycle inputs unavailable; neutral 50 fallback applied.",
    ]

    contexts = {item["asset"]: item for item in build_parallax_report(market, audit)["asset_contexts"]}

    assert contexts["VT"]["confidence"] == "medium"
    assert contexts["BTC"]["confidence"] == "medium"
    assert all(contexts[asset]["confidence"] == "high" for asset in {"TLT", "BNDX", "TIP", "GLDM", "DBC", "XLRE"})
    assert all("O.R.A.C.L.E." in warning for warning in contexts["VT"]["relevant_warnings"])


def test_market_amedas_warnings_are_scoped_to_related_assets():
    market, audit = _inputs()
    _fred_ok_with_clean_asset_warnings(market, audit)
    audit["warnings"] = []
    market["market_warnings"] = ["inflation_air_mass_negative", "btc_downdraft_under_risk_on_sensor"]

    contexts = {item["asset"]: item for item in build_parallax_report(market, audit)["asset_contexts"]}

    assert all(contexts[asset]["confidence"] == "medium" for asset in {"BTC", "TIP", "DBC", "GLDM"})
    assert all(contexts[asset]["confidence"] == "high" for asset in {"VT", "TLT", "BNDX", "XLRE"})


def test_inferno_warning_is_scoped_to_tip_and_inflation_defense_group():
    market, audit = _inputs()
    _fred_ok_with_clean_asset_warnings(market, audit)
    market["market_warnings"] = []
    audit["warnings"] = ["warning: I.N.F.E.R.N.O. severe penalty proxy detected: macro_submission"]

    report = build_parallax_report(market, audit)
    contexts = {item["asset"]: item for item in report["asset_contexts"]}

    assert contexts["TIP"]["confidence"] == "medium"
    assert all(contexts[asset]["confidence"] == "high" for asset in {"BNDX", "TLT", "XLRE", "DBC", "GLDM"})
    assert report["group_contexts"]["inflation_defense"]["warnings"] == audit["warnings"]


def test_global_failure_still_lowers_every_asset():
    market, audit = _inputs()
    _fred_ok_with_clean_asset_warnings(market, audit)
    market["market_warnings"] = []
    audit["warnings"] = []
    audit["audit_completeness"]["failed_adapters"] = ["L.O.D.E."]

    report = build_parallax_report(market, audit)

    assert report["global_critical_warnings"]
    assert all(item["confidence"] == "low" for item in report["asset_contexts"])


def test_markdown_v012_uses_human_readable_labels_without_changing_json_values():
    market, audit = _inputs()
    report = build_parallax_report(market, audit)
    context = report["asset_contexts"][0]
    context.update({"context_label": "context_divergence", "severity": "critical", "confidence": "low"})
    report["asset_contexts"][1].update({"severity": "high", "confidence": "high"})
    report["asset_contexts"][2].update({"severity": "medium", "confidence": "medium"})
    report["asset_contexts"][3].update({"severity": "low", "confidence": "high"})

    markdown = render_markdown(report)
    asset_table = markdown.split("## 4. 資産別Parallax判定", 1)[1].split("## 5.", 1)[0]

    assert markdown.startswith("# Parallax Context Report v0.1.2")
    assert "Parallax状態: 文脈混在 (context_mixed)" in markdown
    assert "| Asset | 文脈判定 | 確認優先度 | 判定信頼度 | 解釈 |" in asset_table
    assert "| 文脈乖離 | 最重要確認 | 低 |" in asset_table
    assert "重点確認" in asset_table
    assert "通常確認" in asset_table
    assert "参考確認" in asset_table
    assert "高" in asset_table
    assert "中" in asset_table
    assert not any(value in asset_table for value in ("critical", "high", "medium", "low"))
    assert "確認優先度は売買判断・売却判断・配分変更判断ではありません" in asset_table
    assert context["context_label"] == "context_divergence"
    assert context["severity"] == "critical"
    assert context["confidence"] == "low"


def test_markdown_summarizes_known_warnings_without_changing_json_warnings():
    market, audit = _inputs()
    warning = "warning: O.R.A.C.L.E. BTC sentiment inputs unavailable; neutral 50 fallback applied."
    audit["warnings"] = [warning]
    report = build_parallax_report(market, audit)

    markdown = render_markdown(report)

    assert "O.R.A.C.L.E. BTC sentiment中立fallback" in markdown
    assert warning not in markdown
    assert warning in report["warnings"]
    assert warning in next(item for item in report["asset_contexts"] if item["asset"] == "BTC")["relevant_warnings"]
