from __future__ import annotations

import json
import os
import subprocess
import tarfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def read_repo_file(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def test_dockerfile_builds_can_use_remote_debian_apt_mirror() -> None:
    dockerfile = read_repo_file("Dockerfile")
    compose = read_repo_file("docker-compose.mysql.yml")

    assert "ARG DEBIAN_APT_MIRROR" in dockerfile
    assert "ARG DEBIAN_APT_SECURITY_MIRROR" in dockerfile
    assert "deb.debian.org/debian-security" in dockerfile
    assert "deb.debian.org/debian" in dockerfile
    assert dockerfile.count("DEBIAN_APT_MIRROR") >= 4
    assert dockerfile.count("DEBIAN_APT_SECURITY_MIRROR") >= 4
    assert compose.count("DEBIAN_APT_MIRROR: ${DEBIAN_APT_MIRROR:-}") >= 5
    assert compose.count("DEBIAN_APT_SECURITY_MIRROR: ${DEBIAN_APT_SECURITY_MIRROR:-}") >= 5


def test_cloud_deploy_validates_release_package_and_has_builder_fallback() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert "DEPLOY_PACKAGE_REQUIRED_PATHS" in deploy_script
    assert "verify_package_contents" in deploy_script
    assert "frontend/src/ui/data/index.ts" in deploy_script
    assert "REMOTE_DEBIAN_APT_MIRROR" in deploy_script
    assert "REMOTE_DEBIAN_APT_SECURITY_MIRROR" in deploy_script
    assert "COMPOSE_BAKE=false" in deploy_script
    assert "DOCKER_BUILDKIT=0" in deploy_script
    assert "context deadline exceeded" in deploy_script
    assert "no active session" in deploy_script
    assert "TLS handshake timeout" in deploy_script
    assert "failed to resolve source metadata" in deploy_script
    assert "failed to do request" in deploy_script
    assert "docker build transient registry/buildkit failure" in deploy_script
    assert "retrying attempt $((attempt + 1))/3" in deploy_script


def test_cloud_ssh_lib_retries_transient_scp_connection_resets() -> None:
    ssh_lib = read_repo_file("scripts/cloud_ssh_lib.sh")

    assert "cloud_ssh_transient_log" in ssh_lib
    assert "/tmp/gupiao-ssh-retry" in ssh_lib
    assert 'ConnectTimeout="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"' in ssh_lib
    assert 'ConnectionAttempts="${CLOUD_SSH_CONNECTION_ATTEMPTS:-3}"' in ssh_lib
    assert "CLOUD_SSH_RETRY_ATTEMPTS" in ssh_lib
    assert 'CLOUD_SSH_RETRY_ATTEMPTS:-6' in ssh_lib
    assert "CLOUD_SSH_RETRY_DELAY_SECONDS" in ssh_lib
    assert "ConnectionAttempts" in ssh_lib
    assert "banner exchange" in ssh_lib
    assert "kex_exchange_identification" in ssh_lib
    assert "Connection reset by peer" in ssh_lib
    assert "Connection closed" in ssh_lib
    assert "ssh transient connection failure" in ssh_lib
    assert "ssh/scp transient connection failure" in ssh_lib


def test_quick_deploy_uses_production_safe_cookie_defaults() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert "HTTPS_REQUIRED=1" in quick_script
    assert "CLOUD_AUTH_COOKIE_SECURE=true" in quick_script
    assert "CLOUD_AUTH_ALLOW_INSECURE_HTTP_COOKIE=false" in quick_script
    assert "AUTH_COOKIE_SECURE=true" in quick_script
    assert "AUTH_ALLOW_INSECURE_HTTP_COOKIE=false" in quick_script
    assert "auth cookie allows http" not in quick_script


def test_quick_deploy_requires_explicit_fast_mode_and_external_connection_config() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert 'CLOUD_HOST="${CLOUD_HOST:-}"' in quick_script
    assert 'CLOUD_SSH_KEY="${CLOUD_SSH_KEY:-}"' in quick_script
    assert "43.143.243.97" not in quick_script
    assert "/Users/j/Downloads/gupiao.pem" not in quick_script
    assert "FAST_MODE=0" in quick_script
    assert 'CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"' in quick_script
    assert "RUN_LOCAL_CHECKS=1" in quick_script
    assert "RUN_FRONTEND_BUILD=1" in quick_script
    assert "--fast-risk-accepted" in quick_script
    assert "fast mode requires --fast-risk-accepted" in quick_script


def test_one_click_deploy_defaults_are_overridable_and_do_not_embed_secret_content() -> None:
    one_click_script = read_repo_file("scripts/one_click_cloud_deploy.sh")
    gitignore = read_repo_file(".gitignore")
    deploy_example = read_repo_file(".env.deploy.local.example")

    assert "DEPLOY_ENV_FILE" in one_click_script
    assert ".env.deploy.local" in one_click_script
    assert "DEFAULT_DEPLOY_MODE" in one_click_script
    assert 'CLOUD_SSH_CONNECT_TIMEOUT="${CLOUD_SSH_CONNECT_TIMEOUT:-30}"' in one_click_script
    assert "CLOUD_HOST is required" in one_click_script
    assert "CLOUD_SSH_KEY or CLOUD_PASSWORD is required" in one_click_script
    assert "43.143.243.97" not in one_click_script
    assert "$HOME/Downloads/gupiao.pem" not in one_click_script
    assert ".env.deploy.local" in gitignore
    assert "CLOUD_HOST=" in deploy_example
    assert "CLOUD_SSH_KEY=" in deploy_example
    assert "DEFAULT_DEPLOY_MODE=safe" in deploy_example
    assert "quick_cloud_deploy.sh" in one_click_script
    assert "BEGIN OPENSSH PRIVATE KEY" not in one_click_script


def test_one_click_deploy_no_args_dry_run_uses_safe_mode_from_local_env(tmp_path: Path) -> None:
    key_path = tmp_path / "gupiao.pem"
    key_path.write_text("fake-key", encoding="utf-8")
    deploy_env = tmp_path / ".env.deploy.local"
    deploy_env.write_text(
        "\n".join([
            "CLOUD_HOST=example.internal",
            f"CLOUD_SSH_KEY={key_path}",
            "CLOUD_DOMAIN=example.com",
            "CLOUD_CERT_EMAIL=ops@example.com",
        ]),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "DEPLOY_ENV_FILE": str(deploy_env),
        "ONE_CLICK_DEPLOY_DRY_RUN": "1",
    }

    result = subprocess.run(
        ["bash", str(ROOT_DIR / "scripts/one_click_cloud_deploy.sh")],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert f"env={deploy_env}" in result.stdout
    assert "target=ubuntu@example.internal" in result.stdout
    assert "domain=example.com" in result.stdout
    assert "mode=--refresh-https-config --public-domain-verify" in result.stdout
    assert "sync_mode=package-only" in result.stdout
    assert "dry-run sync_mode=package-only args=--refresh-https-config --public-domain-verify" in result.stdout


def test_one_click_deploy_fast_mode_is_explicit_in_dry_run(tmp_path: Path) -> None:
    key_path = tmp_path / "gupiao.pem"
    key_path.write_text("fake-key", encoding="utf-8")
    env = {
        **os.environ,
        "ONE_CLICK_DEPLOY_DRY_RUN": "1",
    }

    result = subprocess.run(
        [
            "bash",
            str(ROOT_DIR / "scripts/one_click_cloud_deploy.sh"),
            "--fast",
            "--host",
            "example.internal",
            "--key",
            str(key_path),
        ],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "mode=--fast-risk-accepted --host example.internal --key" in result.stdout
    assert "sync_mode=package-only" in result.stdout
    assert "--refresh-https-config --public-domain-verify" in result.stdout


def test_quick_deploy_can_skip_nginx_refresh_and_retries_frontend_smoke() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert "REFRESH_HTTPS_CONFIG=0" in quick_script
    assert "--refresh-https-config" in quick_script
    assert "--configure-https" in quick_script
    assert "curl_retry /tmp/gupiao_home.html" in quick_script
    assert "REFRESH_HTTPS_CONFIG" in deploy_script
    assert "skip HTTPS/nginx config refresh" in deploy_script
    assert "curl_retry /tmp/gupiao_home.html" in deploy_script


def test_quick_deploy_prints_machine_readable_summary() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert "print_deploy_summary" in quick_script
    assert "summary outcome=" in quick_script
    assert "mode=${mode}" in quick_script
    assert "scope=${DEPLOY_TARGET_SCOPE}" in quick_script
    assert "public_domain_verify=${VERIFY_PUBLIC_DOMAIN}" in quick_script
    assert "performance_verify=${RUN_PERFORMANCE_VERIFY}" in quick_script
    assert 'print_deploy_summary "verify-ok"' in quick_script
    assert 'print_deploy_summary "deploy-ok"' in quick_script


def test_quick_deploy_performance_verify_runs_two_sampled_rounds_and_dumps_diagnostics() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert 'RUN_PERFORMANCE_VERIFY_ROUNDS="${RUN_PERFORMANCE_VERIFY_ROUNDS:-2}"' in quick_script
    assert 'RUN_PERFORMANCE_VERIFY_SAMPLES="${RUN_PERFORMANCE_VERIFY_SAMPLES:-8}"' in quick_script
    assert "--performance-rounds <n>" in quick_script
    assert "--performance-samples <n>" in quick_script
    assert 'for round in $(seq 1 "$RUN_PERFORMANCE_VERIFY_ROUNDS")' in quick_script
    assert '--samples "$RUN_PERFORMANCE_VERIFY_SAMPLES"' in quick_script
    assert "dump_container_diagnostics" in quick_script
    assert "sudo docker logs --tail=120" in quick_script
    assert "dump_container_diagnostics" in deploy_script
    assert 'echo "$name did not become healthy"' in deploy_script
    assert "did not become healthy" in deploy_script


def test_deploy_scripts_support_scope_aware_fast_paths() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    one_click_script = read_repo_file("scripts/one_click_cloud_deploy.sh")
    deploy_example = read_repo_file(".env.deploy.local.example")

    assert 'DEPLOY_TARGET_SCOPE="${DEPLOY_TARGET_SCOPE:-auto}"' in deploy_script
    assert "resolve_deploy_scope" in deploy_script
    assert "frontend-hot" in deploy_script
    assert "go-services/*" in deploy_script
    assert "create frontend hot package" in deploy_script
    assert "frontend_hot:updated" in deploy_script
    assert "frontend_hot_image:rebuilt" in deploy_script
    assert "tquant-web:mysql-before-frontend-hot" in deploy_script
    assert "Dockerfile.frontend-hot" in deploy_script
    assert "rm -rf /app/frontend/dist" in deploy_script
    assert "sudo docker build -t tquant-web:mysql -f \"$WORK_DIR/Dockerfile.frontend-hot\"" in deploy_script
    assert "docker commit" not in deploy_script
    assert "skip HTTPS/backup cron refresh for scope" in deploy_script
    assert "skip latest low-buy data closure for scope" in deploy_script
    assert "--scope <auto|all|frontend-hot|go|ops>" in quick_script
    assert "DEPLOY_FRONTEND_HOT_REQUIRED" in quick_script
    assert "VERIFY_WEB_IMAGE_SYNC" in quick_script
    assert "web_image:skipped_frontend_hot" in quick_script
    assert "--scope  Override target selection" in one_click_script
    assert "DEPLOY_TARGET_SCOPE=auto" in deploy_example
    assert "DEPLOY_SYNC_MODE=delta-package" in deploy_example
    assert "package-only remains the automatic fallback" in deploy_example


def test_cloud_deploy_prefers_remote_git_sync_before_package_upload() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    workflow = read_repo_file(".github/workflows/ci.yml")

    assert 'DEPLOY_SYNC_MODE="${DEPLOY_SYNC_MODE:-package-only}"' in deploy_script
    assert 'DEPLOY_DELTA_MAX_CHANGE_RATIO="${DEPLOY_DELTA_MAX_CHANGE_RATIO:-0.35}"' in deploy_script
    assert 'DEPLOY_GIT_REMOTE_URL="${DEPLOY_GIT_REMOTE_URL:-https://github.com/Xikal/tquant-trading-platform.git}"' in deploy_script
    assert 'DEPLOY_GIT_REF="${DEPLOY_GIT_REF:-${GITHUB_SHA:-HEAD}}"' in deploy_script
    assert "remote_deploy_from_git" in deploy_script
    assert '"$DEPLOY_SYNC_MODE" != "git-inplace"' in deploy_script
    assert '"$DEPLOY_SYNC_MODE" != "git-clone"' in deploy_script
    assert "deploy via remote git sync ref ${DEPLOY_GIT_REF} scope ${DEPLOY_RESOLVED_SCOPE}" in deploy_script
    assert "git_network_retry" in deploy_script
    assert "http.lowSpeedLimit" in deploy_script
    assert "http.lowSpeedTime" in deploy_script
    assert "git network failure; retrying attempt" in deploy_script
    assert 'if test -d "$CLOUD_PROJECT_DIR/.git"; then' in deploy_script
    assert "deploy_sync:git-inplace" in deploy_script
    assert "deploy_sync:git-clone" in deploy_script
    assert "git clean -fd -e .env -e .runtime -e backend/data" in deploy_script
    assert "git_network_retry clone --no-checkout \"$git_url\" \"$WORKTREE\"" in deploy_script
    assert "git -C \"$WORKTREE\" checkout --detach \"$DEPLOY_GIT_REF\"" in deploy_script
    assert '"$DEPLOY_SYNC_MODE" == "git-inplace" || "$DEPLOY_SYNC_MODE" == "git-clone"' in deploy_script
    assert "remote git sync unavailable; falling back to package upload" in deploy_script
    assert "package-only" in deploy_script
    assert 'DEPLOY_SYNC_MODE: "delta-package"' in workflow
    assert "DEPLOY_GIT_REF: ${{ github.sha }}" in workflow
    assert "DEPLOY_GIT_AUTH_TOKEN: ${{ github.token }}" in workflow


def test_delta_package_helper_builds_manifest_delta_and_safe_delete_manifest(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (root / "docker-compose.mysql.yml").write_text("services: {}\n", encoding="utf-8")
    (root / "backend/app/main.py").parent.mkdir(parents=True)
    (root / "backend/app/main.py").write_text("print('main')\n", encoding="utf-8")
    (root / "frontend/src/main.tsx").parent.mkdir(parents=True)
    (root / "frontend/package.json").write_text("{}\n", encoding="utf-8")
    (root / "frontend/src/main.tsx").write_text("console.log('main')\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts/install_https_nginx.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "scripts/deploy_delta_package.py").write_text("helper\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/old-report.md").write_text("old\n", encoding="utf-8")
    previous_manifest = tmp_path / "previous.json"
    subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts/deploy_delta_package.py"),
            "manifest",
            "--root",
            str(root),
            "--output",
            str(previous_manifest),
            "--quiet",
        ],
        check=True,
        cwd=ROOT_DIR,
    )

    (root / "docs/old-report.md").unlink()
    (root / "docs/new-report.md").write_text("new\n", encoding="utf-8")
    delta_archive = tmp_path / "delta.tgz"
    local_manifest = tmp_path / "local.json"
    summary_path = tmp_path / "summary.json"
    subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts/deploy_delta_package.py"),
            "build",
            "--root",
            str(root),
            "--previous",
            str(previous_manifest),
            "--output",
            str(delta_archive),
            "--manifest-output",
            str(local_manifest),
            "--summary-output",
            str(summary_path),
            "--max-change-ratio",
            "1.0",
        ],
        check=True,
        cwd=ROOT_DIR,
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["fallback_reason"] == ""
    assert summary["changed_count"] == 1
    assert summary["deleted_count"] == 1
    assert summary["delta_bytes"] > 0
    with tarfile.open(delta_archive, "r:gz") as tar:
        names = set(tar.getnames())
    assert "./docs/new-report.md" in names
    assert "./.deploy-delta/deploy-manifest.json" in names
    assert "./.deploy-delta/deploy-delete-manifest.json" in names


def test_delta_package_helper_falls_back_on_critical_and_unsafe_delete(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/report.md").write_text("old\n", encoding="utf-8")
    (root / "backend/data").mkdir(parents=True)
    (root / "backend/data/live.db").write_text("db\n", encoding="utf-8")
    previous_manifest = tmp_path / "previous.json"
    subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts/deploy_delta_package.py"),
            "manifest",
            "--root",
            str(root),
            "--output",
            str(previous_manifest),
            "--quiet",
        ],
        check=True,
        cwd=ROOT_DIR,
    )

    (root / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    delta_archive = tmp_path / "critical.tgz"
    summary_path = tmp_path / "critical-summary.json"
    subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts/deploy_delta_package.py"),
            "build",
            "--root",
            str(root),
            "--previous",
            str(previous_manifest),
            "--output",
            str(delta_archive),
            "--manifest-output",
            str(tmp_path / "local.json"),
            "--summary-output",
            str(summary_path),
        ],
        check=True,
        cwd=ROOT_DIR,
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["fallback_reason"] == "critical_paths_changed"
    assert not delta_archive.exists()

    delete_manifest = tmp_path / "delete.json"
    delete_manifest.write_text(
        json.dumps({"files": [{"path": "backend/data/live.db", "sha256": "bad"}]}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts/deploy_delta_package.py"),
            "apply-deletes",
            "--root",
            str(root),
            "--previous-manifest",
            str(previous_manifest),
            "--delete-manifest",
            str(delete_manifest),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "unsafe delete path" in result.stderr


def test_delta_deploy_mode_is_logged_and_falls_back_to_package_only() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert "DEPLOY_SYNC_MODE=delta-package" in read_repo_file(".env.deploy.local.example")
    assert "prepare_deploy_package" in deploy_script
    assert "fetch_remote_deploy_manifest" in deploy_script
    assert "deploy_delta_package.py\" build" in deploy_script
    assert "deploy_sync:delta-package" in deploy_script
    assert "deploy_sync:package-only" in deploy_script
    assert "missing_remote_manifest" in deploy_script
    assert "invalid_remote_manifest" in deploy_script
    assert "remote_delta_apply_failed" in deploy_script
    assert "delta package deploy failed; falling back to full package upload" in deploy_script
    assert "sync metrics: requested_mode=${DEPLOY_SYNC_MODE} sync_mode=${DEPLOY_EFFECTIVE_SYNC_MODE}" in deploy_script
    assert "changed_count=${DEPLOY_DELTA_CHANGED_COUNT}" in deploy_script
    assert "deleted_count=${DEPLOY_DELTA_DELETED_COUNT}" in deploy_script
    assert "delta_bytes=${DEPLOY_DELTA_BYTES}" in deploy_script
    assert "full_bytes=${DEPLOY_DELTA_FULL_BYTES}" in deploy_script
    assert "upload_seconds=${DEPLOY_UPLOAD_SECONDS}" in deploy_script
    assert "fallback_reason=${DEPLOY_DELTA_FALLBACK_REASON:-none}" in deploy_script
    assert "python3 gupiao-upload-delta-new/scripts/deploy_delta_package.py apply-deletes" in deploy_script
    assert ".runtime/deploy-manifest.json" in deploy_script


def test_makefile_has_one_click_deploy_shortcuts() -> None:
    makefile = read_repo_file("Makefile")

    assert "deploy-cloud:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh" in makefile
    assert "deploy-cloud-web:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope frontend-hot --frontend-hot-required" in makefile
    assert "deploy-cloud-go:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope go" in makefile
    assert "deploy-cloud-full:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope all --full" in makefile
    assert "deploy-cloud-fast:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --fast" in makefile
    assert "deploy-cloud-verify:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --verify-only" in makefile


def test_ci_reuses_frontend_artifact_and_selects_deploy_scope() -> None:
    workflow = read_repo_file(".github/workflows/ci.yml")

    assert "Upload frontend dist artifact" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "Download frontend dist artifact" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "Select deploy target scope" in workflow
    assert "fetch-depth: 0" in workflow
    assert "github.event.before" in workflow
    assert 'git diff --name-only "$before" "$after"' in workflow
    assert 'git diff --name-only HEAD^ HEAD' in workflow
    assert "DEPLOY_TARGET_SCOPE=$scope" in workflow
    assert "DEPLOY_CHANGED_FILES<<DEPLOY_FILES" in workflow
    assert "DEPLOY_FRONTEND_HOT_REQUIRED" in workflow


def test_ci_deploy_fails_when_cloud_secrets_are_missing() -> None:
    workflow = read_repo_file(".github/workflows/ci.yml")

    assert "CLOUD_HOST/CLOUD_USER secrets 未配置，不能执行真实部署。" in workflow
    assert 'echo "CLOUD_HOST/CLOUD_USER secrets 未配置，跳过部署。"' not in workflow
    assert "exit 2" in workflow
    assert 'RUN_COMPILE: "0"' in workflow
    assert 'RUN_FRONTEND_BUILD: "0"' in workflow
    assert 'RUN_STRATEGY_TEST: "0"' in workflow


def test_cloud_deploy_remote_smoke_rejects_api_html_fallback() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    for script in (deploy_script, quick_script):
        assert "api_fallback:ok" in script
        assert "/api/__missing_smoke__" in script
        assert "Content-Type" in script
        assert "application/json" in script


def test_mysql_compose_runs_runtime_scheduler_separately_from_web_and_worker() -> None:
    compose = read_repo_file("docker-compose.mysql.yml")

    assert "runtime-scheduler:" in compose
    assert "container_name: tquant-runtime-scheduler-mysql" in compose
    assert 'command: ["python", "-m", "app.workers.runtime_scheduler"]' in compose
    assert "RUNTIME_BACKGROUND_ROLE: scheduler" in compose
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED: ${RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED:-true}" in compose
    assert "RUNTIME_BACKGROUND_ROLE: web" in compose
    assert "RUNTIME_BACKGROUND_ROLE: worker" in compose


def test_runtime_worker_supports_latest_data_watchdog_task() -> None:
    source = read_repo_file("backend/app/workers/runtime_worker.py")
    background_jobs = read_repo_file("backend/app/runtime/background_jobs.py")

    assert '"latest_data_watchdog"' in source
    assert "LatestDailyBarWatchdog().run" in source
    assert 'name="latest_data_watchdog"' in background_jobs
    assert 'task_type="latest_data_watchdog"' in background_jobs


def test_cloud_deploy_starts_runtime_scheduler_container() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    compose = read_repo_file("docker-compose.mysql.yml")

    assert "runtime-worker:" in compose
    assert "runtime-scheduler:" in compose
    assert 'command: ["python", "-m", "app.workers.runtime_worker"]' in compose
    assert 'command: ["python", "-m", "app.workers.runtime_scheduler"]' in compose
    assert "tquant-runtime-scheduler-mysql" in deploy_script
    assert "tquant-runtime-worker-mysql" in deploy_script
    assert "runtime-scheduler" in deploy_script
    assert "runtime-worker" in deploy_script
    assert "app runtime-scheduler runtime-worker backtest-worker analytics-worker" in deploy_script
    assert "tquant-runtime-scheduler-mysql" in quick_script


def test_runtime_data_fallback_runbook_and_startup_guard_exist() -> None:
    runbook = read_repo_file("docs/operations/runtime-data-fallback-runbook.md")
    production_runbook = read_repo_file("PRODUCTION_RUNBOOK.md")
    startup_script = read_repo_file("scripts/dev_start_all.sh")
    component_script = read_repo_file("scripts/run_platform_component.sh")

    assert "runtime_worker.heartbeat" in runbook
    assert "critical tasks queued > 10 min" in runbook
    assert "hermes_daily_bar_watchdog.py" in runbook
    assert "runtime-data-fallback-runbook.md" in production_runbook
    assert "RUNTIME_BACKGROUND_JOBS_ENABLED" in startup_script
    assert "scripts/run_platform_component.sh runtime-worker" in startup_script
    assert "scripts/run_platform_component.sh web" in startup_script
    assert "app.workers.runtime_worker" in component_script
    assert "uvicorn app.main:app" in component_script


def test_platform_component_entrypoints_and_worker_runbooks_exist() -> None:
    component_script = read_repo_file("scripts/run_platform_component.sh")
    startup_script = read_repo_file("scripts/dev_start_all.sh")
    topology_runbook = read_repo_file("docs/operations/deployment-topology-runbook.md")
    worker_runbook = read_repo_file("docs/operations/worker-runbook.md")
    production_runbook = read_repo_file("PRODUCTION_RUNBOOK.md")

    for component in ("web", "runtime-worker", "scheduler", "analytics-worker", "backtest-worker"):
        result = subprocess.run(
            ["bash", str(ROOT_DIR / "scripts/run_platform_component.sh"), component, "--print-command"],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stdout.strip()

    assert "uvicorn app.main:app" in component_script
    assert "app.workers.runtime_worker" in component_script
    assert "app.workers.runtime_scheduler" in component_script
    assert "backend/scripts/analytics_worker.py" in component_script
    assert "scripts/backtest_worker.py" in component_script
    assert "scripts/run_platform_component.sh web" in startup_script
    assert "scripts/run_platform_component.sh runtime-worker" in startup_script
    assert "Deployment Topology Runbook" in topology_runbook
    assert "Worker Runbook" in worker_runbook
    assert "deployment-topology-runbook.md" in production_runbook
    assert "worker-runbook.md" in production_runbook


def test_cloud_deploy_distinguishes_nginx_sni_from_public_domain_reachability() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert "VERIFY_PUBLIC_DOMAIN" in deploy_script
    assert "verify_https_remote" in deploy_script
    assert "--resolve \"${CLOUD_DOMAIN}:443:127.0.0.1\"" in deploy_script
    assert "https_sni_loopback:ok" in deploy_script
    assert "public_domain:warning" in deploy_script


def test_local_artifact_cleanup_script_is_explicit_and_dry_run_by_default() -> None:
    cleanup_script = read_repo_file("scripts/clean_local_artifacts.sh")

    assert "--pycache" in cleanup_script
    assert "--frontend-dist" in cleanup_script
    assert "--apply" in cleanup_script
    assert "DRY_RUN=1" in cleanup_script
    assert "backend/data" not in cleanup_script


def test_reports_index_documents_machine_artifact_policy() -> None:
    index = read_repo_file("docs/reports/README.md")

    assert "人读 Markdown" in index
    assert "机器产物" in index
    assert "backend/data/reports" in index
    assert "不要直接删除历史 JSON" in index
    assert "front-row-weighted-production-scoring-backtest-2026-05-29.json" in index
