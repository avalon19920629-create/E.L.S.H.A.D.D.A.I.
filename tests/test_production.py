import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from el_shaddai.config import ASSETS
from el_shaddai.production import load_production_config, run_production
from el_shaddai.production_manifest import SAFETY_BOUNDARY, evaluate_quality_gate, git_metadata
from run_el_shaddai_production import main


@pytest.fixture(autouse=True)
def yaml_module_for_minimal_test_environment(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=json.load))


def _config(path: Path, *, weights=None):
    weights = weights or {asset: 0.125 for asset in ASSETS}
    path.write_text(json.dumps({
        "price_data": {"provider": "yfinance", "period": "1y"},
        "role_adapters": {"enabled": []},
        "oracle": {"enabled": False},
        "portfolio": {"target_weights": weights},
    }), encoding="utf-8")


def test_load_production_config_validates_all_weights(tmp_path):
    config_path = tmp_path / "production.yaml"
    _config(config_path)
    config = load_production_config(config_path)
    assert config.price_period == "1y"
    assert sum(config.target_weights.values()) == 1.0
    assert config.enabled_role_adapters == ()

    _config(config_path, weights={"VT": 1.0})
    with pytest.raises(ValueError, match="8資産すべて"):
        load_production_config(config_path)


def test_run_production_writes_drive_ready_artifacts_without_demo(tmp_path, monkeypatch):
    config_path = tmp_path / "production.yaml"
    output_dir = tmp_path / "drive" / "reports"
    _config(config_path)
    monkeypatch.setattr(
        "el_shaddai.production.fetch_live_prices",
        lambda period: ({asset: [100 + day * 0.1 for day in range(320)] for asset in ASSETS}, "2026-06-08"),
    )

    paths = run_production(config_path, output_dir)

    assert set(paths) == {"scores_csv", "asset_report_markdown", "dashboard_html", "lumus8_report_markdown", "manifest_json"}
    assert all(path.is_file() and path.parent == output_dir.resolve() for path in paths.values())
    audit_json_path = output_dir / "el_shaddai_lumus8_audit.json"
    assert audit_json_path.is_file()
    audit_json = json.loads(audit_json_path.read_text(encoding="utf-8"))
    assert audit_json["schema_version"] == "el_shaddai_lumus8_audit.v1"
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    assert manifest["run_type"] == "production_single_audit"
    assert manifest["schema_version"] == "production_run_manifest.v1"
    assert manifest["safety"] == SAFETY_BOUNDARY
    assert manifest["quality_gate"]["status"] == "fail"  # Market Amedas / Parallax are connected by the next runner.
    assert manifest["inputs"]["el_shaddai_audit"]["price_data_status"] == "OK"
    assert manifest["inputs"]["el_shaddai_audit"]["fred_data_status"] == "OK"
    assert manifest["inputs"]["el_shaddai_audit"]["fred_provider"] == "pandas_datareader"
    assert any(item["name"] == "el_shaddai_lumus8_audit.json" for item in manifest["outputs"]["generated_files"])
    report = paths["lumus8_report_markdown"].read_text(encoding="utf-8")
    assert "・FREDデータ：OK（provider: pandas_datareader）" in report
    assert "・Market Amedas：未入力" in report
    assert "・相関構造：未入力" in report
    assert "demo" not in paths["lumus8_report_markdown"].name


def test_production_entrypoint_requires_output_dir():
    with pytest.raises(SystemExit):
        main([])


def test_json_write_failure_does_not_stop_existing_production_outputs(tmp_path, monkeypatch):
    config_path = tmp_path / "production.yaml"
    output_dir = tmp_path / "reports"
    _config(config_path)
    monkeypatch.setattr(
        "el_shaddai.production.fetch_live_prices",
        lambda period: ({asset: [100 + day * 0.1 for day in range(320)] for asset in ASSETS}, "2026-06-08"),
    )
    monkeypatch.setattr(
        "el_shaddai.production.write_integrated_audit_json",
        lambda payload, output_path: (_ for _ in ()).throw(OSError("disk full")),
    )

    paths = run_production(config_path, output_dir)

    assert set(paths) == {"scores_csv", "asset_report_markdown", "dashboard_html", "lumus8_report_markdown", "manifest_json"}
    assert all(path.is_file() for path in paths.values())
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    assert any("failed to write el_shaddai_lumus8_audit.json" in warning for warning in manifest["warnings"])
    assert manifest["inputs"]["el_shaddai_audit"]["available"] is False
    assert manifest["quality_gate"]["status"] == "fail"


def test_asset_audits_pass_role_score_as_role_health_and_preserve_oracle_fallback():
    from el_shaddai.production import _asset_audits

    details = SimpleNamespace(components={}, core_score=50)
    scores = [
        SimpleNamespace(asset="DBC", price_score=42, role_score=85, el_shaddai_score=42, main_reason="dbc", data_date="2026-06-08", price_details=details, role_details=details),
        SimpleNamespace(asset="VT", price_score=42, role_score=None, el_shaddai_score=42, main_reason="vt", data_date="2026-06-08", price_details=details, role_details=details),
    ]

    by_asset = {audit.asset: audit for audit in _asset_audits(scores)}

    assert by_asset["DBC"].role_health_score == 85
    assert by_asset["DBC"].supporting_metrics["final_score"] == 42
    assert by_asset["VT"].role_health_score == 42


def _quality_inputs():
    market = {"schema_version": "market_amedas_snapshot.v1"}
    audit = {"schema_version": "el_shaddai_lumus8_audit.v1", "audit_completeness": {"price_data_status": "OK", "fred_data_status": "OK", "fred_provider": "fredapi", "degraded_adapters": [], "failed_adapters": []}}
    parallax = {"schema_version": "parallax_context_report.v1", "safety": dict(SAFETY_BOUNDARY)}
    return market, audit, parallax


def test_quality_gate_pass_warn_and_fail_rules():
    market, audit, parallax = _quality_inputs()
    passed = evaluate_quality_gate(market, audit, parallax)
    assert passed["status"] == "pass"
    assert passed["reasons"] == []
    assert passed["warnings_count"] == 0

    warned = evaluate_quality_gate(market, audit, parallax, warnings=["known fallback", "second warning"])
    assert warned["status"] == "warn"
    assert warned["reasons"] == ["Non-fatal warnings are present: 2"]
    assert warned["warnings_count"] == 2

    audit["audit_completeness"]["degraded_adapters"] = ["TIP"]
    degraded = evaluate_quality_gate(market, audit, parallax)
    assert degraded["status"] == "warn"
    assert degraded["reasons"] == ["degraded_adapters is not empty: TIP"]
    audit["audit_completeness"]["degraded_adapters"] = []

    audit["audit_completeness"]["failed_adapters"] = ["TLT"]
    failed = evaluate_quality_gate(market, audit, parallax, warnings=["known fallback"])
    assert failed["status"] == "fail"
    assert failed["reasons"] == ["failed_adapters is not empty: TLT"]
    audit["audit_completeness"]["failed_adapters"] = []
    assert evaluate_quality_gate(None, audit, parallax)["status"] == "fail"
    broken_safety = {**SAFETY_BOUNDARY, "automatic_trading": True}
    assert evaluate_quality_gate(market, audit, parallax, safety=broken_safety)["status"] == "fail"


def test_git_metadata_failure_is_non_fatal(monkeypatch):
    monkeypatch.setattr("el_shaddai.production_manifest.subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")))
    assert git_metadata() == {"commit": "unknown", "branch": "unknown", "is_dirty": None}
