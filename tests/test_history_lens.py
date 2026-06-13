import csv
import json
import subprocess
import sys

import pytest

from el_shaddai.history_lens import load_archive_index, render_history_markdown, run_history_lens


def _run(number, *, attention, warnings, gate="warn", safety_ok=True):
    return {
        "run_id": f"2026-06-{number:02d}/run_020250",
        "run_date": f"2026-06-{number:02d}",
        "generated_at": f"2026-06-{number:02d}T02:02:50+00:00",
        "quality_gate_status": gate,
        "warnings_count": warnings,
        "parallax_state": "context_mixed" if number != 3 else "context_divergence",
        "dominant_market_regime": "yield" if number != 2 else "growth",
        "secondary_market_regime": "growth",
        "high_attention_assets": attention,
        "price_data_status": "OK",
        "fred_data_status": "OK" if number != 3 else "DEGRADED",
        "fred_provider": "fredapi",
        "degraded_adapters": ["TIP"] if number == 2 else [],
        "failed_adapters": ["TLT"] if number == 3 else [],
        "safety_ok": safety_ok,
    }


def _index(path):
    runs = [
        _run(1, attention=["BTC", "VT"], warnings=1, gate="pass"),
        _run(2, attention=["BTC", "TLT"], warnings=2),
        _run(3, attention=["BTC", "VT"], warnings=9, safety_ok=False),
    ]
    path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    return runs


def test_basic_aggregation_and_data_integrity(tmp_path):
    index = tmp_path / "archive_index.json"
    _index(index)

    report = run_history_lens(index, tmp_path / "out", recent_n=3)["report"]

    assert report["run_count"] == 3
    assert report["date_range"] == {"first_run_date": "2026-06-01", "last_run_date": "2026-06-03"}
    assert report["quality_gate"]["counts"] == {"pass": 1, "warn": 2, "fail": 0, "unknown": 0}
    assert report["warnings"]["trend"] == "rising"
    assert report["parallax"]["state_counts"] == {"context_divergence": 1, "context_mixed": 2}
    assert report["market_regime"]["dominant_counts"] == {"growth": 1, "yield": 2}
    assert report["high_attention_assets"]["counts"] == {"BTC": 3, "VT": 2, "TLT": 1}
    assert report["high_attention_assets"]["persistent_recent"] == ["BTC", "VT"]
    assert report["data_integrity"]["price_data_status_counts"] == {"OK": 3}
    assert report["data_integrity"]["fred_data_status_counts"] == {"DEGRADED": 1, "OK": 2}
    assert report["data_integrity"]["degraded_adapter_runs"] == 1
    assert report["data_integrity"]["failed_adapter_runs"] == 1
    assert report["data_integrity"]["safety_ok_runs"] == 2
    assert report["data_integrity"]["safety_warning_runs"] == 1


def test_missing_fields_are_unknown_and_empty_index_is_reported(tmp_path):
    index = tmp_path / "archive_index.json"
    index.write_text(json.dumps({"runs": [{"run_id": "old/run"}]}), encoding="utf-8")

    report = run_history_lens(index, tmp_path / "out")["report"]
    assert report["quality_gate"]["counts"] == {"pass": 0, "warn": 0, "fail": 0, "unknown": 1}
    assert report["parallax"]["state_counts"] == {"unknown": 1}
    assert report["warnings"]["latest_count"] == "unknown"
    assert report["data_integrity"]["safety_unknown_runs"] == 1

    index.write_text(json.dumps({"runs": []}), encoding="utf-8")
    empty = run_history_lens(index, tmp_path / "empty")["report"]
    assert empty["run_count"] == 0
    assert empty["date_range"]["first_run_date"] is None


def test_csv_lists_counts_and_unknown_safety(tmp_path):
    index = tmp_path / "archive_index.csv"
    with index.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run_id", "run_date", "high_attention_assets", "degraded_adapters_count", "failed_adapters_count"])
        writer.writeheader()
        writer.writerow({"run_id": "one", "run_date": "2026-06-01", "high_attention_assets": "['BTC', 'VT']", "degraded_adapters_count": "1", "failed_adapters_count": "0"})
        writer.writerow({"run_id": "two", "run_date": "2026-06-02", "high_attention_assets": "BTC, TLT", "degraded_adapters_count": "0", "failed_adapters_count": "1"})

    report = run_history_lens(index, tmp_path / "out", recent_n=2)["report"]
    assert report["high_attention_assets"]["counts"] == {"BTC": 2, "TLT": 1, "VT": 1}
    assert report["data_integrity"]["degraded_adapter_runs"] == 1
    assert report["data_integrity"]["failed_adapter_runs"] == 1
    assert report["data_integrity"]["safety_unknown_runs"] == 2


def test_markdown_and_output_formats_do_not_direct_actions(tmp_path):
    index = tmp_path / "archive_index.json"
    _index(index)
    result = run_history_lens(index, tmp_path / "out", recent_n=2)
    markdown = (tmp_path / "out" / "history_lens_report.md").read_text(encoding="utf-8")

    for expected in ("L.U.M.U.S.-8 History Lens Report v0.1", "結論サマリー", "直近", "高注意資産", "安全境界"):
        assert expected in markdown
    for prohibited in ("売却する", "買う", "追加投資する", "配分変更する", "ロスカットする", "自動売買"):
        assert prohibited not in markdown
    assert json.loads((tmp_path / "out" / "history_lens_report.json").read_text(encoding="utf-8"))["run_count"] == 3
    assert render_history_markdown(result["report"]) == markdown


def test_missing_index_and_invalid_recent_n_are_clear(tmp_path):
    with pytest.raises(FileNotFoundError, match="Archive index does not exist"):
        load_archive_index(tmp_path / "missing.json")
    index = tmp_path / "archive_index.json"
    _index(index)
    with pytest.raises(ValueError, match="recent_n"):
        run_history_lens(index, tmp_path / "out", recent_n=0)


def test_module_cli_help():
    completed = subprocess.run([sys.executable, "-m", "el_shaddai.history_lens", "--help"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    assert "--archive-index" in completed.stdout
