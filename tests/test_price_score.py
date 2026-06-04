from el_shaddai.price_score import score_price


def test_price_score_rewards_drawdown():
    falling = [100 - i * 0.2 for i in range(260)]
    rising = [50 + i * 0.2 for i in range(260)]

    assert score_price("VT", falling).score > score_price("VT", rising).score


def test_price_score_handles_missing_history_neutrally():
    result = score_price("VT", [])

    assert result.score == 50.0
    assert "neutral fallback" in result.reasons[0]
