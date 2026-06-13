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


def test_fred_api_key_prefers_fredapi_over_configured_provider(monkeypatch):
    import pandas as pd

    calls = []

    class FakeFred:
        def __init__(self, *, api_key):
            calls.append(("init", api_key))

        def get_series(self, series_id, *, observation_start, observation_end):
            calls.append((series_id, observation_start, observation_end))
            return pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))

    monkeypatch.setenv("FRED_API_KEY", "colab-secret")
    monkeypatch.setitem(sys.modules, "fredapi", SimpleNamespace(Fred=FakeFred))

    from el_shaddai.fred_data import fetch_fred_series_rows

    rows = fetch_fred_series_rows(["DGS10"], "2026-01-01", "2026-01-02", provider="pandas_datareader")

    assert calls == [
        ("init", "colab-secret"),
        ("DGS10", "2026-01-01", "2026-01-02"),
    ]
    assert rows == [
        {"date": "2026-01-01", "DGS10": 1.0},
        {"date": "2026-01-02", "DGS10": 2.0},
    ]


def test_no_fred_api_key_preserves_configured_keyless_provider(monkeypatch):
    import pandas as pd

    calls = []

    class FakeFredReader:
        def __init__(self, series_ids, **kwargs):
            calls.append((series_ids, kwargs))

        def read(self):
            return pd.DataFrame({"DGS10": [4.5]}, index=pd.to_datetime(["2026-01-02"]))

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "pandas_datareader", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "pandas_datareader.fred", SimpleNamespace(FredReader=FakeFredReader))

    from el_shaddai.fred_data import fetch_fred_series_rows

    rows = fetch_fred_series_rows(["DGS10"], "2026-01-01", "2026-01-02", provider="pandas_datareader")

    assert calls[0][0] == ["DGS10"]
    assert rows == [{"date": "2026-01-02", "DGS10": 4.5}]


def test_successful_lode_and_inferno_fetches_do_not_emit_neutral_fallback_warnings(monkeypatch):
    monkeypatch.setattr("el_shaddai.lode_adapter.fetch_lode_fred_data", lambda *_args, **_kwargs: _lode_rows())
    monkeypatch.setattr("el_shaddai.inferno_adapter.fetch_inferno_fred_data", lambda *_args, **_kwargs: _inferno_rows())

    lode = latest_tlt_role_inputs()
    inferno = latest_tip_role_inputs()

    assert lode.used_lode and not lode.degraded
    assert inferno.used_inferno and not inferno.degraded
    assert not any("neutral TLT Role proxy fallback applied" in warning for warning in lode.warnings)
    assert not any("neutral TIP Role proxy fallback applied" in warning for warning in inferno.warnings)


def test_fredapi_failure_warnings_name_route_and_keep_audit_alive(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "colab-secret")
    monkeypatch.setattr("el_shaddai.lode_adapter.fetch_lode_fred_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("read timeout")))
    monkeypatch.setattr("el_shaddai.inferno_adapter.fetch_inferno_fred_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("read timeout")))

    lode = latest_tlt_role_inputs(cache_dir=str(tmp_path / "lode"))
    inferno = latest_tip_role_inputs(cache_dir=str(tmp_path / "inferno"))

    assert lode.degraded and not lode.used_lode
    assert inferno.degraded and not inferno.used_inferno
    assert "via fredapi" in lode.warnings[0]
    assert "neutral TLT Role proxy fallback applied" in lode.warnings[0]
    assert "via fredapi" in inferno.warnings[0]
    assert "neutral TIP Role proxy fallback applied" in inferno.warnings[0]


def test_successful_fred_adapters_are_healthy_and_report_effective_fredapi_provider(tmp_path: Path, monkeypatch):
    from el_shaddai.inferno_adapter import compute_tip_role_proxies
    from el_shaddai.lode_adapter import compute_tlt_role_proxies

    monkeypatch.setenv("FRED_API_KEY", "colab-secret")
    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=json.load))
    config = tmp_path / "production.json"
    config.write_text(json.dumps({
        "price_data": {"provider": "yfinance", "period": "1y"},
        "fred": {"provider": "pandas_datareader", "cache_dir": str(tmp_path / "cache")},
        "role_adapters": {"enabled": ["TLT", "TIP"]}, "oracle": {"enabled": False},
        "portfolio": {"target_weights": {asset: 0.125 for asset in ASSETS}},
    }), encoding="utf-8")
    monkeypatch.setattr("el_shaddai.production.fetch_live_prices", lambda _period: ({asset: [100 + i for i in range(320)] for asset in ASSETS}, "2026-06-08"))
    monkeypatch.setattr("el_shaddai.production.ROLE_ADAPTERS", {
        "TLT": lambda **_kwargs: compute_tlt_role_proxies(_lode_rows()),
        "TIP": lambda **_kwargs: compute_tip_role_proxies(_inferno_rows()),
    })

    paths = run_production(config, tmp_path / "out")
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    report = paths["lumus8_report_markdown"].read_text(encoding="utf-8")

    assert manifest["warnings"] == []
    assert manifest["warning_summary"] == {"count": 0, "items": []}
    assert manifest["degraded_assets"] == []
    assert manifest["failed_adapters"] == []
    assert manifest["adapter_status"]["TLT"]["degraded"] is False
    assert manifest["adapter_status"]["TIP"]["degraded"] is False
    assert "・FREDデータ：OK（provider: fredapi）" in report
    assert "neutral TLT Role proxy fallback applied" not in report
    assert "neutral TIP Role proxy fallback applied" not in report
