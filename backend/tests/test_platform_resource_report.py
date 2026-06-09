from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "collect_platform_resource_report.py"
INSTALL_SCRIPT = ROOT_DIR / "scripts" / "install_platform_resource_limits.py"


def run_report(fixture: dict[str, object], tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    fixture_path = tmp_path / "fixture.json"
    report_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixture",
            str(fixture_path),
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


def sample_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "generated_at": "2026-06-08T00:00:00+00:00",
        "root": {"used_pct": 55},
        "memory": {"swap": {"used_pct": 10}},
        "docker": {"build_cache": {"size": "1.0GB", "size_bytes": 1_000_000_000}},
        "docker_stats": {"count": 3, "total_memory_bytes": 900_000_000, "rows": []},
        "swappiness": {"value": 10, "recommended_value": 10, "ok": True},
        "separated_stack": {"running_count": 0, "running": [], "rows": []},
        "app_workers": {"gunicorn_workers": 1, "app_workers_env": 1, "default_ok": True},
        "journal": {"usage": "300M", "usage_bytes": 300_000_000},
        "mysql": {
            "slow_log": {"size": "100M", "size_bytes": 100_000_000},
            "variables": {"binlog_expire_logs_seconds": 259200},
            "binary_logs": {"count": 3, "total_bytes": 300_000_000, "logs": []},
        },
        "deploy_backups": {"count": 1, "total_bytes": 200_000_000, "rows": []},
        "mysql_backups": {
            "count": 1,
            "total_bytes": 135_000_000,
            "latest": {"size": "135M", "mtime": "1780876800.0", "path": "/home/ubuntu/mysql-backups/tquant-all-databases.sql.gz", "size_bytes": 135_000_000},
            "rows": [],
        },
    }
    report.update(overrides)
    return report


def test_platform_resource_report_passes_clean_fixture(tmp_path: Path) -> None:
    result = run_report(sample_report(), tmp_path, "--fail-on-blocking")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "ok"
    assert payload["evaluation"]["blocking"] == []
    assert "当前资源巡检通过" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_platform_resource_report_blocks_high_root_usage(tmp_path: Path) -> None:
    result = run_report(sample_report(root={"used_pct": 86}), tmp_path, "--fail-on-blocking")

    assert result.returncode == 42
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["evaluation"]["status"] == "blocking"
    assert "root_used_pct=86" in payload["evaluation"]["blocking"]
    assert "部署 gate 必须停止" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_platform_resource_report_warns_on_slow_log_cache_and_binlog_retention(tmp_path: Path) -> None:
    fixture = sample_report(
        memory={"swap": {"used_pct": 77}},
        docker={"build_cache": {"size": "6.0GB", "size_bytes": 6_000_000_000}},
        swappiness={"value": 60, "recommended_value": 10, "ok": False},
        separated_stack={"running_count": 3, "running": ["tquant-frontend-web", "tquant-backend-api", "tquant-separated-gateway"]},
        app_workers={"gunicorn_workers": 2, "app_workers_env": 2, "default_ok": False},
        mysql={
            "slow_log": {"size": "3.1G", "size_bytes": 3_100_000_000},
            "variables": {"binlog_expire_logs_seconds": 2592000, "max_binlog_size": 1_073_741_824},
            "binary_logs": {"count": 26, "total_bytes": 26_000_000_000, "logs": []},
        },
    )

    result = run_report(fixture, tmp_path, "--fail-on-blocking")

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    warnings = payload["evaluation"]["warnings"]
    assert payload["evaluation"]["status"] == "warning"
    assert "swap_used_pct=77" in warnings
    assert "docker_build_cache_bytes=6000000000" in warnings
    assert "mysql_slow_log_bytes=3100000000" in warnings
    assert "binlog_expire_logs_seconds=2592000" in warnings
    assert "max_binlog_size=1073741824" in warnings
    assert "swappiness=60" in warnings
    assert "separated_stack_running=3" in warnings
    assert "app_gunicorn_workers=2" in warnings


def test_platform_resource_report_parses_human_sizes_before_thresholds(tmp_path: Path) -> None:
    fixture = sample_report(
        docker={"build_cache": {"size": "6.0GB", "size_bytes": None}},
        mysql={
            "slow_log": {"size": "3.1G", "size_bytes": None},
            "variables": {"binlog_expire_logs_seconds": 259200},
            "binary_logs": {"count": 0, "total_bytes": 0, "logs": []},
        },
    )

    result = run_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    warnings = payload["evaluation"]["warnings"]
    assert "docker_build_cache_bytes=6442450944" in warnings
    assert "mysql_slow_log_bytes=3328599654" in warnings


