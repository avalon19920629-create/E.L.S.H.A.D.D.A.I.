from pathlib import Path

from el_shaddai.integrated_audit import _demo


def test_market_amedas_scenario_stdout_and_file_are_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert _demo("market_amedas_20260606") == 0
    stdout = capsys.readouterr().out
    report = Path("artifacts/demo/el_shaddai_integrated_audit_market_amedas_20260606.md")
    assert report.is_file() and report.stat().st_size > 0
    assert ":codex-terminal-citation" not in stdout
    assert ":codex-terminal-citation" not in report.read_text(encoding="utf-8")


def test_market_amedas_20260606_uses_observed_values():
    from el_shaddai.integrated_audit import _demo_inputs, run_integrated_audit

    audits, portfolio, market = _demo_inputs("market_amedas_20260606")
    assert market.air_mass == {"yield": 50.2, "growth": 44.7, "defense": 4.4, "inflation": 0.7}
    assert market.updrafts["value"] == 0.48
    assert market.downdrafts == {"cash": 0.0, "commodity": -0.14, "gold": -0.28, "btc": -0.54}
    result = run_integrated_audit(audits, portfolio, market)
    assert all(row["wound_level"] == 0 for row in result["asset_health_rank"])
    assert all(row["role_evidence_score"] > 0 for row in result["asset_health_rank"])
