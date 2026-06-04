from pathlib import Path

from el_shaddai import cli
from el_shaddai.aura_adapter import AuraResult
from el_shaddai.config import ROLE_COMPONENT_WEIGHTS
from el_shaddai.lode_adapter import LodeResult


def test_manual_csv_inputs_generate_real_proxies(tmp_path: Path):
    output_dir = tmp_path / "manual"

    assert cli.main([
        "--lode-inputs-csv",
        "data/sample_lode_inputs.csv",
        "--aura-prices-csv",
        "data/sample_aura_prices.csv",
        "--output-dir",
        str(output_dir),
    ]) == 0

    csv_text = (output_dir / "el_shaddai_scores.csv").read_text(encoding="utf-8")
    report_text = (output_dir / "el_shaddai_report.md").read_text(encoding="utf-8")

    assert "TLT,62.43,50.00,50.00" not in csv_text
    assert "GLDM,46.03,50.00,46.03" not in csv_text
    assert "manual L.O.D.E. CSV" in report_text
    assert "manual A.U.R.A. CSV" in report_text


def test_live_adapter_failures_do_not_break_cli(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "latest_tlt_role_inputs",
        lambda: LodeResult(
            role_inputs={"TLT": {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["TLT"]}},
            proxies={name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["TLT"]},
            reasons={},
            warnings=["warning: FRED 403 simulated; neutral TLT Role proxy fallback applied."],
            data_date="unknown",
            source="test",
            used_lode=False,
        ),
    )
    monkeypatch.setattr(
        cli,
        "latest_gldm_role_inputs",
        lambda: AuraResult(
            role_inputs={"GLDM": {name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["GLDM"]}},
            proxies={name: 0.0 for name in ROLE_COMPONENT_WEIGHTS["GLDM"]},
            reasons={},
            warnings=["warning: yfinance missing simulated; neutral GLDM Role proxy fallback applied."],
            data_date="unknown",
            source="test",
            used_aura=False,
            correlations={},
            dominant_anchor="N/A",
            dominant_correlation=0.0,
            gri_score=0.0,
            gri_interpretation="neutral fallback",
        ),
    )

    assert cli.main(["--use-lode-tlt-role", "--use-aura-gldm-role", "--output-dir", str(tmp_path / "fallback")]) == 0


def test_diagnose_data_sources_outputs_environment_state(capsys, monkeypatch):
    monkeypatch.setattr(
        cli,
        "latest_tlt_role_inputs",
        lambda: LodeResult({"TLT": {}}, {}, {}, ["warning: lode fallback reason"], "unknown", "test", False),
    )
    monkeypatch.setattr(
        cli,
        "latest_gldm_role_inputs",
        lambda: AuraResult({"GLDM": {}}, {}, {}, ["warning: aura fallback reason"], "unknown", "test", False, {}, "N/A", 0.0, 0.0, "neutral fallback"),
    )

    assert cli.main(["--diagnose-data-sources"]) == 0
    out = capsys.readouterr().out

    assert "Data source diagnostics" in out
    assert "yfinance import:" in out
    assert "FRED endpoint:" in out
    assert "L.O.D.E. fetch: fallback" in out
    assert "A.U.R.A. fetch: fallback" in out
    assert "warning: lode fallback reason" in out
    assert "warning: aura fallback reason" in out
