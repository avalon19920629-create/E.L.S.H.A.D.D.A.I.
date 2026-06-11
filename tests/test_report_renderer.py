from el_shaddai.integrated_audit import run_integrated_audit
from el_shaddai.models import AssetAuditInput, MarketAmedasInput, PortfolioInput
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
    assert "codex-terminal-citation" not in report.lower()
    assert "{metadata}" not in report
    assert "主要気団の比率（合計100%の構成比）：利回り気団 50.2%、成長気団 44.7%、防衛気団 4.4%、インフレ気団 0.7%" in report
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


def test_report_opens_with_conclusion_caveats_breakdown_and_knights_table():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    audits = [AssetAuditInput(a, e, 20, diagnosis_summary="proxy reason with many details; second detail that belongs in the asset report") for a, e in names]
    result = run_integrated_audit(audits, PortfolioInput({a: 0.125 for a, _ in names}))
    report = result["report_text"]

    assert report.index("【結論サマリー】") < report.index("【総合診断】")
    assert "負傷アセットは6件（内訳：構造負傷 6件）" in report
    assert "機会判定は2件 / degraded adaptersは0件 / failed adaptersは0件" in report
    assert "市場文脈補正なし" in report
    assert "危機時分散評価なし" in report
    assert "| asset | adapter | score | status | injury_type | one_line_summary | recommended_action |" in report
    assert "second detail that belongs in the asset report" not in report
    assert "詳細なproxy理由・指標値は詳細ログおよびasset reportを参照する。" in report


def test_oracle_assets_are_displayed_as_opportunity_judgments_not_role_injuries():
    inputs = [
        AssetAuditInput("VT", "O.R.A.C.L.E.", 50, wound_level=2),
        AssetAuditInput("BTC", "O.R.A.C.L.E.", 80),
        AssetAuditInput("TLT", "L.O.D.E.", 50, wound_level=2),
    ]
    result = run_integrated_audit(inputs, PortfolioInput({"VT": 1 / 3, "BTC": 1 / 3, "TLT": 1 / 3}))
    by_asset = {row["asset"]: row for row in result["asset_health_rank"]}

    assert by_asset["VT"]["injury_type"] == "追加買い判定"
    assert by_asset["VT"]["display_status"] == "追加買い候補"
    assert by_asset["BTC"]["injury_type"] == "機会判定"
    assert by_asset["BTC"]["display_status"] == "機会中立"
    assert by_asset["TLT"]["injury_type"] == "役割負傷"
    assert by_asset["TLT"]["display_status"] == by_asset["TLT"]["health_label"]
    assert "VT：役割負傷" not in result["report_text"]
    assert "| VT | O.R.A.C.L.E." in result["report_text"] and "| 追加買い候補 |" in result["report_text"]


def test_oracle_opportunities_are_excluded_from_wounded_count_and_rendered_separately():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    result = run_integrated_audit(
        [AssetAuditInput(asset, engine, 50, wound_level=2, diagnosis_summary=f"{engine.lower()}: value=50.00") for asset, engine in names],
        PortfolioInput({asset: 0.125 for asset, _ in names}),
        data_runtime={"degraded_assets": ["TLT"], "failed_adapters": ["TIP"]},
    )
    report = result["report_text"]
    wounded_assets = {row["asset"] for row in result["wounded_assets"]}
    opportunity_assets = {row["asset"] for row in result["opportunity_judgments"]}
    wounded_section = report.split("【負傷アセット】", 1)[1].split("【機会判定】", 1)[0]
    opportunity_section = report.split("【機会判定】", 1)[1].split("【役割グループ診断】", 1)[0]

    assert wounded_assets == {"TLT", "TIP", "GLDM", "XLRE", "BNDX", "DBC"}
    assert opportunity_assets == {"VT", "BTC"}
    assert "負傷アセットは6件（内訳：役割負傷 6件）" in report
    assert "機会判定は2件 / degraded adaptersは1件 / failed adaptersは1件" in report
    assert "・VT：追加買い判定" not in wounded_section
    assert "・BTC：追加買い判定" not in wounded_section
    assert "・VT：追加買い判定 / o.r.a.c.l.e.: value=50.00 / 既存ルール内で追加買い機会を確認" in opportunity_section
    assert "・BTC：追加買い判定 / o.r.a.c.l.e.: value=50.00 / 既存ルール内で追加買い機会を確認" in opportunity_section
    assert all(f"・{asset}：役割負傷" in wounded_section for asset in wounded_assets)
    assert "低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。" in report
    assert "自動売買を実行しない" in report


