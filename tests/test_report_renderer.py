from el_shaddai.integrated_audit import run_integrated_audit
from el_shaddai.models import AssetAuditInput, PortfolioInput
from el_shaddai.report_renderer import REQUIRED_SECTIONS


def test_report_is_japanese_and_contains_all_required_sections_and_actions():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    result = run_integrated_audit([AssetAuditInput(a, e, 80) for a, e in names], PortfolioInput({a: 0.125 for a, _ in names}))
    report = result["report_text"]
    for section in REQUIRED_SECTIONS:
        assert f"【{section}】" in report
    assert result["recommended_actions"]
    assert result["not_recommended_actions"]
    assert "Market Amedas単独では売却・配分変更を正当化しない" in report
    assert "低スコアは自動売却を意味しない" in report


def test_report_translates_internal_market_flags_and_avoids_false_wound_instruction():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    result = run_integrated_audit([AssetAuditInput(a, e, 80) for a, e in names], PortfolioInput({a: 0.125 for a, _ in names}))
    report = result["report_text"]
    assert "文脈フラグ：中立市場文脈" in report
    assert "文脈フラグ: neutral_market_context" not in report
    assert "負傷アセットを次回監査で重点確認する" not in report
    assert "内部役割健全度スコア" in report


def test_report_sanitizes_terminal_citations_and_expands_market_context():
    from el_shaddai.models import MarketAmedasInput

    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    audits = [AssetAuditInput(a, e, 80) for a, e in names]
    audits[0].wound_level = 1
    audits[0].diagnosis_summary = "確認対象 :codex-terminal-citation[terminal-output]"
    market = MarketAmedasInput({"yield": 62, "growth": 72, "defense": 28, "inflation": 32}, {}, {"VT": 78, "smallcap": 71, "junk": 65}, {"BTC": 76, "TLT": 64, "BNDX": 55}, "growth negative divergence")
    report = run_integrated_audit(audits, PortfolioInput({a: 0.125 for a, _ in names}), market)["report_text"]
    assert ":codex-terminal-citation[" not in report
    assert "主要気団の比率：" in report
    assert "主要気団の強弱：" in report
    assert "主要な上昇流：世界株式" in report
    assert "主要な下降流：BTC" in report
    assert "BTC注意：" in report
    assert "危機時分散の実測評価は含まれていない" in report


def test_market_scenario_summary_and_recommendations_are_specific():
    from el_shaddai.integrated_audit import _demo_inputs

    audits, portfolio, market = _demo_inputs("market_amedas_20260606")
    report = run_integrated_audit(audits, portfolio, market)["report_text"]
    assert "個別アセットに明確な役割負傷はないが" in report
    assert "景気後退防衛・危機時退避グループを次回監査で確認する" in report
    assert "BTCは成長気団が強い中で逆行しているため" in report
    assert "Market Amedas単独では売却・配分変更を正当化しない" in report
    assert "低スコア資産を機械的に売却しない" in report
    assert "市場文脈だけでは負傷扱いにしない" in report
    assert "自動売買を実行しない" in report
