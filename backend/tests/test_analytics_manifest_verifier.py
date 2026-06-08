from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "verify_analytics_manifests.py"


def run_manifest_report(root: Path, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    report_path = tmp_path / "manifest-report.json"
    markdown_path = tmp_path / "manifest-report.md"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--analytics-root",
            str(root),
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_manifest_verifier_accepts_matching_manifest_and_hash(tmp_path: Path) -> None:
    root = tmp_path / "analytics"
    parquet_file = root / "parquet" / "daily_bars" / "part-000.parquet"
    parquet_file.parent.mkdir(parents=True)
    parquet_file.write_bytes(b"not-real-parquet-but-hashable")
    manifest = {
        "dataset_key": "daily_bars",
        "manifest_id": "daily_bars:test",
        "dataset_version": "daily_bars_20260608000101",
        "generated_at": "2026-06-08T00:01:01Z",
        "status": "active",
        "quality_status": "ok",
        "period_start": "2026-06-01",
        "period_end": "2026-06-08",
        "row_count": 1,
        "source": {"source_table": "daily_bar_snapshots"},
        "files": [{"path": "parquet/daily_bars/part-000.parquet", "rows": 1, "sha256": _sha256(parquet_file)}],
    }
    _write_manifest(root, "daily_bars", manifest)

    result = run_manifest_report(root, tmp_path, "--datasets", "daily_bars", "--fail-on-blocking")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "manifest-report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["verified_files"] == 1
    markdown = (tmp_path / "manifest-report.md").read_text(encoding="utf-8")
    assert "| daily_bars | present | 1 | ok | 1 | - | - |" in markdown


def test_manifest_verifier_warns_on_legacy_missing_manifest_id(tmp_path: Path) -> None:
    root = tmp_path / "analytics"
    parquet_file = root / "parquet" / "daily_bars" / "part-000.parquet"
    parquet_file.parent.mkdir(parents=True)
    parquet_file.write_bytes(b"legacy")
    _write_manifest(
        root,
        "daily_bars",
        {
            "dataset_key": "daily_bars",
            "dataset_version": "daily_bars_20260608000101",
            "generated_at": "2026-06-08T00:01:01Z",
            "status": "active",
            "quality_status": "ok",
            "period_start": "2026-06-01",
            "period_end": "2026-06-08",
            "row_count": 1,
            "source": {"source_table": "daily_bar_snapshots"},
            "files": [{"path": "parquet/daily_bars/part-000.parquet", "rows": 1, "sha256": _sha256(parquet_file)}],
        },
    )

    result = run_manifest_report(root, tmp_path, "--datasets", "daily_bars", "--fail-on-blocking")

    assert result.returncode == 0
    payload = json.loads((tmp_path / "manifest-report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "warning"
    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["warning_dataset_count"] == 1
    assert payload["datasets"]["daily_bars"]["warnings"] == ["manifest_id_missing"]


def test_manifest_verifier_blocks_hash_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "analytics"
    parquet_file = root / "parquet" / "daily_bars" / "part-000.parquet"
    parquet_file.parent.mkdir(parents=True)
    parquet_file.write_bytes(b"changed")
    _write_manifest(
        root,
        "daily_bars",
        {
            "dataset_key": "daily_bars",
            "manifest_id": "daily_bars:test",
            "dataset_version": "daily_bars_20260608000101",
            "generated_at": "2026-06-08T00:01:01Z",
            "status": "active",
            "quality_status": "ok",
            "period_start": "2026-06-01",
            "period_end": "2026-06-08",
            "row_count": 1,
            "source": {"source_table": "daily_bar_snapshots"},
            "files": [{"path": "parquet/daily_bars/part-000.parquet", "rows": 1, "sha256": "bad"}],
        },
    )

    result = run_manifest_report(root, tmp_path, "--datasets", "daily_bars", "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "manifest-report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "artifact_hash_mismatch:1" in payload["datasets"]["daily_bars"]["blockers"]


def test_manifest_verifier_reports_missing_manifest_as_blocking(tmp_path: Path) -> None:
    result = run_manifest_report(tmp_path / "analytics", tmp_path, "--datasets", "daily_bars")

    assert result.returncode == 0
    payload = json.loads((tmp_path / "manifest-report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "manifest_blocked_count=1" in payload["evaluation"]["blocking"]
    assert payload["summary"]["missing_datasets"] == ["daily_bars"]


def test_manifest_verifier_source_is_read_only() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "DELETE FROM" not in script
    assert "UPDATE " not in script
    assert "DROP TABLE" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "to_parquet" not in script


def _write_manifest(root: Path, dataset_key: str, payload: dict[str, object]) -> None:
    manifests = root / "manifests"
    manifests.mkdir(parents=True)
    (manifests / f"{dataset_key}.latest.json").write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
