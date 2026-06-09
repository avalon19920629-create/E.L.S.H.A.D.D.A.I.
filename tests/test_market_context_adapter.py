from el_shaddai.market_context_adapter import adapt_market_context
from el_shaddai.models import MarketAmedasInput


def observed_market():
    return MarketAmedasInput(
        {"yield": 50.2, "growth": 44.7, "defense": 4.4, "inflation": 0.7},
        {"usd_wind": "凪（影響なし）", "junk_oxygen": "正常（健全な上昇）", "smallcap_geothermal": "温暖（景気回復は本物）"},
        {"value": 0.48, "nasdaq": 0.41, "high_dividend": 0.37, "reit": 0.36, "us_equity": 0.33, "smallcap": 0.28},
        {"cash": 0.00, "commodity": -0.14, "gold": -0.28, "btc": -0.54}, "デジタルゴールド (Summer) モード",
    )


def test_missing_market_input_returns_neutral_context():
    context = adapt_market_context(None)
    assert context.market_context_flags == ["neutral_market_context"]
    assert all(value == 1.0 for value in context.regime_relevance_adjustments.values())
    assert "中立" in context.market_context_summary


def test_observed_market_flags_and_adjustments_are_safe_and_japanese():
    context = adapt_market_context(observed_market())
    expected = {"yield_air_mass_dominant", "growth_air_mass_strong", "defense_air_mass_absent", "inflation_air_mass_absent", "usd_wind_calm", "junk_oxygen_healthy", "smallcap_geothermal_warm", "btc_negative_divergence", "gold_commodity_weakness"}
    assert expected <= set(context.market_context_flags)
    assert all(0.9 <= value <= 1.1 for value in context.regime_relevance_adjustments.values())
    assert "売却判断に直結させない" in context.market_context_summary
    assert "利回り気団が強い" in context.market_context_summary
    assert "yield_air_mass_dominant" not in context.market_context_summary


def test_market_context_preserves_observed_air_masses_signed_flows_and_btc_divergence():
    context = adapt_market_context(observed_market())
    assert context.air_mass_ratios == {"利回り気団": 50.2, "成長気団": 44.7, "防衛気団": 4.4, "インフレ気団": 0.7}
    assert context.air_mass_measure == "ratio"
    assert context.top_updrafts[:5] == [
        {"name": "バリュー", "observed_value": 0.48}, {"name": "ナスダック", "observed_value": 0.41},
        {"name": "高配当", "observed_value": 0.37}, {"name": "REIT", "observed_value": 0.36}, {"name": "米国株", "observed_value": 0.33},
    ]
    assert context.top_downdrafts == [
        {"name": "BTC", "observed_value": -0.54}, {"name": "金", "observed_value": -0.28},
        {"name": "商品", "observed_value": -0.14}, {"name": "現金", "observed_value": 0.0},
    ]
    assert "成長気団が強い中で下降流" in context.btc_divergence_note
    assert context.btc_sensor_summary == "デジタルゴールド (Summer) モード"


def test_independent_air_mass_scores_are_identified_as_strengths():
    market = MarketAmedasInput({"yield": 60, "growth": 70, "defense": 35, "inflation": 45}, {}, {}, {})
    context = adapt_market_context(market)

    assert context.air_mass_measure == "strength"
    assert "60.0 / 100" in context.market_narratives[0]
