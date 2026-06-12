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
    assert all(item["confidence"] == "medium" for item in contexts.values())


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
