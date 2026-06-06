from pathlib import Path

from el_shaddai import cli
from el_shaddai.config import ROLE_COMPONENT_WEIGHTS
from el_shaddai.gaia_adapter import (
    GaiaResult,
    compute_dbc_role_proxies,
    dbc_role_inputs_from_csv,
    latest_dbc_role_inputs,
)
from el_shaddai.report import write_markdown
from el_shaddai.role_score import score_role
from el_shaddai.scoring import score_all


def _base_prices(days: int = 90):
    return {
        "DBC": [25 + i * 0.04 + ((i % 5) - 2) * 0.02 for i in range(days)],
        "USO": [70 + i * 0.08 + ((i % 4) - 1.5) * 0.03 for i in range(days)],
        "UNG": [15 + i * 0.03 + ((i % 6) - 2.5) * 0.01 for i in range(days)],
        "GLD": [180 + i * 0.12 + ((i % 7) - 3) * 0.04 for i in range(days)],
        "CPER": [25 + i * 0.03 + ((i % 3) - 1) * 0.02 for i in range(days)],
        "DBA": [20 + i * 0.02 + ((i % 4) - 1.5) * 0.01 for i in range(days)],
        "SPY": [430 + i * 0.05 + ((i % 8) - 3.5) * 0.04 for i in range(days)],
        "UUP": [28 - i * 0.005 + ((i % 5) - 2) * 0.003 for i in range(days)],
        "TIP": [105 + i * 0.02 + ((i % 6) - 2.5) * 0.01 for i in range(days)],
        "GLDM": [36 + i * 0.03 + ((i % 7) - 3) * 0.008 for i in range(days)],
        "TLT": [94 - i * 0.01 + ((i % 5) - 2) * 0.01 for i in range(days)],
        "BNDX": [49 - i * 0.004 + ((i % 5) - 2) * 0.004 for i in range(days)],
        "__dates__": [f"2026-04-{(i % 30) + 1:02d}" for i in range(days)],
    }


def test_sample_gaia_prices_csv_generates_dbc_proxies():
    result = dbc_role_inputs_from_csv("data/sample_gaia_prices.csv")

    assert result.used_gaia is True
    assert set(result.role_inputs["DBC"]) == set(ROLE_COMPONENT_WEIGHTS["DBC"])
    assert all(-2.0 <= value <= 2.0 for value in result.proxies.values())
    assert result.source == "manual G.A.I.A. CSV: data/sample_gaia_prices.csv"


def test_dbc_rise_makes_commodity_trend_positive():
    result = compute_dbc_role_proxies(_base_prices())

    assert result.proxies["commodity_trend"] > 0.0