def test_next_checkpoints_keep_oracle_opportunities_separate_from_real_wounds():
    inputs = [
        AssetAuditInput("BTC", "O.R.A.C.L.E.", 50, wound_level=1),
        AssetAuditInput("VT", "O.R.A.C.L.E.", 50, wound_level=1),
        AssetAuditInput("TLT", "L.O.D.E.", 50, wound_level=1),
    ]
    result = run_integrated_audit(inputs, PortfolioInput({"BTC": 1 / 3, "VT": 1 / 3, "TLT": 1 / 3}))

    assert "BTCの追加買い候補判定が継続するか確認する。" in result["next_checkpoints"]
    assert "VTの追加買い候補判定が継続するか確認する。" in result["next_checkpoints"]
    assert "・BTCの追加買い候補判定が継続するか確認する。" in result["report_text"]
    assert "・VTの追加買い候補判定が継続するか確認する。" in result["report_text"]
    assert "BTCの1. 価格負傷が継続するか確認する。" not in result["report_text"]
    assert "VTの1. 価格負傷が継続するか確認する。" not in result["report_text"]
    assert "TLTの1. 価格負傷が継続するか確認する。" in result["next_checkpoints"]


def test_report_labels_independent_market_amedas_values_as_strength_not_ratio():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."), ("GLDM", "A.U.R.A."), ("XLRE", "A.R.C.A.D.I.A."), ("BNDX", "A.T.L.A.S."), ("DBC", "G.A.I.A."))
    market = MarketAmedasInput(
        {"yield": 60, "growth": 70, "defense": 35, "inflation": 45}, {}, {}, {}
    )
    report = run_integrated_audit(
        [AssetAuditInput(asset, engine, 80) for asset, engine in names],
        PortfolioInput({asset: 0.125 for asset, _ in names}),
        market,
    )["report_text"]

    assert "主要気団の強度（各気団の独立スコア）：利回り気団 60.0 / 100" in report
    assert "主要気団の比率" not in report


def test_data_completeness_reports_missing_optional_inputs_without_asset_injury_or_secrets():
    names = (("VT", "O.R.A.C.L.E."), ("BTC", "O.R.A.C.L.E."), ("TLT", "L.O.D.E."), ("TIP", "I.N.F.E.R.N.O."))
    result = run_integrated_audit(
        [AssetAuditInput(asset, engine, 80) for asset, engine in names],
        PortfolioInput({asset: 0.25 for asset, _ in names}),
        data_runtime={"fred_provider": "fredapi", "degraded_assets": [], "failed_adapters": [], "FRED_API_KEY": "never-render-this"},
    )
    report = result["report_text"]

    assert "【データ完全性】" in report
    assert "・価格データ：OK" in report
    assert "・FREDデータ：OK（provider: fredapi）" in report
    assert "・Market Amedas：未入力" in report
    assert "・相関構造：未入力" in report
    assert "・degraded adapters：なし" in report
    assert "・failed adapters：なし" in report
    assert "監査完全性：暫定監査（文脈未接続監査）" in report
    assert "理由：Market Amedas未入力 / 相関構造未入力" in report
    assert "今回の総合状態は、Market Amedasおよび相関構造が未入力のため、文脈未接続の暫定判定です。" in report
    assert "総合状態と推奨運用判断は、文脈未接続の参考判定として確認してください。" in report
    assert "暫定判定は自動売買・自動売却を意味しません。" in report
    assert "低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。" in report
    assert "never-render-this" not in report
    assert result["wounded_assets"] == []


