from pathlib import Path

from el_shaddai.integrated_audit import _demo

FORBIDDEN_METADATA = ("codex-terminal-citation", "terminal_chunk_id", "line_range_start", "line_range_end")


def test_market_amedas_scenario_stdout_and_file_are_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert _demo("market_amedas_20260606") == 0
    stdout = capsys.readouterr().out
    report = Path("artifacts/demo/el_shaddai_integrated_audit_market_amedas_20260606.md")
    assert report.is_file() and report.stat().st_size > 0
    assert not any(token in stdout.lower() for token in FORBIDDEN_METADATA)
    assert not any(token in report.read_text(encoding="utf-8").lower() for token in FORBIDDEN_METADATA)


def test_market_amedas_20260606_uses_observed_values():
    from el_shaddai.integrated_audit import _demo_inputs, run_integrated_audit

    audits, portfolio, market = _demo_inputs("market_amedas_20260606")
    assert market.air_mass == {"yield": 50.2, "growth": 44.7, "defense": 4.4, "inflation": 0.7}
    assert market.updrafts["value"] == 0.48
    assert market.downdrafts == {"cash": 0.0, "commodity": -0.14, "gold": -0.28, "btc": -0.54}
    result = run_integrated_audit(audits, portfolio, market)
    assert all(row["wound_level"] == 0 for row in result["asset_health_rank"])
    assert all(row["role_evidence_score"] > 0 for row in result["asset_health_rank"])


def test_demo_markdown_and_stdout_remove_incomplete_terminal_metadata(tmp_path, monkeypatch, capsys):
    import el_shaddai.integrated_audit as integrated_audit

    original_demo_inputs = integrated_audit._demo_inputs
    bad = "\u200b:codex-terminal-citation[codex-terminal-citation]{line_range_start=80 line_range_end=85 terminal_chunk_id=結論サマリー】"

    def contaminated_demo_inputs(scenario):
        audits, portfolio, market = original_demo_inputs(scenario)
        audits[0].diagnosis_summary = bad
        return audits, portfolio, market

    monkeypatch.setattr(integrated_audit, "_demo_inputs", contaminated_demo_inputs)
    monkeypatch.chdir(tmp_path)
    assert integrated_audit._demo("market_amedas_20260606") == 0
    stdout = capsys.readouterr().out.lower()
    markdown = Path("artifacts/demo/el_shaddai_integrated_audit_market_amedas_20260606.md").read_text(encoding="utf-8").lower()

    assert not any(token in stdout for token in FORBIDDEN_METADATA)
    assert not any(token in markdown for token in FORBIDDEN_METADATA)
