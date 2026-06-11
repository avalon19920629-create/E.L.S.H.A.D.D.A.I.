import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from el_shaddai.config import ASSETS
from el_shaddai.production import load_production_config, run_production
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
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    assert manifest["run_type"] == "production_single_audit"
    assert manifest["safety"] == {"advisory_only": True, "automatic_trading": False, "continuous_monitoring": False}
    report = paths["lumus8_report_markdown"].read_text(encoding="utf-8")
    assert "・FREDデータ：OK（provider: pandas_datareader）" in report
    assert "・Market Amedas：未入力" in report
    assert "・相関構造：未入力" in report
    assert "demo" not in paths["lumus8_report_markdown"].name


def test_production_entrypoint_requires_output_dir():
    with pytest.raises(SystemExit):
        main([])
