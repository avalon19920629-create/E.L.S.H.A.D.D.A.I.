from el_shaddai.scoring import label_for, score_asset


def test_permanent_asset_uses_price_only():
    score = score_asset("BTC", [100 - i * 0.1 for i in range(260)], {}, "2026-01-01")

    assert score.role_score is None
    assert score.el_shaddai_score == score.price_score


def test_non_permanent_asset_uses_min_of_price_and_role():
    score = score_asset("TLT", [100 - i * 0.1 for i in range(260)], {"TLT": {"recession_pressure": -2, "us_10y_yield": -2, "us_30y_yield": -2, "yield_curve": -2, "real_rate": -2, "debt_sustainability": -2, "interest_burden": -2, "foreign_demand": -2}}, "2026-01-01")

    assert score.role_score == 0.0
    assert score.el_shaddai_score == 0.0
    assert score.label == "Risk"


def test_labels_for_permanent_and_role_assets():
    assert label_for("VT", 85) == "Spot Buy Candidate"
    assert label_for("GLDM", 85) == "Strong Opportunity"