def test_platform_resource_report_parses_mysql8_binary_logs() -> None:
    module = runpy.run_path(str(SCRIPT))
    log_parser = module["parse_mysql_binary_logs"]
    variable_parser = module["parse_mysql_variables"]
    backup_parser = module["parse_deploy_backups"]
    mysql_backup_parser = module["parse_mysql_backups"]
    stats_parser = module["parse_docker_stats"]
    separated_parser = module["parse_separated_stack"]
    workers_parser = module["parse_app_worker_count"]

    payload = log_parser(
        "Log_name\tFile_size\tEncrypted\n"
        "binlog.000032\t1073746277\tNo\n"
        "binlog.000033\t426880848\tNo\n"
    )
    variables = variable_parser("binlog_expire_logs_seconds\t259200\nmax_binlog_size\t1073741824\n")

    assert payload["count"] == 2
    assert payload["total_bytes"] == 1_500_627_125
    assert payload["logs"][0]["name"] == "binlog.000032"
    assert variables == {"binlog_expire_logs_seconds": 259200, "max_binlog_size": 1_073_741_824}
    backups = backup_parser(
        "104857600 1780876800.0 /home/ubuntu/gupiao-deploy-backup-202606080001\n"
        "200M 1780876700.0 /home/ubuntu/gupiao-deploy-backup-202606080000\n"
    )
    assert backups["count"] == 2
    assert backups["total_bytes"] == 314_572_800
    assert backups["rows"][0]["path"].endswith("202606080001")
    mysql_backups = mysql_backup_parser(
        "135M 1780876900.0 /home/ubuntu/mysql-backups/tquant-all-databases-20260608.sql.gz\n"
        "120M 1780790500.0 /home/ubuntu/mysql-backups/tquant-all-databases-20260607.sql.gz\n"
    )
    assert mysql_backups["count"] == 2
    assert mysql_backups["latest"]["path"].endswith("20260608.sql.gz")
    assert mysql_backups["total_bytes"] == 267_386_880
    stats = stats_parser("tquant-app-mysql\t0.1%\t713.3MiB / 3.636GiB\t19.16%\n")
    assert stats["count"] == 1
    assert stats["rows"][0]["memory_used_bytes"] == 747_949_260
    separated = separated_parser("tquant-frontend-web\tUp 40 minutes (healthy)\n")
    assert separated["running_count"] == 1
    workers = workers_parser('["sh","-c","exec gunicorn -k uvicorn.workers.UvicornWorker -w \\"${APP_WORKERS:-1}\\" --bind 0.0.0.0:8000 app.main:app"] ["APP_WORKERS=1"]')
    assert workers["gunicorn_workers"] == 1
    assert workers["app_workers_env"] == 1


def test_platform_resource_report_warns_when_deploy_backups_exceed_retention(tmp_path: Path) -> None:
    fixture = sample_report(
        deploy_backups={
            "count": 5,
            "total_bytes": 5_000_000_000,
            "rows": [{"size": "1G", "mtime": "1780876800.0", "path": f"/home/ubuntu/gupiao-deploy-backup-{idx}"} for idx in range(5)],
        }
    )

    result = run_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "deploy_backup_count=5" in payload["evaluation"]["warnings"]
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| 部署归档数量 | 5 |" in markdown
    assert "| 部署归档总体积 | 5000000000 bytes |" in markdown


