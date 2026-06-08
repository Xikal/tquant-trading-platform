from __future__ import annotations

import gzip
import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "verify_mysql_backup_artifact.py"


def run_verifier(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--json-output",
            str(tmp_path / "report.json"),
            "--markdown-output",
            str(tmp_path / "report.md"),
            *extra,
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_mysql_backup_artifact_verifier_accepts_valid_sql_gzip(tmp_path: Path) -> None:
    backup = tmp_path / "tquant-all-databases.sql.gz"
    with gzip.open(backup, "wt", encoding="utf-8") as handle:
        handle.write("-- MySQL dump 10.13\nCREATE TABLE sample(id int);\nINSERT INTO sample VALUES (1);\n")

    result = run_verifier(tmp_path, "--backup-path", str(backup), "--fail-on-blocking")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["backup"]["gzip_ok"] is True
    assert payload["backup"]["sql_signature_ok"] is True
    assert payload["backup"]["sha256"]
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "当前 MySQL 备份文件可读" in markdown


def test_mysql_backup_artifact_verifier_blocks_invalid_gzip(tmp_path: Path) -> None:
    backup = tmp_path / "bad.sql.gz"
    backup.write_text("not a gzip", encoding="utf-8")

    result = run_verifier(tmp_path, "--backup-path", str(backup), "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "mysql_backup_gzip_invalid" in payload["evaluation"]["blocking"]


def test_mysql_backup_artifact_verifier_remote_collection_is_read_only(monkeypatch) -> None:
    module = runpy.run_path(str(SCRIPT))
    collect_remote = module["collect_remote"]
    command_result = module["CommandResult"]

    def fake_run_command(command, timeout=120):
        assert command[0] == "ssh"
        remote_script = command[-1]
        assert "gzip -t" in remote_script
        assert "gzip -cd" in remote_script
        assert "sha256sum" in remote_script
        assert "mysql-backups/*.sql.gz" in remote_script
        assert "gunzip" not in remote_script
        assert "mysql <" not in remote_script
        assert "DROP TABLE" not in remote_script
        assert "rm -f" not in remote_script
        assert "docker volume prune" not in remote_script
        stdout = "\n".join(
            [
                "__BACKUP__ 135000000 1780876900.0 /home/ubuntu/mysql-backups/tquant-all-databases.sql.gz",
                "__GZIP__ ok",
                "__SHA256__ abc123",
                "__SAMPLE_BEGIN__",
                "-- MySQL dump 10.13",
                "CREATE TABLE sample(id int);",
                "__SAMPLE_END__",
            ]
        )
        return command_result("ssh fake", 0, stdout + "\n", "")

    monkeypatch.setitem(collect_remote.__globals__, "run_command", fake_run_command)

    report = collect_remote("example.test", "ubuntu", None, backup_glob="/home/*/mysql-backups/*.sql.gz", sample_bytes=4096)

    assert report["evaluation"]["status"] == "ok"
    assert report["backup"]["present"] is True
    assert report["backup"]["gzip_ok"] is True
    assert report["backup"]["sql_signature_ok"] is True


def test_mysql_backup_artifact_verifier_source_is_non_destructive() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "DROP TABLE" not in source
    assert "DELETE FROM" not in source
    assert "PURGE BINARY LOGS" not in source
    assert "docker volume prune" not in source
    assert "gunzip" not in source
    assert "mysql <" not in source
    assert "rm -f" not in source
