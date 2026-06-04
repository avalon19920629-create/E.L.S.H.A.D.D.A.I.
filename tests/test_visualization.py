from pathlib import Path

from el_shaddai.data_loader import load_sample_prices
from el_shaddai.scoring import score_all
from el_shaddai.visualization import NEUTRAL_ROLE_WARNING, write_html


def test_html_contains_executive_summary_and_neutral_role_warning(tmp_path: Path):
    prices, data_date = load_sample_prices(260)
    scores = score_all(prices, {}, data_date)

    path = write_html(scores, tmp_path)
    html = path.read_text(encoding="utf-8")

    assert "Executive Summary" in html
    assert "Top Genki-dama candidate" in html
    assert "Permanent Holdings / Value Opportunity Only" in html
    assert NEUTRAL_ROLE_WARNING in html
    assert "High Price Opportunity / High Role" in html
    assert "<details><summary>" in html


def test_html_omits_neutral_warning_when_role_inputs_are_non_neutral(tmp_path: Path):
    prices, data_date = load_sample_prices(260)
    scores = score_all(prices, {"TLT": {"recession_pressure": 1.0}}, data_date)

    path = write_html(scores, tmp_path)
    html = path.read_text(encoding="utf-8")

    assert NEUTRAL_ROLE_WARNING not in html
