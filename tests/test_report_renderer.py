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