def test_uso_ung_rise_makes_energy_leadership_positive():
    prices = _base_prices()
    prices["USO"] = [70 + i * 0.3 + ((i % 4) - 1.5) * 0.02 for i in range(90)]
    prices["UNG"] = [15 + i * 0.15 + ((i % 5) - 2) * 0.01 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["energy_leadership"] > 0.0


def test_cper_gld_rise_makes_metals_leadership_positive():
    prices = _base_prices()
    prices["GLD"] = [180 + i * 0.5 + ((i % 7) - 3) * 0.03 for i in range(90)]
    prices["CPER"] = [25 + i * 0.12 + ((i % 4) - 1.5) * 0.01 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["metals_leadership"] > 0.0


def test_dba_rise_makes_agriculture_leadership_positive():
    prices = _base_prices()
    prices["DBA"] = [20 + i * 0.15 + ((i % 4) - 1.5) * 0.01 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["agriculture_leadership"] > 0.0


def test_uup_rise_makes_dollar_headwind_negative():
    prices = _base_prices()
    prices["UUP"] = [28 + i * 0.08 + ((i % 5) - 2) * 0.004 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["dollar_headwind"] < 0.0


def test_weak_dbc_and_strong_tip_tlt_bndx_makes_deflation_drag_negative():
    prices = _base_prices()
    prices["DBC"] = [25 - i * 0.04 + ((i % 5) - 2) * 0.02 for i in range(90)]
    prices["TIP"] = [105 + i * 0.08 + ((i % 6) - 2.5) * 0.01 for i in range(90)]
    prices["TLT"] = [94 + i * 0.10 + ((i % 5) - 2) * 0.01 for i in range(90)]
    prices["BNDX"] = [49 + i * 0.04 + ((i % 5) - 2) * 0.004 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["deflation_drag"] < 0.0


def test_isolated_dbc_rise_without_subsector_breadth_makes_commodity_noise_negative():
    prices = _base_prices()
    prices["DBC"] = [25 + i * 0.08 + ((i % 5) - 2) * 0.02 for i in range(90)]
    for ticker in ("USO", "UNG", "GLD", "CPER", "DBA"):
        prices[ticker] = [prices[ticker][0] - i * 0.01 + ((i % 4) - 1.5) * 0.005 for i in range(90)]

    result = compute_dbc_role_proxies(prices)

    assert result.proxies["commodity_noise"] < 0.0


def test_dbc_caps_60_45_40_30_are_applied():
    all_good = {name: 2.0 for name in ROLE_COMPONENT_WEIGHTS["DBC"]}

    cap60 = score_role("DBC", {"DBC": all_good | {"dollar_headwind": -2.0}})
    cap45 = score_role("DBC", {"DBC": all_good | {"dollar_headwind": -2.0, "deflation_drag": -2.0}})
    cap40 = score_role("DBC", {"DBC": all_good | {"growth_collapse": -2.0, "commodity_noise": -2.0}})
    cap30 = score_role("DBC", {"DBC": all_good | {"dollar_headwind": -2.0, "deflation_drag": -2.0, "growth_collapse": -2.0}})

    assert cap60.score <= 60.0 and any("60" in cap for cap in cap60.applied_caps)
    assert cap45.score <= 45.0 and any("45" in cap for cap in cap45.applied_caps)
    assert cap40.score <= 40.0 and any("40" in cap for cap in cap40.applied_caps)
    assert cap30.score <= 30.0 and any("30" in cap for cap in cap30.applied_caps)


def test_manual_csv_route_reports_used_gaia_data_true(tmp_path: Path):
    assert cli.main(["--gaia-prices-csv", "data/sample_gaia_prices.csv", "--output-dir", str(tmp_path)]) == 0
    report = (tmp_path / "el_shaddai_report.md").read_text(encoding="utf-8")

    assert "Used G.A.I.A. data: True" in report


def test_cli_gaia_fallback_exits_cleanly(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "latest_dbc_role_inputs",
        lambda: GaiaResult(
            {"DBC": {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["DBC"]}},
            {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["DBC"]},
            {name: "neutral fallback" for name in ROLE_COMPONENT_WEIGHTS["DBC"]},
            ["warning: gaia fallback"],
            "unknown",
            "test",
            False,
            {},
            [],
            "Gaia Dormant - Commodity role is neutral or inactive.",
        ),
    )

    assert cli.main(["--use-gaia-dbc-role", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "el_shaddai_report.md").exists()


def test_report_includes_gaia_raw_adjusted_groups_caps_and_interpretation(tmp_path: Path):
    prices = {asset: [100 - i * 0.1 for i in range(260)] for asset in ["VT", "BNDX", "TLT", "TIP", "XLRE", "GLDM", "DBC", "BTC"]}
    gaia = dbc_role_inputs_from_csv("data/sample_gaia_prices.csv")
    scores = score_all(prices, gaia.role_inputs, "2026-04-30")
    report_path = write_markdown(scores, tmp_path, "test", gaia_result=gaia)
    text = report_path.read_text(encoding="utf-8")

    assert "## DBC Role inputs generated by G.A.I.A." in text
    assert "Raw metrics:" in text
    assert "Role raw_weighted_score" in text
    assert "Role penalty_adjusted_score" in text
    assert "Role core_score" in text
    assert "Role support_score" in text
    assert "Role penalty_score" in text
    assert "Role applied_caps" in text
    assert "Commodity regime interpretation:" in text
    assert "G.A.I.A. commodity_regime_interpretation:" in text
    assert "Proxy table:" in text


def test_latest_dbc_role_inputs_falls_back_on_fetch_failure(monkeypatch):
    monkeypatch.setattr("el_shaddai.gaia_adapter.fetch_gaia_price_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no data")))

    result = latest_dbc_role_inputs()

    assert result.used_gaia is False
    assert all(value == 0.0 for value in result.role_inputs["DBC"].values())
