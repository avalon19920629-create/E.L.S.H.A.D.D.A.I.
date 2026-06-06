import pytest

from el_shaddai.integrated_audit import health_level_for, run_integrated_audit
from el_shaddai.labels import HEALTH_LABELS_JA
from el_shaddai.models import AssetAuditInput, MarketAmedasInput, PortfolioInput

ASSETS = ("VT", "BTC", "TLT", "TIP", "GLDM", "XLRE", "BNDX", "DBC")
ENGINES = {"VT": "O.R.A.C.L.E.", "BTC": "O.R.A.C.L.E.", "TLT": "L.O.D.E.", "TIP": "I.N.F.E.R.N.O.", "GLDM": "A.U.R.A.", "XLRE": "A.R.C.A.D.I.A.", "BNDX": "A.T.L.A.S.", "DBC": "G.A.I.A."}


def audits(score=80, **kwargs):
    return [AssetAuditInput(asset, ENGINES[asset], score, confidence_level=kwargs.pop("confidence_level", 3), **kwargs) for asset in ASSETS]


def portfolio(previous_action_level=None):
    return PortfolioInput({asset: 1 / 8 for asset in ASSETS}, previous_action_level=previous_action_level)


def test_asset_scores_are_clamped_and_health_labels_are_assigned():
    inputs = audits(80)
    inputs[0].role_health_score = 150
    inputs[1].role_health_score = -20
    result = run_integrated_audit(inputs, portfolio())
    by_asset = {row["asset"]: row for row in result["asset_health_rank"]}
    assert by_asset["VT"]["asset_health_score"] == 100
    assert by_asset["BTC"]["asset_health_score"] == 0
    assert by_asset["VT"]["health_label"] == HEALTH_LABELS_JA[5]
    assert health_level_for(75) == 4
    assert health_level_for(60) == 3


def test_low_score_is_wounded_but_never_an_automatic_sell_recommendation():
    result = run_integrated_audit(audits(20), portfolio())
    combined = " ".join(result["recommended_actions"] + result["not_recommended_actions"] + [result["report_text"]])
    assert "自動売却" in combined or "機械的に売却しない" in combined
    assert result["portfolio_adjustment_recommendation"]["advisory_only"] is True
    assert all("売却する" not in action for action in result["recommended_actions"])


def test_hysteresis_downgrades_first_adjustment_but_level_four_is_immediate():
    warning = run_integrated_audit(audits(58), portfolio())
    assert warning["raw_action_level"] == 2
    assert warning["action_level"] == 1
    assert "2回連続" in warning["hysteresis_note"]

    collapse = run_integrated_audit(audits(10, wound_level=3), portfolio())
    assert collapse["action_level"] == 4


def test_structured_result_has_sanctuary_rank_wounds_roles_and_report():
    result = run_integrated_audit(audits(80), portfolio())
    required = {"sanctuary_health_score", "lumus_global_judgment", "portfolio_adjustment_recommendation", "asset_health_rank", "wounded_assets", "role_group_diagnosis", "report_text"}
    assert required <= result.keys()
    assert len(result["asset_health_rank"]) == 8
    assert len(result["role_group_diagnosis"]) == 5
    assert 0 <= result["sanctuary_health_score"] <= 100


def test_price_weakness_is_separate_from_role_wound():
    inputs = audits(68)
    inputs[0].risk_flags = ["price_weakness"]
    inputs[1].risk_flags = ["role_impairment"]
    result = run_integrated_audit(inputs, portfolio())
    by_asset = {row["asset"]: row for row in result["asset_health_rank"]}
    assert by_asset["VT"]["wound_level"] == 0
    assert by_asset["BTC"]["wound_level"] >= 1


def test_market_weather_alone_cannot_raise_action_to_adjustment():
    market = MarketAmedasInput({"yield": 100, "growth": 0, "defense": 0, "inflation": 0}, {}, {}, {}, "negative divergence")
    without = run_integrated_audit(audits(80), portfolio())
    with_weather = run_integrated_audit(audits(80), portfolio(), market)
    assert without["action_level"] < 2
    assert with_weather["action_level"] < 2


def test_persistent_adjustment_warning_can_remain_advisory_level_two():
    result = run_integrated_audit(audits(58), portfolio(previous_action_level=2))
    assert result["raw_action_level"] == 2
    assert result["action_level"] == 2
    assert result["portfolio_adjustment_recommendation"]["advisory_only"] is True


def test_explicit_wound_level_from_engine_is_respected():
    inputs = audits(90)
    inputs[0].wound_level = 2
    result = run_integrated_audit(inputs, portfolio())
    vt = next(row for row in result["asset_health_rank"] if row["asset"] == "VT")
    assert vt["wound_level"] == 2
