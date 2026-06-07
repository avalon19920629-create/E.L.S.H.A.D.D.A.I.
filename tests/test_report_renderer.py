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
    from el_shaddai.integrated_audit import _demo_inputs

    audits, portfolio, market = _demo_inputs("market_amedas_20260606")
    audits[0].wound_level = 1
    audits[0].diagnosis_summary = "確認対象 :codex-terminal-citation[codex-terminal-citation]{metadata}"
    report = run_integrated_audit(audits, portfolio, market)["report_text"]
    assert ":codex-terminal-citation" not in report
    assert "{metadata}" not in report
    assert "主要気団の比率（Market Amedas観測値）：利回り気団 50.2%、成長気団 44.7%、防衛気団 4.4%、インフレ気団 0.7%" in report
    assert "主要な上昇流：バリュー +0.48、ナスダック +0.41、高配当 +0.37、REIT +0.36、米国株 +0.33" in report
    assert "主要な下降流：BTC -0.54、金 -0.28、商品 -0.14、現金 0.00" in report
    assert "BTCセンサー：デジタルゴールド (Summer) モード" in report
    assert "BTC注意：" in report
    assert "危機時分散の実測評価は含まれていない" in report


def test_market_scenario_summary_and_recommendations_are_specific():
    from el_shaddai.integrated_audit import _demo_inputs

    audits, portfolio, market = _demo_inputs("market_amedas_20260606")
    report = run_integrated_audit(audits, portfolio, market)["report_text"]
    assert "個別アセットに明確な役割負傷はないが" in report
    assert "景気後退防衛" in report and "危機時退避グループを次回監査で確認する" in report
    assert "BTCは成長気団が強い中で下降流にあるため" in report
    assert "Market Amedas単独では売却・配分変更を正当化しない" in report
    assert "低スコア資産を機械的に売却しない" in report
    assert "市場文脈だけでは負傷扱いにしない" in report
    assert "自動売買を実行しない" in report