def test_data_completeness_reports_degraded_and_failed_adapters_and_available_optional_inputs():
    market = MarketAmedasInput({}, {}, {}, {})
    audits = [
        AssetAuditInput("TLT", "L.O.D.E.", 80, supporting_metrics={"correlation_integrity_score": 90}),
        AssetAuditInput("TIP", "I.N.F.E.R.N.O.", 80),
        AssetAuditInput("GLDM", "A.U.R.A.", 80),
    ]
    report = run_integrated_audit(
        audits,
        PortfolioInput({"TLT": 1 / 3, "TIP": 1 / 3, "GLDM": 1 / 3}),
        market,
        data_runtime={"fred_provider": "pandas_datareader", "degraded_assets": ["GLDM", "TLT"], "failed_adapters": ["TIP"]},
    )["report_text"]

    assert "・FREDデータ：failed（provider: pandas_datareader）" in report
    assert "・Market Amedas：入力あり" in report
    assert "・相関構造：入力あり" in report
    assert "・degraded adapters：GLDM、TLT" in report
    assert "・failed adapters：TIP" in report


def test_data_completeness_reports_fred_degraded_when_fred_adapter_is_degraded_but_not_failed():
    report = run_integrated_audit(
        [AssetAuditInput("TLT", "L.O.D.E.", 80)],
        PortfolioInput({"TLT": 1.0}),
        data_runtime={"fred_provider": "fredapi", "degraded_assets": ["TLT"], "failed_adapters": []},
    )["report_text"]

    assert "・FREDデータ：degraded（provider: fredapi）" in report
    assert "・degraded adapters：TLT" in report
    assert "・failed adapters：なし" in report


def test_market_amedas_missing_marks_audit_as_provisional_without_adding_asset_injury():
    audits = [
        AssetAuditInput("TLT", "L.O.D.E.", 80, supporting_metrics={"correlation_integrity_score": 90}),
        AssetAuditInput("TIP", "I.N.F.E.R.N.O.", 80),
    ]
    result = run_integrated_audit(
        audits,
        PortfolioInput({"TLT": 0.5, "TIP": 0.5}),
        data_runtime={"fred_provider": "fredapi", "degraded_assets": [], "failed_adapters": []},
    )
    report = result["report_text"]

    assert result["data_completeness"]["audit_integrity"] == "暫定監査"
    assert result["data_completeness"]["audit_integrity_reasons"] == ["Market Amedas未入力"]
    assert "監査完全性：暫定監査（文脈未接続監査）" in report
    assert "理由：Market Amedas未入力" in report
    assert "今回の総合状態は、Market Amedasが未入力のため、文脈未接続の暫定判定です。" in report
    assert "データ接続：FRED OK / degraded adapters なし / failed adapters なし" in report
    assert result["wounded_assets"] == []


def test_correlation_missing_marks_audit_as_provisional_without_adding_asset_injury():
    market = MarketAmedasInput({}, {}, {}, {})
    result = run_integrated_audit(
        [AssetAuditInput("TLT", "L.O.D.E.", 80), AssetAuditInput("TIP", "I.N.F.E.R.N.O.", 80)],
        PortfolioInput({"TLT": 0.5, "TIP": 0.5}),
        market,
    )
    report = result["report_text"]

    assert result["data_completeness"]["audit_integrity"] == "暫定監査"
    assert result["data_completeness"]["audit_integrity_reasons"] == ["相関構造未入力"]
    assert "監査完全性：暫定監査（文脈未接続監査）" in report
    assert "理由：相関構造未入力" in report
    assert "今回の総合状態は、相関構造が未入力のため、文脈未接続の暫定判定です。" in report
    assert result["wounded_assets"] == []


