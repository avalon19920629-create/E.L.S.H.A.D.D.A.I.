"""Archive L.U.M.U.S.-8 production artifacts without changing audit decisions."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .production_manifest import SAFETY_BOUNDARY

ARCHIVE_INDEX_SCHEMA_VERSION = "lumus8_production_archive_index.v1"
DRIVE_MOUNT_ROOT = Path("/content/drive/MyDrive")
DEFAULT_DRIVE_ARCHIVE_ROOT = DRIVE_MOUNT_ROOT / "lumus8_production"
DEFAULT_LOCAL_ARCHIVE_ROOT = Path("/content/lumus8_production/archive")
ARCHIVE_ITEMS = (
    "market_amedas_snapshot.json",
    "el_shaddai_lumus8_audit.json",
    "el_shaddai_lumus8_audit.md",
    "el_shaddai_report.md",
    "el_shaddai_scores.csv",
    "el_shaddai_dashboard.html",
    "parallax_context_report.json",
    "parallax_context_report.md",
    "production_run_manifest.json",
    "fred_cache",
)
REQUIRED_ARCHIVE_ITEMS = frozenset({
    "production_run_manifest.json",
    "parallax_context_report.json",
    "parallax_context_report.md",
    "el_shaddai_lumus8_audit.json",
    "market_amedas_snapshot.json",
})
CSV_COLUMNS = (
    "run_id", "run_date", "generated_at", "archive_path", "quality_gate_status",
    "warnings_count", "parallax_state", "dominant_market_regime", "secondary_market_regime",
    "high_attention_assets", "price_data_status", "fred_data_status", "fred_provider",
    "degraded_adapters_count", "failed_adapters_count",
)


def _read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_drive_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(Path("/content/drive").resolve())
    except ValueError:
        return False
    return True


def resolve_archive_root(archive_root: str | Path | None = None) -> Path:
    """Select Drive when mounted, otherwise use the local Colab archive root."""
    requested = Path(archive_root).expanduser() if archive_root is not None else DEFAULT_DRIVE_ARCHIVE_ROOT
    if _is_drive_path(requested) and not DRIVE_MOUNT_ROOT.is_dir():
        return DEFAULT_LOCAL_ARCHIVE_ROOT
    return requested


def _copy_item(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _fresh_run_destination(root: Path, now: datetime) -> tuple[str, Path]:
    date_part = now.date().isoformat()
    time_part = now.strftime("run_%H%M%S")
    parent = root / date_part
    destination = parent / time_part
    sequence = 1
    while destination.exists():
        destination = parent / f"{time_part}_{sequence:03d}"
        sequence += 1
    return f"{date_part}/{destination.name}", destination


def _backup_corrupt_index(index_path: Path) -> Path:
    candidate = index_path.with_name(index_path.name + ".bak")
    sequence = 1
    while candidate.exists():
        candidate = index_path.with_name(f"{index_path.name}.bak.{sequence:03d}")
        sequence += 1
    shutil.move(index_path, candidate)
    return candidate


def _load_index(index_path: Path) -> tuple[dict[str, Any], Path | None]:
    if not index_path.exists():
        return {"schema_version": ARCHIVE_INDEX_SCHEMA_VERSION, "runs": []}, None
    index = _read_mapping(index_path)
    if index is None or not isinstance(index.get("runs"), list):
        backup = _backup_corrupt_index(index_path)
        return {"schema_version": ARCHIVE_INDEX_SCHEMA_VERSION, "runs": []}, backup
    index["schema_version"] = ARCHIVE_INDEX_SCHEMA_VERSION
    return index, None


def _manifest_summary(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest = manifest or {}
    inputs = manifest.get("inputs", {}) if isinstance(manifest.get("inputs"), Mapping) else {}
    audit = inputs.get("el_shaddai_audit", {}) if isinstance(inputs.get("el_shaddai_audit"), Mapping) else {}
    parallax = inputs.get("parallax_report", {}) if isinstance(inputs.get("parallax_report"), Mapping) else {}
    quality = manifest.get("quality_gate", {}) if isinstance(manifest.get("quality_gate"), Mapping) else {}
    checks = quality.get("checks", {}) if isinstance(quality.get("checks"), Mapping) else {}
    safety = manifest.get("safety", {}) if isinstance(manifest.get("safety"), Mapping) else {}
    warning_summary = manifest.get("warning_summary", {}) if isinstance(manifest.get("warning_summary"), Mapping) else {}
    return {
        "generated_at": manifest.get("generated_at"),
        "quality_gate_status": quality.get("status", "unknown"),
        "quality_gate_label": quality.get("label", "unknown"),
        "warnings_count": quality.get("warnings_count", warning_summary.get("count", 0)),
        "parallax_state": parallax.get("parallax_state"),
        "dominant_market_regime": parallax.get("dominant_market_regime"),
        "secondary_market_regime": parallax.get("secondary_market_regime"),
        "high_attention_assets": list(parallax.get("high_attention_assets", []) or []),
        "price_data_status": audit.get("price_data_status", checks.get("price_data_status", "unknown")),
        "fred_data_status": audit.get("fred_data_status", checks.get("fred_data_status", "unknown")),
        "fred_provider": audit.get("fred_provider", checks.get("fred_provider", "unknown")),
        "degraded_adapters": list(audit.get("degraded_adapters", checks.get("degraded_adapters", [])) or []),
        "failed_adapters": list(audit.get("failed_adapters", checks.get("failed_adapters", [])) or []),
        "safety": dict(safety),
    }


def _write_index_csv(path: Path, runs: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for run in runs:
            row = {key: run.get(key) for key in CSV_COLUMNS}
            row["high_attention_assets"] = ",".join(map(str, run.get("high_attention_assets", [])))
            row["degraded_adapters_count"] = len(run.get("degraded_adapters", []))
            row["failed_adapters_count"] = len(run.get("failed_adapters", []))
            writer.writerow(row)


def render_archive_summary(result: Mapping[str, Any]) -> str:
    """Render a concise Colab-friendly archive result."""
    return "\n".join([
        "=" * 60,
        "PRODUCTION ARCHIVE",
        "=" * 60,
        f"Status       : {result.get('status')}",
        f"Run ID       : {result.get('run_id')}",
        f"Archive path : {result.get('archive_path')}",
        f"Latest path  : {result.get('latest_path') or 'not updated'}",
        f"Index        : {result.get('index_path')}",
        f"Copied files : {len(result.get('generated_files', []))}",
        f"Missing files: {result.get('missing_files', [])}",
        f"Safety       : {'OK' if result.get('safety_ok') else 'WARNING'}",
        "=" * 60,
    ])


def archive_production_run(
    output_dir: str | Path,
    archive_root: str | Path | None = None,
    *,
    update_latest: bool = True,
) -> dict[str, Any]:
    """Copy one production run, update latest, and append searchable indexes."""
    source_root = Path(output_dir).expanduser().resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"OUTPUT_DIR does not exist: {source_root}")

    root = resolve_archive_root(archive_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    run_id, destination = _fresh_run_destination(root, now)
    destination.mkdir(parents=True)

    generated_files: list[str] = []
    missing_files: list[str] = []
    for name in ARCHIVE_ITEMS:
        source = source_root / name
        if source.exists():
            _copy_item(source, destination / name)
            generated_files.append(name)
        else:
            missing_files.append(name)

    latest_path: Path | None = None
    if update_latest:
        latest_path = root / "latest"
        if latest_path.is_dir() and not latest_path.is_symlink():
            shutil.rmtree(latest_path)
        elif latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        shutil.copytree(destination, latest_path)

    manifest = _read_mapping(source_root / "production_run_manifest.json")
    summary = _manifest_summary(manifest)
    safety_ok = all(summary["safety"].get(key) == expected for key, expected in SAFETY_BOUNDARY.items())
    archive_warnings: list[str] = []
    missing_required = sorted(REQUIRED_ARCHIVE_ITEMS.intersection(missing_files))
    if missing_required:
        archive_warnings.append(f"Required archive artifacts are missing: {', '.join(missing_required)}")
    if manifest is None:
        archive_warnings.append("production_run_manifest.json is missing or invalid")
    if not safety_ok:
        archive_warnings.append("advisory-only safety boundary is not intact")
    status = "archived" if not archive_warnings else "warning"

    entry = {
        "run_id": run_id,
        "run_date": now.date().isoformat(),
        **summary,
        "generated_at": summary.get("generated_at") or now.isoformat(),
        "archive_path": str(destination),
        "latest_updated": update_latest,
        "safety_ok": safety_ok,
        "archive_status": status,
        "archive_warnings": archive_warnings,
        "generated_files": generated_files,
        "missing_files": missing_files,
    }
    index_path = root / "archive_index.json"
    index, corrupt_backup = _load_index(index_path)
    index["updated_at"] = now.isoformat()
    index["runs"].append(entry)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = root / "archive_index.csv"
    _write_index_csv(csv_path, index["runs"])

    result = {
        **entry,
        "index_path": str(index_path),
        "csv_index_path": str(csv_path),
        "latest_path": str(latest_path) if latest_path else None,
        "corrupt_index_backup": str(corrupt_backup) if corrupt_backup else None,
        "status": status,
    }
    print(render_archive_summary(result))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive L.U.M.U.S.-8 production artifacts")
    parser.add_argument("--output-dir", required=True, help="Directory containing production artifacts")
    parser.add_argument("--archive-root", help="Archive root; Drive path falls back locally when Drive is unavailable")
    parser.add_argument("--update-latest", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = archive_production_run(args.output_dir, args.archive_root, update_latest=args.update_latest)
    return 0 if result["status"] in {"archived", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
