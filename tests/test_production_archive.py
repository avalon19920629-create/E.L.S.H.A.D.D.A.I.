import csv
import json
from pathlib import Path

from el_shaddai.production_archive import ARCHIVE_ITEMS, archive_production_run, resolve_archive_root
from el_shaddai.production_manifest import SAFETY_BOUNDARY


def _manifest(*, safety=None):
    return {
        "schema_version": "production_run_manifest.v1",
        "generated_at": "2026-06-13T14:30:12+00:00",
        "run_date": "2026-06-13",
        "inputs": {
            "el_shaddai_audit": {
                "price_data_status": "OK",
                "fred_data_status": "OK",
                "fred_provider": "fredapi",
                "degraded_adapters": ["TIP"],
                "failed_adapters": ["TLT"],
            },
            "parallax_report": {
                "parallax_state": "context_mixed",
                "dominant_market_regime": "yield",
                "secondary_market_regime": "growth",
                "high_attention_assets": ["BTC", "TLT"],
            },
        },
        "quality_gate": {
            "status": "warn",
            "label": "Production audit completed with warnings",
            "warnings_count": 9,
        },
        "safety": safety or dict(SAFETY_BOUNDARY),
    }


def _artifacts(path: Path, *, complete=True, safety=None):
    path.mkdir()
    names = ARCHIVE_ITEMS if complete else ("production_run_manifest.json", "market_amedas_snapshot.json")
    for name in names:
        target = path / name
        if name == "fred_cache":
            target.mkdir()
            (target / "cache.json").write_text("{}", encoding="utf-8")
        elif name == "production_run_manifest.json":
            target.write_text(json.dumps(_manifest(safety=safety)), encoding="utf-8")
        else:
            target.write_text("{}", encoding="utf-8")


def test_archive_copies_artifacts_updates_latest_and_indexes(tmp_path):
    output = tmp_path / "output"
    root = tmp_path / "archive"
    _artifacts(output)

    result = archive_production_run(output, root, update_latest=True)

    destination = Path(result["archive_path"])
    assert result["status"] == "archived"
    assert result["missing_files"] == []
    assert all((destination / name).exists() for name in ARCHIVE_ITEMS)
    assert all((root / "latest" / name).exists() for name in ARCHIVE_ITEMS)
    index = json.loads((root / "archive_index.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == "lumus8_production_archive_index.v1"
    assert len(index["runs"]) == 1
    run = index["runs"][0]
    assert run["quality_gate_status"] == "warn"
    assert run["warnings_count"] == 9
    assert run["fred_provider"] == "fredapi"
    assert run["price_data_status"] == "OK"
    assert run["fred_data_status"] == "OK"
    assert run["failed_adapters"] == ["TLT"]
    assert run["safety"] == SAFETY_BOUNDARY
    assert run["safety_ok"] is True
    with (root / "archive_index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["high_attention_assets"] == "BTC,TLT"
    assert rows[0]["failed_adapters_count"] == "1"


def test_archive_appends_runs_and_uses_collision_safe_directories(tmp_path, monkeypatch):
    output = tmp_path / "output"
    root = tmp_path / "archive"
    _artifacts(output)

    first = archive_production_run(output, root)
    second = archive_production_run(output, root)

    assert first["run_id"] != second["run_id"]
    index = json.loads((root / "archive_index.json").read_text(encoding="utf-8"))
    assert len(index["runs"]) == 2


def test_missing_files_and_broken_safety_are_recorded_without_stopping(tmp_path):
    output = tmp_path / "output"
    root = tmp_path / "archive"
    broken_safety = {**SAFETY_BOUNDARY, "automatic_trading": True}
    _artifacts(output, complete=False, safety=broken_safety)

    result = archive_production_run(output, root)

    assert result["status"] == "warning"
    assert "parallax_context_report.json" in result["missing_files"]
    assert result["safety_ok"] is False
    assert any("safety boundary" in item for item in result["archive_warnings"])
    assert (root / "archive_index.json").is_file()


def test_corrupted_index_is_backed_up_and_rebuilt(tmp_path):
    output = tmp_path / "output"
    root = tmp_path / "archive"
    _artifacts(output)
    root.mkdir()
    (root / "archive_index.json").write_text("{broken", encoding="utf-8")

    result = archive_production_run(output, root)

    backup = Path(result["corrupt_index_backup"])
    assert backup.name == "archive_index.json.bak"
    assert backup.read_text(encoding="utf-8") == "{broken"
    index = json.loads((root / "archive_index.json").read_text(encoding="utf-8"))
    assert len(index["runs"]) == 1


def test_drive_path_falls_back_to_local_root_when_drive_is_not_mounted(tmp_path, monkeypatch):
    monkeypatch.setattr("el_shaddai.production_archive.DRIVE_MOUNT_ROOT", tmp_path / "missing-drive")
    monkeypatch.setattr("el_shaddai.production_archive.DEFAULT_LOCAL_ARCHIVE_ROOT", tmp_path / "local-archive")
    monkeypatch.setattr("el_shaddai.production_archive._is_drive_path", lambda path: True)

    assert resolve_archive_root("/content/drive/MyDrive/lumus8_production") == tmp_path / "local-archive"
