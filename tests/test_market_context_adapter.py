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
