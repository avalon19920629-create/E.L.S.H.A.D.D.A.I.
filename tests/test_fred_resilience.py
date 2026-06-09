import json
import sys
from types import SimpleNamespace
from pathlib import Path

from el_shaddai.config import ASSETS, ROLE_COMPONENT_WEIGHTS
from el_shaddai.inferno_adapter import latest_tip_role_inputs
from el_shaddai.lode_adapter import latest_tlt_role_inputs
from el_shaddai.production import run_production


def _lode_rows():
    return [
        {"date": "2025-01-01", "T10Y2Y": 1.0, "DFII10": -0.5, "GFDEGDQ188S": 90.0, "A091RC1Q027SBEA": 400.0, "W006RC1Q027SBEA": 4000.0, "FDHBFIN": 7000.0, "GFDEBTN": 23000000.0},
        {"date": "2026-01-01", "T10Y2Y": -1.2, "DFII10": 2.0, "GFDEGDQ188S": 125.0, "A091RC1Q027SBEA": 950.0, "W006RC1Q027SBEA": 4300.0, "FDHBFIN": 8500.0, "GFDEBTN": 35000000.0},
    ]


def _inferno_rows():
    return [
        {"date": "2025-01-01", "CPIAUCSL": 100.0, "CPILFESL": 100.0, "PCEPI": 100.0, "PCEPILFE": 100.0, "T5YIE": 2.0, "T10YIE": 2.0, "DFII10": 0.5, "UNRATE": 4.0, "DTWEXBGS": 100.0},
        {"date": "2026-01-01", "CPIAUCSL": 105.0, "CPILFESL": 104.0, "PCEPI": 104.0, "PCEPILFE": 103.5, "T5YIE": 2.1, "T10YIE": 2.0, "DFII10": 0.8, "UNRATE": 4.8, "DTWEXBGS": 101.0},
    ]


def test_lode_uses_last_successful_cache_after_live_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("el_shaddai.lode_adapter.fetch_lode_fred_data", lambda *_args, **_kwargs: _lode_rows())
    live = latest_tlt_role_inputs(cache_dir=str(tmp_path))
    assert live.used_lode and not live.degraded

    monkeypatch.setattr("el_shaddai.lode_adapter.fetch_lode_fred_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("read timeout")))
    cached = latest_tlt_role_inputs(cache_dir=str(tmp_path))
    assert cached.used_lode and cached.degraded
    assert cached.source == "cache"
    assert cached.stale_days == 0


def test_inferno_has_clear_neutral_degradation_without_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("el_shaddai.inferno_adapter.fetch_inferno_fred_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("read timeout")))
    result = latest_tip_role_inputs(cache_dir=str(tmp_path))
    assert not result.used_inferno and result.degraded
    assert result.stale_days is None
    assert "no usable cache" in result.warnings[0]


def test_production_manifest_marks_neutral_fred_adapter_failed(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=json.load))
    config = tmp_path / "production.json"
    config.write_text(json.dumps({
        "price_data": {"provider": "yfinance", "period": "1y"},
        "fred": {"cache_dir": str(tmp_path / "cache")},
        "role_adapters": {"enabled": ["TLT"]}, "oracle": {"enabled": False},
        "portfolio": {"target_weights": {asset: 0.125 for asset in ASSETS}},
    }), encoding="utf-8")
    monkeypatch.setattr("el_shaddai.production.fetch_live_prices", lambda _period: ({asset: [100 + i for i in range(320)] for asset in ASSETS}, "2026-06-08"))
    monkeypatch.setattr("el_shaddai.production.ROLE_ADAPTERS", {"TLT": lambda **_kwargs: __import__("el_shaddai.lode_adapter", fromlist=["LodeResult"]).LodeResult(
        {"TLT": {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["TLT"]}}, {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["TLT"]}, {}, ["neutral"], "unknown", "L.O.D.E. FRED", False, True, None
    )})
    manifest = json.loads(run_production(config, tmp_path / "out")["manifest_json"].read_text(encoding="utf-8"))
    assert manifest["degraded_assets"] == ["TLT"]
    assert manifest["failed_adapters"] == ["TLT"]
    assert manifest["adapter_status"]["TLT"] == {"source": "L.O.D.E. FRED", "degraded": True, "stale_days": None}
