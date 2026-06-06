from el_shaddai.market_context_adapter import adapt_market_context
from el_shaddai.models import MarketAmedasInput


def test_missing_market_input_returns_neutral_context():
    context = adapt_market_context(None)
    assert context.market_context_flags == ["neutral_market_context"]
    assert all(value == 1.0 for value in context.regime_relevance_adjustments.values())
    assert "中立" in context.market_context_summary


def test_market_flags_and_adjustments_are_compact_and_bounded():
    context = adapt_market_context(MarketAmedasInput(
        {"yield": 90, "growth": 80, "defense": 20, "inflation": 20},
        {"junk_oxygen": "healthy", "smallcap_geothermal": "warm"}, {}, {"gold": 90, "commodity": 80}, "negative divergence",
    ))
    assert "yield_air_mass_dominant" in context.market_context_flags
    assert "btc_negative_divergence" in context.market_context_flags
    assert all(0.9 <= value <= 1.1 for value in context.regime_relevance_adjustments.values())
    assert "売却判断に直結させない" in context.market_context_summary
    assert "利回り気団が優勢" in context.market_context_summary
    assert "yield_air_mass_dominant" not in context.market_context_summary


def test_market_context_exposes_air_masses_flows_and_btc_divergence_in_japanese():
    context = adapt_market_context(MarketAmedasInput(
        {"yield": 62, "growth": 72, "defense": 28, "inflation": 32}, {},
        {"VT": 78, "smallcap": 71, "junk": 65, "XLRE": 53},
        {"BTC": 76, "TLT": 64, "BNDX": 55, "gold": 48}, "growth negative divergence",
    ))
    assert sum(context.air_mass_ratios.values()) == 100.0
    assert set(context.air_mass_strengths) == {"利回り気団", "成長気団", "防衛気団", "インフレ気団"}
    assert context.top_updrafts[0]["name"] == "世界株式"
    assert context.top_downdrafts[0]["name"] == "BTC"
    assert "成長気団が強い中で逆行" in context.btc_divergence_note
