from pathlib import Path

from el_shaddai.report import write_markdown
from el_shaddai.role_score import score_role
from el_shaddai.scoring import score_all


def test_tlt_multiple_fiscal_penalties_cap_role_score():
    result = score_role(
        "TLT",
        {
            "TLT": {
                "recession_pressure": 2,
                "yield_curve": 2,
                "real_rate": 2,
                "us_10y_yield": 2,
                "us_30y_yield": 2,
                "debt_sustainability": -2,
                "interest_burden": -2,
                "foreign_demand": -2,
            }
        },
    )

    assert result.raw_weighted_score == 70.0
    assert result.score == 45.0
    assert result.penalty_adjusted_score == 45.0
    assert result.penalty_score == 0.0
    assert any("severe risk cap" in cap for cap in result.applied_caps)


def test_gldm_macro_independence_core_impairment_lowers_score():
    result = score_role(
        "GLDM",
        {
            "GLDM": {
                "macro_independence": -2,
                "currency_hedge": -2,
                "safe_haven_pressure": 0,
                "inflation_regime": 0,
                "liquidity_regime": 2,
                "dominant_anchor_strength": 2,
                "central_bank_buying": 0,
                "geopolitical_risk": 0,
                "real_rate": 0,
                "dxy": 0,
            }
        },
    )

    assert result.core_score < 30.0
    assert result.score <= 50.0
    assert any("core role impairment" in cap for cap in result.applied_caps)


def test_gldm_neutral_placeholders_do_not_dilute_strong_core():
    result = score_role(
        "GLDM",
        {
            "GLDM": {
                "macro_independence": 2,
                "currency_hedge": 2,
                "safe_haven_pressure": 2,
                "inflation_regime": 2,
                "liquidity_regime": 0,
                "dominant_anchor_strength": 0,
                "central_bank_buying": 0,
                "geopolitical_risk": 0,
                "real_rate": 0,
                "dxy": 0,
            }
        },
    )

    assert result.raw_weighted_score < result.score
    assert result.core_score == 100.0
    assert result.score >= 85.0


def test_role_aggregation_metrics_are_reported(tmp_path: Path):
    prices = {asset: [100 - i * 0.1 for i in range(260)] for asset in ["VT", "BNDX", "TLT", "TIP", "XLRE", "GLDM", "DBC", "BTC"]}
    scores = score_all(prices, {}, "2026-01-01")
    path = write_markdown(scores, tmp_path, "test")
    text = path.read_text(encoding="utf-8")

    assert "## Role Component Weights" in text
    assert "raw_weighted_score" in text
    assert "penalty_adjusted_score" in text
    assert "core_score" in text
    assert "role_interpretation" in text