def test_available_market_amedas_and_correlation_render_normal_integrated_audit():
    market = MarketAmedasInput({}, {}, {}, {})
    result = run_integrated_audit(
        [AssetAuditInput("TLT", "L.O.D.E.", 80, supporting_metrics={"correlation_integrity_score": 90})],
        PortfolioInput({"TLT": 1.0}),
        market,
    )
    report = result["report_text"]

    assert result["data_completeness"]["audit_integrity"] == "統合監査"
    assert result["data_completeness"]["audit_integrity_reasons"] == []
    assert "監査完全性：統合監査（文脈接続済み）" in report
    assert "Market Amedasおよび相関構造を接続した通常の統合監査です。" in report
    assert "暫定監査" not in report
    assert "文脈未接続の暫定判定" not in report


def test_xlre_high_price_warning_with_preserved_rental_function_is_not_rendered_as_collapse():
    inputs = [
        AssetAuditInput(
            "XLRE", "A.R.C.A.D.I.A.", 22.88,
            diagnosis_summary="52w range position=98.0; z-score=1.80; weekly return=3.0%; role headwinds",
            supporting_metrics={
                "price_score": 22.88,
                "role_score": 43.74,
                "final_score": 22.88,
                "core_score": 58.46,
                "rental_cashflow": 85.72,
                "price_components": {
                    "range_52w_position": 2.0,
                    "z_score": 5.0,
                    "weekly_drawdown": 20.0,
                    "range_5y_position": 35.0,
                },
                "role_components": {
                    "rental_cashflow": 85.72,
                    "reit_relative_strength": 7.30,
                    "credit_stress": 0.00,
                    "real_rate_shock": 25.88,
                },
            },
        ),
        AssetAuditInput("TLT", "L.O.D.E.", 20, diagnosis_summary="通常の役割負傷"),
    ]
    result = run_integrated_audit(inputs, PortfolioInput({"XLRE": 0.5, "TLT": 0.5}))
    by_asset = {row["asset"]: row for row in result["asset_health_rank"]}
    xlre = by_asset["XLRE"]
    report = result["report_text"]

    assert xlre["display_status"] == "構造逆風"
    assert xlre["injury_type"] == "価格警戒＋役割逆風"
    assert xlre["display_status"] != "0. 戦闘不能"
    assert "価格崩壊" not in report
    assert "価格警戒：高値圏 / 追加買い非推奨" in report
    assert "役割逆風：金利・信用・相対劣後" in report
    assert "中核機能：地代キャッシュフロー機能は残存" in report
    assert "構造崩壊ではなく、価格警戒と外部環境逆風の複合判定" in report
    assert "XLREは売却ではなく、次回監査で金利・信用・REIT相対強度を重点確認する。" in result["next_checkpoints"]
    assert "低スコアは自動売却を意味しない。固定比率と既存の乖離ルールを優先する。" in report
    assert "監査結果から自動売買を実行しない。" in report
    assert by_asset["TLT"]["display_status"] == "0. 戦闘不能"
    assert by_asset["TLT"]["injury_type"] == "構造負傷"


def test_xlre_low_price_score_without_preserved_core_uses_normal_injury_labels():
    audit = AssetAuditInput(
        "XLRE", "A.R.C.A.D.I.A.", 20,
        supporting_metrics={
            "price_score": 20, "role_score": 40, "core_score": 45, "rental_cashflow": 40,
            "price_components": {"range_52w_position": 0, "z_score": 0},
        },
    )
    result = run_integrated_audit([audit], PortfolioInput({"XLRE": 1.0}))
    xlre = result["asset_health_rank"][0]

    assert xlre["display_status"] == "0. 戦闘不能"
    assert xlre["injury_type"] == "構造負傷"
    assert xlre["interpretation_notes"] == []
