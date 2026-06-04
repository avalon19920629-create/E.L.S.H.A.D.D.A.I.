from el_shaddai.config import ROLE_COMPONENT_WEIGHTS
from el_shaddai.role_score import proxy_to_score, score_role


def test_role_score_not_applied_to_vt_or_btc():
    assert score_role("VT").score is None
    assert score_role("BTC").score is None


def test_role_score_uses_direction_adjusted_proxy_inputs():
    assert "direction-adjusted" in (proxy_to_score.__doc__ or "")
    weak = score_role("TLT", {"TLT": {name: -2 for name in ROLE_COMPONENT_WEIGHTS["TLT"]}})
    strong = score_role("TLT", {"TLT": {name: 2 for name in ROLE_COMPONENT_WEIGHTS["TLT"]}})

    assert weak.score == 0.0
    assert strong.score == 100.0


def test_role_score_falls_back_to_neutral_when_weights_sum_to_zero(monkeypatch):
    monkeypatch.setitem(ROLE_COMPONENT_WEIGHTS, "TLT", {"recession_pressure": 0.0, "real_rate": 0.0})

    result = score_role("TLT", {"TLT": {"recession_pressure": 2, "real_rate": -2}})

    assert result.score == 50.0
    assert result.components == {"recession_pressure": 100.0, "real_rate": 0.0}
    assert any("weights sum to 0" in reason for reason in result.reasons)


def test_role_score_warns_about_unknown_inputs():
    result = score_role("TLT", {"TLT": {"foo": 1, "bar": -1}})

    assert any("warning: ignored unknown role input(s): bar, foo" == reason for reason in result.reasons)
