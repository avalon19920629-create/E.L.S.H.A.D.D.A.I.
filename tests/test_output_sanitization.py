from dataclasses import replace

from el_shaddai.data_loader import load_sample_prices
from el_shaddai.report import write_markdown
from el_shaddai.scoring import score_all
from el_shaddai.text_sanitizer import safe_print, sanitize_output_text
from el_shaddai.visualization import write_html

CITATION = ":codex-terminal-citation[codex-terminal-citation]{metadata}"


def test_sanitizer_removes_terminal_citation_token_and_metadata_completely():
    cleaned = sanitize_output_text(f"before {CITATION} after")

    assert cleaned == "before  after"
    assert "codex-terminal-citation" not in cleaned.lower()
    assert "metadata" not in cleaned


def test_markdown_html_and_stdout_never_emit_terminal_citation(tmp_path, capsys):
    prices, data_date = load_sample_prices(260)
    scores = score_all(prices, {}, data_date)
    scores[0] = replace(scores[0], main_reason=f"reason {CITATION}")

    markdown = write_markdown(scores, tmp_path, f"source {CITATION}").read_text(encoding="utf-8")
    html = write_html(scores, tmp_path).read_text(encoding="utf-8")
    safe_print(f"warning {CITATION}")
    stdout = capsys.readouterr().out

    for output in (markdown, html, stdout):
        assert "codex-terminal-citation" not in output.lower()
        assert "metadata" not in output
