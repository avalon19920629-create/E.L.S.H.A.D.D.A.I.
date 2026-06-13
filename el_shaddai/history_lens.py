"""Contextualize Production Archive history without changing audit decisions."""

from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .production_manifest import SAFETY_BOUNDARY

SCHEMA_VERSION = "lumus8_history_lens.v0.1"
UNKNOWN = "unknown"


def _text(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return UNKNOWN
    return str(value).strip()


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _items(value: Any) -> list[str]:
    """Normalize JSON lists and common CSV list representations."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item) != UNKNOWN]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = ast.literal_eval(stripped)
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, (list, tuple, set)):
                return [_text(item) for item in parsed if _text(item) != UNKNOWN]
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [_text(value)]


def _safety_state(run: Mapping[str, Any]) -> str:
    explicit = run.get("safety_ok")
    if isinstance(explicit, bool):
        return "ok" if explicit else "warning"
    safety = run.get("safety")
    if isinstance(safety, Mapping) and safety:
        intact = all(safety.get(key) == expected for key, expected in SAFETY_BOUNDARY.items())
        return "ok" if intact else "warning"
    return UNKNOWN


def _normalize_run(run: Mapping[str, Any]) -> dict[str, Any]:
    degraded = _items(run.get("degraded_adapters"))
    failed = _items(run.get("failed_adapters"))
    return {
        "run_id": _text(run.get("run_id")),
        "run_date": _text(run.get("run_date")),
        "generated_at": _text(run.get("generated_at")),
        "quality_gate_status": _text(run.get("quality_gate_status")).lower(),
        "warnings_count": _optional_integer(run.get("warnings_count")),
        "parallax_state": _text(run.get("parallax_state")),
        "dominant_market_regime": _text(run.get("dominant_market_regime")),
        "secondary_market_regime": _text(run.get("secondary_market_regime")),
        "high_attention_assets": _items(run.get("high_attention_assets")),
        "price_data_status": _text(run.get("price_data_status")),
        "fred_data_status": _text(run.get("fred_data_status")),
        "fred_provider": _text(run.get("fred_provider")),
        "degraded_adapters": degraded,
        "failed_adapters": failed,
        "degraded_adapters_count": _integer(run.get("degraded_adapters_count"), len(degraded)),
        "failed_adapters_count": _integer(run.get("failed_adapters_count"), len(failed)),
        "safety_state": _safety_state(run),
        "archive_path": _text(run.get("archive_path")),
        "generated_files": _items(run.get("generated_files")),
        "missing_files": _items(run.get("missing_files")),
    }


def load_archive_index(archive_index: str | Path) -> list[dict[str, Any]]:
    """Load and normalize runs from a Production Archive JSON or CSV index."""
    path = Path(archive_index).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Archive index does not exist: {path}")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            raw_runs: Sequence[Mapping[str, Any]] = list(csv.DictReader(handle))
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Archive index is not valid JSON: {path}") from exc
        if isinstance(payload, Mapping):
            raw_runs = payload.get("runs", [])
        else:
            raw_runs = payload
        if not isinstance(raw_runs, list):
            raise ValueError(f"Archive index runs must be a list: {path}")
    runs = [_normalize_run(run) for run in raw_runs if isinstance(run, Mapping)]
    return sorted(runs, key=lambda run: (run["run_date"], run["generated_at"], run["run_id"]))


def _counts(runs: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(_text(run.get(key)) for run in runs).items()))


def _quality_counts(runs: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(_text(run.get("quality_gate_status")) for run in runs)
    return {key: counts[key] for key in ("pass", "warn", "fail", UNKNOWN)} | {
        key: value for key, value in sorted(counts.items()) if key not in {"pass", "warn", "fail", UNKNOWN}
    }


def build_history_report(
    runs: Sequence[Mapping[str, Any]], *, source_index: str | Path, recent_n: int = 5
) -> dict[str, Any]:
    """Build a serializable History Lens summary from normalized or raw runs."""
    if recent_n < 1:
        raise ValueError("recent_n must be at least 1")
    normalized = [_normalize_run(run) if "safety_state" not in run else dict(run) for run in runs]
    normalized.sort(key=lambda run: (run["run_date"], run["generated_at"], run["run_id"]))
    latest = normalized[-1] if normalized else {}
    warning_values = [run["warnings_count"] for run in normalized if run["warnings_count"] is not None]
    warning_average = sum(warning_values) / len(warning_values) if warning_values else 0.0
    latest_warning = latest.get("warnings_count")
    if latest_warning is None:
        warning_trend = UNKNOWN if normalized else "stable"
    else:
        warning_trend = "rising" if latest_warning > warning_average + 2 else "falling" if latest_warning < warning_average - 2 else "stable"

    asset_counts = Counter(asset for run in normalized for asset in set(run["high_attention_assets"]))
    recent = normalized[-recent_n:]
    persistence_threshold = max(1, len(recent) - 1)
    recent_asset_counts = Counter(asset for run in recent for asset in set(run["high_attention_assets"]))
    persistent = sorted(asset for asset, count in recent_asset_counts.items() if count >= persistence_threshold)

    safety_counts = Counter(run["safety_state"] for run in normalized)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_index": str(Path(source_index).expanduser()),
        "run_count": len(normalized),
        "date_range": {
            "first_run_date": normalized[0]["run_date"] if normalized else None,
            "last_run_date": latest.get("run_date"),
        },
        "quality_gate": {"counts": _quality_counts(normalized), "latest_status": latest.get("quality_gate_status", UNKNOWN)},
        "warnings": {
            "latest_count": latest_warning if latest_warning is not None else UNKNOWN,
            "average_count": round(warning_average, 2),
            "trend": warning_trend,
            "series": [{"run_id": run["run_id"], "warnings_count": run["warnings_count"]} for run in normalized],
        },
        "parallax": {"latest_state": latest.get("parallax_state", UNKNOWN), "state_counts": _counts(normalized, "parallax_state")},
        "market_regime": {
            "dominant_counts": _counts(normalized, "dominant_market_regime"),
            "secondary_counts": _counts(normalized, "secondary_market_regime"),
            "latest_dominant": latest.get("dominant_market_regime", UNKNOWN),
            "latest_secondary": latest.get("secondary_market_regime", UNKNOWN),
        },
        "high_attention_assets": {
            "counts": dict(sorted(asset_counts.items(), key=lambda item: (-item[1], item[0]))),
            "latest": latest.get("high_attention_assets", []),
            "persistent_recent": persistent,
            "recent_window": len(recent),
            "persistence_threshold": persistence_threshold if recent else 0,
        },
        "data_integrity": {
            "price_data_status_counts": _counts(normalized, "price_data_status"),
            "fred_data_status_counts": _counts(normalized, "fred_data_status"),
            "fred_provider_counts": _counts(normalized, "fred_provider"),
            "failed_adapter_runs": sum(run["failed_adapters_count"] > 0 for run in normalized),
            "degraded_adapter_runs": sum(run["degraded_adapters_count"] > 0 for run in normalized),
            "safety_ok_runs": safety_counts["ok"],
            "safety_warning_runs": safety_counts["warning"],
            "safety_unknown_runs": safety_counts[UNKNOWN],
        },
        "recent_runs": recent,
    }
    return report


def _most_common(counts: Mapping[str, int]) -> str:
    return max(counts, key=lambda key: (counts[key], key)) if counts else UNKNOWN


def render_history_markdown(report: Mapping[str, Any]) -> str:
    """Render a human-readable, observation-only History Lens report."""
    date_range = report["date_range"]
    quality = report["quality_gate"]
    warnings = report["warnings"]
    parallax = report["parallax"]
    regime = report["market_regime"]
    assets = report["high_attention_assets"]
    integrity = report["data_integrity"]
    persistent = ", ".join(assets["persistent_recent"]) or "なし"
    lines = [
        "# L.U.M.U.S.-8 History Lens Report v0.1", "", "## 1. 結論サマリー", "",
        f"- 対象監査回数: {report['run_count']}",
        f"- 期間: {date_range['first_run_date'] or 'なし'} 〜 {date_range['last_run_date'] or 'なし'}",
        f"- 最新quality gate: {quality['latest_status']}", f"- 最新Parallax状態: {parallax['latest_state']}",
        f"- 最新主気団 / 副気団: {regime['latest_dominant']} / {regime['latest_secondary']}",
        f"- 継続高注意資産（直近{assets['recent_window']}回中{assets['persistence_threshold']}回以上）: {persistent}", "",
        "## 2. 直近監査一覧", "",
        "| Run ID | Date | Quality | Warnings | Parallax | Dominant | Secondary | High attention |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for run in report["recent_runs"]:
        attention = ", ".join(run["high_attention_assets"]) or "-"
        lines.append(f"| {run['run_id']} | {run['run_date']} | {run['quality_gate_status']} | {run['warnings_count']} | {run['parallax_state']} | {run['dominant_market_regime']} | {run['secondary_market_regime']} | {attention} |")
    lines += [
        "", "## 3. Warning推移", "", f"- 最新warning数: {warnings['latest_count']}",
        f"- 平均warning数: {warnings['average_count']}", f"- 傾向: {warnings['trend']}",
        "- 単発値と継続的な変化を分けて確認し、観測履歴を文脈化します。", "",
        "## 4. 市場regime履歴", "", f"- 主気団の最多: {_most_common(regime['dominant_counts'])}",
        f"- 副気団の最多: {_most_common(regime['secondary_counts'])}", "",
        "## 5. 高注意資産の出現回数", "", "| Asset | Count | Recent persistent |", "|---|---:|---|",
    ]
    for asset, count in assets["counts"].items():
        lines.append(f"| {asset} | {count} | {'yes' if asset in assets['persistent_recent'] else 'no'} |")
    lines += [
        "", "## 6. データ取得・安全境界の安定性", "",
        f"- price_data_status: {integrity['price_data_status_counts']}", f"- fred_data_status: {integrity['fred_data_status_counts']}",
        f"- failed adapter発生回数: {integrity['failed_adapter_runs']}", f"- degraded adapter発生回数: {integrity['degraded_adapter_runs']}",
        f"- safety OK回数: {integrity['safety_ok_runs']}", f"- safety warning回数: {integrity['safety_warning_runs']}",
        f"- safety unknown回数: {integrity['safety_unknown_runs']}", "", "## 7. 注意点", "",
        "History LensはProduction Archiveの監査ログを読み、観測履歴を文脈化する補助ビューアです。監査判定や資産配分を変更する機能ではありません。", "",
    ]
    return "\n".join(lines)


def run_history_lens(
    archive_index: str | Path, output_dir: str | Path, *, recent_n: int = 5, output_format: str = "both"
) -> dict[str, Any]:
    """Generate requested History Lens output files and return paths with report."""
    if output_format not in {"json", "markdown", "both"}:
        raise ValueError("output_format must be json, markdown, or both")
    runs = load_archive_index(archive_index)
    report = build_history_report(runs, source_index=archive_index, recent_n=recent_n)
    destination = Path(output_dir).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "history_lens_report.json"
    markdown_path = destination / "history_lens_report.md"
    if output_format in {"json", "both"}:
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output_format in {"markdown", "both"}:
        markdown_path.write_text(render_history_markdown(report), encoding="utf-8")
    return {"report": report, "json_path": str(json_path) if output_format in {"json", "both"} else None, "markdown_path": str(markdown_path) if output_format in {"markdown", "both"} else None}


def render_cli_summary(result: Mapping[str, Any]) -> str:
    report = result["report"]
    return "\n".join(["=" * 60, "L.U.M.U.S.-8 HISTORY LENS", "=" * 60, f"Runs        : {report['run_count']}", f"Date range  : {report['date_range']['first_run_date']} -> {report['date_range']['last_run_date']}", f"Latest gate : {report['quality_gate']['latest_status']}", f"Latest state: {report['parallax']['latest_state']}", f"Warning trend: {report['warnings']['trend']}", f"Persistent high attention: {', '.join(report['high_attention_assets']['persistent_recent']) or 'none'}", f"Output JSON : {result['json_path'] or 'not requested'}", f"Output MD   : {result['markdown_path'] or 'not requested'}", "=" * 60])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize L.U.M.U.S.-8 Production Archive history.")
    parser.add_argument("--archive-index", required=True, help="Path to archive_index.json or archive_index.csv")
    parser.add_argument("--output-dir", required=True, help="Directory for History Lens reports")
    parser.add_argument("--recent-n", type=int, default=5, help="Recent run window (default: 5)")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="both", dest="output_format")
    args = parser.parse_args(argv)
    result = run_history_lens(args.archive_index, args.output_dir, recent_n=args.recent_n, output_format=args.output_format)
    print(render_cli_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