def test_platform_resource_report_accepts_zero_deploy_backups(tmp_path: Path) -> None:
    result = run_report(sample_report(deploy_backups={"count": 0, "total_bytes": 0, "rows": []}), tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["deploy_backups"]["count"] == 0
    assert "deploy_backup_count=0" not in payload["evaluation"]["warnings"]


def test_platform_resource_report_includes_mysql_backup_status(tmp_path: Path) -> None:
    fixture = sample_report(
        mysql_backups={
            "count": 2,
            "total_bytes": 255_000_000,
            "latest": {"size": "135M", "mtime": "1780876900.0", "path": "/home/ubuntu/mysql-backups/tquant-all-databases-20260608.sql.gz", "size_bytes": 135_000_000},
            "rows": [],
        }
    )

    result = run_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["mysql_backups"]["count"] == 2
    assert payload["mysql_backups"]["latest"]["path"].endswith("20260608.sql.gz")
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| MySQL 备份数量 | 2 |" in markdown
    assert "| MySQL 备份总体积 | 255000000 bytes |" in markdown
    assert "tquant-all-databases-20260608.sql.gz" in markdown


def test_platform_resource_report_warns_when_mysql_backup_is_missing(tmp_path: Path) -> None:
    result = run_report(sample_report(mysql_backups={"count": 0, "total_bytes": 0, "latest": None, "rows": []}), tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "mysql_backup_count=0" in payload["evaluation"]["warnings"]


def test_platform_resource_report_script_is_read_only() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "rm -rf" not in script
    assert "docker system prune" not in script
    assert "docker volume prune" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "truncate" not in script.lower()


def test_platform_resource_report_warns_when_command_evidence_is_missing(tmp_path: Path) -> None:
    result = run_report(sample_report(source={"local": True}), tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "collector_command_evidence_missing" in payload["evaluation"]["warnings"]


def test_platform_resource_report_warns_when_resource_configs_are_missing(tmp_path: Path) -> None:
    fixture = sample_report(
        resource_configs={
            "docker_daemon": {"present": False, "path": "/etc/docker/daemon.json"},
            "journald_dropin": {"present": False, "path": "/etc/systemd/journald.conf.d/tquant-resource.conf"},
            "buildkit": {"present": False, "path": "/etc/buildkit/buildkitd.toml"},
            "mysql_compose_resource_config": {"present": False, "path": "docker-compose.mysql.yml"},
            "mysql_slow_logrotate": {"present": False, "path": "/etc/logrotate.d/tquant-mysql-slow-log"},
        },
    )

    result = run_report(fixture, tmp_path)

    assert result.returncode == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    warnings = payload["evaluation"]["warnings"]
    assert "resource_config_missing=docker_daemon" in warnings
    assert "resource_config_missing=journald_dropin" in warnings
    assert "resource_config_missing=buildkit" in warnings
    assert "resource_config_missing=mysql_compose_resource_config" in warnings
    assert "resource_config_missing=mysql_slow_logrotate" in warnings
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| `docker_daemon` | missing | `/etc/docker/daemon.json` |" in markdown


def test_platform_resource_limit_templates_are_bounded_and_non_destructive() -> None:
    templates = {
        "slow_logrotate": ROOT_DIR / "deploy" / "mysql" / "mysql-slow-logrotate.conf",
        "docker_daemon": ROOT_DIR / "deploy" / "docker" / "daemon-resource.json",
        "journald": ROOT_DIR / "deploy" / "systemd" / "journald-resource.conf",
        "buildkit": ROOT_DIR / "deploy" / "buildkit" / "buildkitd-resource.toml",
        "compose": ROOT_DIR / "docker-compose.mysql.yml",
        "deploy_env_example": ROOT_DIR / ".env.deploy.local.example",
    }
    contents = {name: path.read_text(encoding="utf-8") for name, path in templates.items()}

    assert "size 256M" in contents["slow_logrotate"]
    assert "rotate 14" in contents["slow_logrotate"]
    assert "copytruncate" in contents["slow_logrotate"]
    assert "--binlog-expire-logs-seconds=${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}" in contents["compose"]
    assert "--max-binlog-size=${MYSQL_MAX_BINLOG_SIZE:-256M}" in contents["compose"]
    assert "MYSQL_BINLOG_EXPIRE_LOGS_SECONDS=259200" in contents["deploy_env_example"]
    assert "MYSQL_MAX_BINLOG_SIZE=256M" in contents["deploy_env_example"]
    assert '"max-size": "50m"' in contents["docker_daemon"]
    assert '"max-file": "3"' in contents["docker_daemon"]
    assert "SystemMaxUse=300M" in contents["journald"]
    assert "MaxRetentionSec=7day" in contents["journald"]
    assert 'maxUsedSpace = "2GB"' in contents["buildkit"]
    combined = "\n".join(contents.values())
    assert "docker volume prune" not in combined
    assert "rm -rf" not in combined
    assert "PURGE BINARY LOGS" not in combined


def test_platform_resource_report_supports_remote_ssh_collection_without_writes() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "--ssh-host" in script
    assert "Collect from a remote host over SSH without changing state" in script
    assert "collect_remote" in script
    assert "sudo docker system df" in script
    assert "sudo docker stats --no-stream" in script
    assert "sysctl -n vm.swappiness" in script
    assert "tquant-separated-gateway" in script
    assert "tquant-app-mysql --format '{{json .Config.Cmd}} {{json .Config.Env}}'" in script
    assert "sudo journalctl --disk-usage" in script
    assert 'sudo du -sh "$mysql_data_dir"' in script
    assert 'sudo du -sh "$slow_log"' in script
    assert "gupiao-deploy-backup-*" in script
    assert "mysql-backups/*.sql.gz" in script
    assert "SHOW BINARY LOGS" in script
    assert "PURGE BINARY LOGS" not in script
    assert "docker volume prune" not in script


def test_platform_resource_remote_collection_escapes_compose_env_placeholders(monkeypatch) -> None:
    module = runpy.run_path(str(SCRIPT))
    collect_remote = module["collect_remote"]
    command_result = module["CommandResult"]

    def fake_run_command(command, timeout=20):
        assert command[0] == "ssh"
        remote_script = command[-1]
        assert "${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}" in remote_script
        assert "${MYSQL_MAX_BINLOG_SIZE:-256M}" in remote_script
        stdout = "\n".join(
            [
                "__SECTION__:df_root",
                "Filesystem Size Used Avail Use% Mounted on",
                "/dev/vda1 59G 33G 26G 56% /",
                "__SECTION__:free",
                "              total        used        free      shared  buff/cache   available",
                "Mem:           3792        2472         203           1        1116         203",
                "Swap:          2048        2048           0",
                "__SECTION__:docker_system_df",
                "TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE",
                "Build Cache     42        0         5.9GB     5.9GB",
                "__SECTION__:docker_stats",
                "tquant-app-mysql\t0.1%\t713.3MiB / 3.636GiB\t19.16%",
                "__SECTION__:swappiness",
                "60",
                "__SECTION__:separated_stack",
                "tquant-frontend-web\tUp 40 minutes (healthy)",
                "__SECTION__:app_workers",
                '["sh","-c","exec gunicorn -k uvicorn.workers.UvicornWorker -w \\"${APP_WORKERS:-1}\\" --bind 0.0.0.0:8000 app.main:app"] ["APP_WORKERS=1"]',
                "__SECTION__:journal",
                "Archived and active journals take up 1.2G in the file system.",
                "__SECTION__:mysql_volume",
                "11G\t/var/lib/docker/volumes/tquant-mysql_mysql_data/_data",
                "__SECTION__:mysql_slow_log",
                "3.1G\t/var/lib/docker/volumes/tquant-mysql_mysql_data/_data/mysql-slow.log",
                "__SECTION__:mysql_variables",
                "binlog_expire_logs_seconds\t259200",
                "max_binlog_size\t1073741824",
                "__SECTION__:mysql_binary_logs",
                "Log_name\tFile_size\tEncrypted",
                "binlog.000001\t1024\tNo",
                "__SECTION__:resource_configs",
                "docker_daemon missing /etc/docker/daemon.json",
                "journald missing /etc/systemd/journald.conf",
                "journald_dropin missing /etc/systemd/journald.conf.d/tquant-resource.conf",
                "buildkit missing /etc/buildkit/buildkitd.toml",
                "mysql_slow_logrotate missing /etc/logrotate.d/tquant-mysql-slow-log",
                "mysql_compose_resource_config present /home/ubuntu/gupiao-upload/docker-compose.mysql.yml",
                "__SECTION__:deploy_backups",
                "__SECTION__:mysql_backups",
                "135M 1780876900.0 /home/ubuntu/mysql-backups/tquant-all-databases-20260608.sql.gz",
            ]
        )
        return command_result("ssh fake", 0, stdout + "\n", "")

    monkeypatch.setitem(collect_remote.__globals__, "run_command", fake_run_command)

    report = collect_remote("example.test", "ubuntu", None, Path("/var/lib/mysql"))

    assert report["resource_configs"]["mysql_compose_resource_config"]["present"] is True
    assert report["mysql"]["variables"]["binlog_expire_logs_seconds"] == 259200
    assert report["mysql"]["variables"]["max_binlog_size"] == 1_073_741_824
    assert report["swappiness"]["value"] == 60
    assert report["separated_stack"]["running_count"] == 1
    assert report["app_workers"]["gunicorn_workers"] == 1
    assert report["commands"]["ssh"]["returncode"] == 0


def test_platform_resource_limit_installer_is_dry_run_and_non_destructive() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Defaults to dry-run and never prunes data." in script
    assert 'parser.add_argument("--apply", action="store_true"' in script
    assert "backup_existing" in script
    assert "merge_json=True" in script
    assert "daemon-resource.json" in script
    assert "journald-resource.conf" in script
    assert "buildkitd-resource.toml" in script
    assert "tquant-swappiness.conf" in script
    assert "sudo sysctl --system" in script
    assert "mysql-resource.cnf" not in script
    assert "mysql-slow-logrotate.conf" in script
    assert "mysql_resource_cnf" not in script
    assert "up -d mysql" in script
    assert "sudo systemctl restart docker" in script
    assert "sudo docker compose -f docker-compose.mysql.yml up -d mysql" in script
    assert "docker volume prune" not in script
    assert "rm -rf" not in script
    assert "PURGE BINARY LOGS" not in script
    assert "unlink(" not in script


def test_platform_resource_limit_installer_dry_run_reports_without_writing(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--backup-root", str(tmp_path / "backups")],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["items"]
    assert all(item["applied"] is False for item in payload["items"])
    assert any(item["name"] == "docker_daemon" for item in payload["items"])
    assert payload["restart_hints"] == []
