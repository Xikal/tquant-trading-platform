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


def test_cloud_deploy_preserves_existing_paper_auto_trading_flag() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert 'if test -n "${PAPER_AUTO_TRADING_ENABLED+x}"; then' in deploy_script
    assert 'upsert_env_value PAPER_AUTO_TRADING_ENABLED "$PAPER_AUTO_TRADING_ENABLED"' in deploy_script
    assert "elif ! grep -Eq '^PAPER_AUTO_TRADING_ENABLED=' .env; then" in deploy_script
    assert "upsert_env_value PAPER_AUTO_TRADING_ENABLED false" in deploy_script
    assert 'upsert_env_value PAPER_AUTO_TRADING_ENABLED "${PAPER_AUTO_TRADING_ENABLED:-false}"' not in deploy_script


def test_cloud_ssh_lib_retries_transient_scp_connection_resets() -> None:
    ssh_lib = read_repo_file("scripts/cloud_ssh_lib.sh")

    assert "cloud_ssh_transient_log" in ssh_lib
    assert "/tmp/gupiao-ssh-retry" in ssh_lib
    assert 'mktemp "/tmp/gupiao-ssh-retry-${attempt}.XXXXXX"' in ssh_lib
    assert 'mktemp "/tmp/gupiao-scp-retry-${attempt}.XXXXXX"' in ssh_lib
    assert "XXXXXX.log" not in ssh_lib
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
    assert "CLOUD_SSH_KEY or CLOUD_PASSWORD is required" in quick_script
    assert '[[ -z "$CLOUD_SSH_KEY" && -z "${CLOUD_PASSWORD:-}" ]]' in quick_script
    assert '[[ -n "$CLOUD_SSH_KEY" && ! -f "$CLOUD_SSH_KEY" ]]' in quick_script
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
    assert 'CLOUD_PUBLIC_BASE_URL="${CLOUD_PUBLIC_BASE_URL:-https://${CLOUD_HOST:-}}"' in one_click_script
    assert "https://<CLOUD_HOST>" in one_click_script
    assert "43.143.243.97" not in one_click_script
    assert "$HOME/Downloads/gupiao.pem" not in one_click_script
    assert ".env.deploy.local" in gitignore
    assert "CLOUD_HOST=" in deploy_example
    assert "CLOUD_SSH_KEY=" in deploy_example
    assert "# CLOUD_PASSWORD=" in deploy_example
    assert "DEFAULT_DEPLOY_MODE=safe" in deploy_example
    assert "RUN_REMOTE_PREFLIGHT=1" in deploy_example
    assert "REMOTE_MIN_FREE_GB=8" in deploy_example
    assert "REMOTE_MIN_SWAP_MB=2048" in deploy_example
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
            "CLOUD_PUBLIC_BASE_URL=https://example.internal",
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
    assert "mode=--refresh-https-config" in result.stdout
    assert "--public-domain-verify" not in result.stdout
    assert "sync_mode=package-only" in result.stdout
    assert "dry-run sync_mode=package-only args=--refresh-https-config" in result.stdout


def test_one_click_deploy_no_args_dry_run_allows_password_from_local_env(tmp_path: Path) -> None:
    deploy_env = tmp_path / ".env.deploy.local"
    deploy_env.write_text(
        "\n".join([
            "CLOUD_HOST=example.internal",
            "CLOUD_PASSWORD=secret",
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

    assert "target=ubuntu@example.internal" in result.stdout
    assert "ssh=password" in result.stdout


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
    assert "--refresh-https-config" in result.stdout
    assert "--public-domain-verify" not in result.stdout


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
    assert "public_entry_verify=${VERIFY_PUBLIC_ENTRY}" in quick_script
    assert "public_base=${public_base}" in quick_script
    assert "summary urls default=${public_base}/monitor" in quick_script
    assert "performance_verify=${RUN_PERFORMANCE_VERIFY}" in quick_script
    assert 'print_deploy_summary "verify-ok"' in quick_script
    assert 'print_deploy_summary "deploy-ok"' in quick_script


def test_quick_deploy_runs_remote_resource_preflight_without_destructive_prune() -> None:
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert 'RUN_REMOTE_PREFLIGHT="${RUN_REMOTE_PREFLIGHT:-1}"' in quick_script
    assert 'REMOTE_PREFLIGHT_READ_ONLY="${REMOTE_PREFLIGHT_READ_ONLY:-0}"' in quick_script
    assert 'REMOTE_MIN_FREE_GB="${REMOTE_MIN_FREE_GB:-8}"' in quick_script
    assert 'REMOTE_ROOT_WARN_PCT="${REMOTE_ROOT_WARN_PCT:-70}"' in quick_script
    assert 'REMOTE_ROOT_BLOCK_PCT="${REMOTE_ROOT_BLOCK_PCT:-80}"' in quick_script
    assert 'REMOTE_DOCKER_BUILD_CACHE_WARN_GB="${REMOTE_DOCKER_BUILD_CACHE_WARN_GB:-2}"' in quick_script
    assert 'REMOTE_MYSQL_SLOW_LOG_WARN_MB="${REMOTE_MYSQL_SLOW_LOG_WARN_MB:-512}"' in quick_script
    assert 'REMOTE_BINLOG_EXPIRE_MAX_SECONDS="${REMOTE_BINLOG_EXPIRE_MAX_SECONDS:-259200}"' in quick_script
    assert 'REMOTE_MAX_BINLOG_SIZE_WARN_MB="${REMOTE_MAX_BINLOG_SIZE_WARN_MB:-256}"' in quick_script
    assert 'REMOTE_MYSQL_BACKUP_MIN_COUNT="${REMOTE_MYSQL_BACKUP_MIN_COUNT:-1}"' in quick_script
    assert 'REMOTE_MIN_SWAP_MB="${REMOTE_MIN_SWAP_MB:-2048}"' in quick_script
    assert 'REMOTE_TEMP_SWAP_PATH="${REMOTE_TEMP_SWAP_PATH:-/swapfile-codex-deploy}"' in quick_script
    assert "--skip-remote-preflight" in quick_script
    assert "--skip-remote-cleanup" in quick_script
    assert "--remote-root-block-pct <n>" in quick_script
    assert "remote_preflight" in quick_script
    assert "run_verify_only_preflight" in quick_script
    assert 'REMOTE_PREFLIGHT_READ_ONLY=1' in quick_script
    assert 'RUN_REMOTE_SAFE_CLEANUP=0' in quick_script
    assert 'REMOTE_TEMP_SWAP_MB=0' in quick_script
    assert 'run_verify_only_preflight' in quick_script.split('if [[ "$VERIFY_ONLY" == "1" ]]; then', 1)[1]
    assert 'REMOTE_PREFLIGHT_READ_ONLY="$REMOTE_PREFLIGHT_READ_ONLY"' in quick_script
    assert 'test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "${RUN_REMOTE_SAFE_CLEANUP:-1}" = "1"' in quick_script
    assert 'test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "$FREE_GB" -lt' in quick_script
    assert 'test "${REMOTE_PREFLIGHT_READ_ONLY:-0}" != "1" && test "$SWAP_MB" -lt' in quick_script
    assert "remote_resource_gate" in quick_script
    assert "preflight:root_used_pct=" in quick_script
    assert "preflight:blocking_root_used_pct=" in quick_script
    assert "preflight:docker_build_cache_gb=" in quick_script
    assert "preflight:mysql_slow_log_mb=" in quick_script
    assert "preflight:binlog_expire_seconds=" in quick_script
    assert "preflight:max_binlog_size_mb=" in quick_script
    assert "preflight:mysql_compose_resource_config=" in quick_script
    assert "preflight:journald_resource_config=" in quick_script
    assert "preflight:deploy_backup_count=" in quick_script
    assert "preflight:mysql_backup_count=" in quick_script
    assert "preflight:warning_max_binlog_size_mb=" in quick_script
    assert "preflight:warning_mysql_compose_resource_config=" in quick_script
    assert "preflight:warning_journald_resource_config=" in quick_script
    assert "preflight:warning_deploy_backup_count=" in quick_script
    assert "preflight:warning_mysql_backup_count=" in quick_script
    assert "preflight:low_disk_safe_prune" in quick_script
    assert 'value ~ /Gi?B$/' in quick_script
    assert 'sudo du -m "$slow_log"' in quick_script
    assert "--binlog-expire-logs-seconds=${MYSQL_BINLOG_EXPIRE_LOGS_SECONDS:-259200}" in quick_script
    assert "--max-binlog-size=${MYSQL_MAX_BINLOG_SIZE:-256M}" in quick_script
    assert "exec -T mysql test -f /etc/mysql/conf.d/tquant-resource.cnf" not in quick_script
    assert "sudo docker builder prune -f" in quick_script
    assert "sudo docker image prune -f" in quick_script
    assert "docker_volumes_kept" in quick_script
    assert "sudo swapon" in quick_script
    assert "remote_post_deploy_cleanup" in quick_script
    assert "image prune -a" not in quick_script
    assert "volume prune" not in quick_script


def test_deploy_scripts_support_prebuilt_image_pull_restart_mode() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    builder_script = read_repo_file("scripts/build_prebuilt_images.sh")
    deploy_example = read_repo_file(".env.deploy.local.example")

    assert 'DEPLOY_PREBUILT_IMAGES_ENABLED="${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}"' in deploy_script
    assert 'DEPLOY_PREBUILT_WEB_IMAGE_REF="${DEPLOY_PREBUILT_WEB_IMAGE_REF:-}"' in deploy_script
    assert 'DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF="${DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF:-}"' in deploy_script
    assert 'DEPLOY_PREBUILT_GO_BFF_IMAGE_REF="${DEPLOY_PREBUILT_GO_BFF_IMAGE_REF:-}"' in deploy_script
    assert 'DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF="${DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF:-}"' in deploy_script
    assert 'DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF="${DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF:-}"' in deploy_script
    assert "use_prebuilt_app_images" in deploy_script
    assert "use_prebuilt_go_images" in deploy_script
    assert "prebuilt_images:pull_app" in deploy_script
    assert "prebuilt_images:pull_go" in deploy_script
    assert 'sudo docker pull "$DEPLOY_PREBUILT_WEB_IMAGE_REF"' in deploy_script
    assert 'sudo docker tag "$DEPLOY_PREBUILT_WEB_IMAGE_REF" tquant-web:mysql' in deploy_script
    assert 'sudo docker tag "$DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" tquant-analytics:mysql' in deploy_script
    assert 'sudo docker tag "$DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" tquant-go-bff:mysql' in deploy_script
    assert 'sudo docker tag "$DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" tquant-go-market-read:mysql' in deploy_script
    assert 'sudo docker tag "$DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" tquant-go-scan-worker:mysql' in deploy_script
    assert "docker_build:skipped_prebuilt_app" in deploy_script
    assert "docker_build:skipped_prebuilt_go" in deploy_script
    assert "prebuilt_images:app_unavailable_fallback_build" in deploy_script
    assert "prebuilt_images:go_unavailable_fallback_build" in deploy_script

    assert 'DEPLOY_PREBUILT_IMAGES_ENABLED="${DEPLOY_PREBUILT_IMAGES_ENABLED:-auto}"' in quick_script
    assert "--prebuilt-images" in quick_script
    assert "--prebuilt-web-image <ref>" in quick_script
    assert "prebuilt_images=${DEPLOY_PREBUILT_IMAGES_ENABLED}" in quick_script
    assert "export DEPLOY_PREBUILT_IMAGES_ENABLED" in quick_script
    assert "export DEPLOY_PREBUILT_WEB_IMAGE_REF" in quick_script
    assert "export DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" in quick_script
    assert "export DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" in quick_script
    assert "export DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" in quick_script
    assert "export DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" in quick_script

    assert "Build local prebuilt images for cloud pull+restart deploys. It never deploys." in builder_script
    assert 'IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"' in builder_script
    assert "PUSH_IMAGES=0" in builder_script
    assert "--push" in builder_script
    assert 'COMPOSE_BAKE=false docker compose -f "$COMPOSE_FILE" build app analytics-worker' in builder_script
    assert 'COMPOSE_BAKE=false docker compose -f "$COMPOSE_FILE" build go-bff-gateway go-market-read-service go-scan-worker' in builder_script
    assert "DEPLOY_PREBUILT_WEB_IMAGE_REF" in builder_script
    assert "DEPLOY_PREBUILT_ANALYTICS_IMAGE_REF" in builder_script
    assert "DEPLOY_PREBUILT_GO_BFF_IMAGE_REF" in builder_script
    assert "DEPLOY_PREBUILT_GO_MARKET_READ_IMAGE_REF" in builder_script
    assert "DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF" in builder_script
    assert "quick_cloud_deploy.sh" not in builder_script
    assert "deploy_cloud_server.sh" not in builder_script

    assert "DEPLOY_PREBUILT_IMAGES_ENABLED=auto" in deploy_example
    assert "DEPLOY_PREBUILT_WEB_IMAGE_REF=registry.example.com/tquant-web:<sha>" in deploy_example
    assert "DEPLOY_PREBUILT_GO_SCAN_IMAGE_REF=registry.example.com/tquant-go-scan-worker:<sha>" in deploy_example


def test_cloud_cleanup_removes_extensionless_upload_packages_without_volume_prune() -> None:
    cleanup_script = read_repo_file("scripts/cloud_server_cleanup.sh")

    assert "-name 'gupiao-deploy-*'" in cleanup_script
    assert "-name 'gupiao-delta-deploy-*'" in cleanup_script
    assert "-name 'gupiao-frontend-hot-*'" in cleanup_script
    assert "-name 'gupiao_remote_verify*.sh'" in cleanup_script
    assert "-name 'gupiao-deploy-*.tgz'" not in cleanup_script
    assert "tquant-queue-hotpatch-*" in cleanup_script
    assert "docker volumes:kept" in cleanup_script
    assert "sudo docker builder prune -f" in cleanup_script
    assert "sudo docker image prune -f" in cleanup_script
    assert "image prune -a" not in cleanup_script
    assert "volume prune" not in cleanup_script


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
    frontend_nginx = read_repo_file("deploy/frontend/nginx.conf")
    frontend_dockerfile = read_repo_file("deploy/frontend/Dockerfile")
    scope_helper = read_repo_file("scripts/deploy_scope.py")

    assert 'DEPLOY_TARGET_SCOPE="${DEPLOY_TARGET_SCOPE:-auto}"' in deploy_script
    assert "scripts/deploy_scope.py" in deploy_script
    assert "DEPLOY_RESOLVED_UNITS" in deploy_script
    assert "frontend-next" in deploy_script
    assert "frontend_next_hot:updated" in deploy_script
    assert "frontend_next_hot:monolith_compat" in deploy_script
    assert "frontend_next_hot:separated_frontend_web" in deploy_script
    assert "frontend-hot" in deploy_script
    assert "go-services/" in scope_helper
    assert "create frontend hot package" in deploy_script
    assert "create frontend-next hot package" in deploy_script
    assert "frontend_hot:updated" in deploy_script
    assert "frontend_hot_image:rebuilt" in deploy_script
    assert "tquant-web:mysql-before-frontend-hot" in deploy_script
    assert "Dockerfile.frontend-hot" in deploy_script
    assert "rm -rf /app/frontend/dist" in deploy_script
    assert "sudo docker build -t tquant-web:mysql -f \"$WORK_DIR/Dockerfile.frontend-hot\"" in deploy_script
    assert "docker commit" not in deploy_script
    assert "skip HTTPS/backup cron refresh for scope" in deploy_script
    assert "skip latest low-buy data closure for scope" in deploy_script
    assert "--scope <auto|frontend-next|frontend-legacy|backend-api|db-migration|worker|go|ops|all>" in quick_script
    assert "DEPLOY_FRONTEND_HOT_REQUIRED" in quick_script
    assert "DEPLOY_FRONTEND_NEXT_REQUIRED" in quick_script
    assert "DEPLOY_CHANGED_FILES_FROM" in quick_script
    assert "VERIFY_WEB_IMAGE_SYNC" in quick_script
    assert "web_image:skipped_frontend_hot" in quick_script
    assert "web_image:skipped_frontend_next" in quick_script
    assert "--scope  Override target selection" in one_click_script
    assert "--frontend-next-required" in one_click_script
    assert "DEPLOY_TARGET_SCOPE=auto" in deploy_example
    assert "DEPLOY_COMPOSE_TOPOLOGY=separated" in deploy_example
    assert "DEPLOY_FRONTEND_NEXT_REQUIRED=1" in deploy_example
    assert "DEPLOY_SYNC_MODE=delta-package" in deploy_example
    assert "CLOUD_PUBLIC_BASE_URL=https://43.143.243.97" in deploy_example
    assert "package-only remains the automatic fallback" in deploy_example
    assert "root /usr/share/nginx/html-next;" in frontend_nginx
    assert "location /__legacy/assets/" in frontend_nginx
    assert "/usr/share/nginx/html-root/" in frontend_dockerfile
    assert "/usr/share/nginx/html-next/" in frontend_dockerfile


def test_deploy_scope_resolution_keeps_units_in_main_shell() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    resolve_function = deploy_script.split("resolve_deploy_scope() {", 1)[1].split(
        "deploy_scope_has_unit() {", 1
    )[0]
    main_function = deploy_script.split("main() {", 1)[1]
    assert 'DEPLOY_RESOLVED_SCOPE="$(python3 -c' in resolve_function
    assert 'DEPLOY_RESOLVED_UNITS="$(python3 -c' in resolve_function
    assert 'DEPLOY_RESOLVED_SCOPE="$(resolve_deploy_scope)"' not in deploy_script
    assert "resolve_deploy_scope" in main_function


def test_frontend_next_scope_does_not_build_backend_or_run_migration() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    remote_deploy = deploy_script.split("remote_deploy() {", 1)[1]
    hot_branch = remote_deploy.split('if [[ "$DEPLOY_RESOLVED_SCOPE" == "frontend-next" ]]; then', 1)[1].split(
        'if [[ "$DEPLOY_RESOLVED_SCOPE" == "frontend-hot"', 1
    )[0]
    assert "frontend_next_hot:updated" in hot_branch
    assert "frontend_next_hot:separated_frontend_web" in hot_branch
    assert "frontend_next_hot:monolith_compat" in hot_branch
    assert 'FRONTEND_COMPOSE_FILE="$FRONTEND_COMPOSE_FILE"' in hot_branch
    assert 'sudo docker compose -f "$FRONTEND_COMPOSE_FILE" up -d --no-deps --force-recreate frontend-web' in hot_branch
    assert "backend-api" not in hot_branch
    assert "docker_compose_build" not in hot_branch
    assert "migration" not in hot_branch
    assert "runtime-worker" not in hot_branch
    assert "analytics-worker" not in hot_branch


def test_combined_frontend_next_scope_publishes_dist_without_backend_build() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    make_package = deploy_script.split("make_package() {", 1)[1].split(
        "fetch_remote_deploy_manifest() {", 1
    )[0]
    package_branch = deploy_script.split('if ! cloud_ssh env \\', 2)[2]
    publish_function = deploy_script.split("publish_frontend_next() {", 1)[1].split(
        "refresh_gateway_if_present() {", 1
    )[0]
    combined_branch = deploy_script.split('if has_unit frontend-next && test "$DEPLOY_SCOPE" != all; then', 1)[1].split(
        'if test "$DEPLOY_SCOPE" = all; then\n  publish_frontend_next', 1
    )[0]
    assert "if ! deploy_scope_has_unit frontend-legacy && ! deploy_scope_has_unit frontend-next; then" in make_package
    assert "tar_excludes+=(--exclude='frontend/dist')" in make_package
    assert package_branch.index("publish_frontend_next() {") < package_branch.index("if has_unit frontend-next")
    assert package_branch.index("refresh_gateway_if_present() {") < package_branch.index("if has_unit ops")
    assert "test -f frontend-next/dist/index.html" in publish_function
    assert "frontend_next:separated_frontend_web" in publish_function
    assert "frontend_next:monolith_compat" in publish_function
    assert "frontend_next:updated" in publish_function
    assert "publish_frontend_next" in combined_branch
    assert "backend-api" not in publish_function
    assert "migration" not in publish_function
    assert "runtime-worker" not in publish_function


def test_backend_api_scope_restarts_api_only_and_does_not_touch_frontend_dist() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    backend_branch = deploy_script.split('if has_unit backend-api && test "$DEPLOY_SCOPE" != all; then', 1)[1].split(
        'if has_unit worker && test "$DEPLOY_SCOPE" != all; then', 1
    )[0]
    assert 'docker_compose_build "$BACKEND_API_COMPOSE_FILE" backend-api' in backend_branch
    assert 'sudo docker compose -f "$BACKEND_API_COMPOSE_FILE" up -d --no-deps --no-build --force-recreate backend-api' in backend_branch
    assert "backend_api:updated" in backend_branch
    assert "frontend-next/dist" not in backend_branch
    assert "frontend/dist" not in backend_branch
    assert "migration" not in backend_branch
    assert "runtime-worker" not in backend_branch


def test_db_migration_scope_requires_backup_before_migration() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    migration_branch = deploy_script.split('if has_unit db-migration && test "$DEPLOY_SCOPE" != all; then', 1)[1].split(
        'if has_unit backend-api && test "$DEPLOY_SCOPE" != all; then', 1
    )[0]
    assert "run_database_backup" in deploy_script
    assert "bash ./scripts/backup_database.sh" in deploy_script
    assert "db_migration:backup_failed" in deploy_script
    assert "db_migration:backup_script_missing" in deploy_script
    assert migration_branch.index("run_database_backup") < migration_branch.index("--exit-code-from migration migration")
    assert "backend-api" not in migration_branch
    assert "runtime-worker" not in migration_branch

    all_branch = deploy_script.split('if test "$DEPLOY_SCOPE" = all; then', 1)[1].split("if has_unit go; then", 1)[0]
    assert all_branch.index("run_database_backup") < all_branch.index("--exit-code-from migration migration")


def test_separated_topology_uses_service_specific_compose_files() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")
    one_click_script = read_repo_file("scripts/one_click_cloud_deploy.sh")
    deploy_example = read_repo_file(".env.deploy.local.example")

    assert 'BACKEND_API_COMPOSE_FILE="${BACKEND_API_COMPOSE_FILE:-docker-compose.separated.yml}"' in deploy_script
    assert 'FRONTEND_COMPOSE_FILE="${FRONTEND_COMPOSE_FILE:-docker-compose.separated.yml}"' in deploy_script
    assert 'DB_MIGRATION_COMPOSE_FILE="${DB_MIGRATION_COMPOSE_FILE:-docker-compose.mysql.yml}"' in deploy_script
    assert 'RUNTIME_COMPOSE_FILE="${RUNTIME_COMPOSE_FILE:-docker-compose.mysql.yml}"' in deploy_script
    assert 'GO_COMPOSE_FILE="${GO_COMPOSE_FILE:-docker-compose.mysql.yml}"' in deploy_script
    assert 'BACKEND_API_PORT="${BACKEND_API_PORT:-18091}"' in quick_script
    assert "export BACKEND_API_COMPOSE_FILE FRONTEND_COMPOSE_FILE DB_MIGRATION_COMPOSE_FILE RUNTIME_COMPOSE_FILE GO_COMPOSE_FILE" in quick_script
    assert "--backend-api-compose-file <file>" in quick_script
    assert "--frontend-compose-file <file>" in quick_script
    assert "--db-migration-compose-file <file>" in one_click_script
    assert "BACKEND_API_COMPOSE_FILE=docker-compose.separated.yml" in deploy_example
    assert "DB_MIGRATION_COMPOSE_FILE=docker-compose.mysql.yml" in deploy_example


def test_all_scope_runs_frontend_after_go_and_then_gateway_refresh() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    package_remote = deploy_script.split("remote_deploy() {", 1)[1]
    package_remote = package_remote.split("remote_configure_ops() {", 1)[0]

    assert package_remote.index('if test "$DEPLOY_SCOPE" = all; then\n  run_database_backup') < package_remote.index(
        "if has_unit go; then"
    )
    assert package_remote.index("if has_unit go; then") < package_remote.index(
        'if test "$DEPLOY_SCOPE" = all; then\n  publish_frontend_next'
    )
    assert package_remote.index(
        'if test "$DEPLOY_SCOPE" = all; then\n  publish_frontend_next\nfi'
    ) < package_remote.index(
        'if has_unit ops || test "$DEPLOY_SCOPE" = all; then\n  refresh_gateway_if_present\nfi'
    )


def test_verify_remote_is_scope_aware_for_separated_topology() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    verify_function = deploy_script.split("verify_deploy_scope_remote() {", 1)[1].split("verify_go_remote() {", 1)[0]
    assert "verify_frontend_next_remote" in verify_function
    assert "verify_backend_api_remote" in verify_function
    assert "verify_worker_remote" in verify_function
    assert "verify_go_remote" in verify_function
    assert "deploy_scope_has_unit backend-api" in verify_function
    assert "deploy_scope_has_unit frontend-next" in verify_function
    assert "verify_remote" in verify_function
    assert 'BACKEND_API_PORT="$BACKEND_API_PORT"' in deploy_script
    assert "tquant-frontend-web health" in deploy_script
    assert "tquant-backend-api health" in deploy_script


def test_deploy_scope_helper_recognizes_frontend_next_and_blocks_strategy_policy() -> None:
    script = read_repo_file("scripts/deploy_scope.py")

    assert "frontend-next/" in script
    assert "frontend-legacy" in script
    assert "backend-api" in script
    assert "db-migration" in script
    assert "strategy_policy.py requires explicit human review" in script


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
    assert 'if [[ "$DEPLOY_RESOLVED_SCOPE" != "go" ]]; then' in deploy_script
    assert "frontend_next_uses_hot_package" in deploy_script
    assert "frontend_hot_uses_hot_package" in deploy_script
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
    assert "deploy-cloud-next:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope frontend-next --frontend-next-required" in makefile
    assert "deploy-cloud-api:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope backend-api" in makefile
    assert "deploy-cloud-db:" in makefile
    assert "./scripts/one_click_cloud_deploy.sh --scope db-migration" in makefile
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
    assert "Upload frontend-next dist artifact" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "Download frontend dist artifact" in workflow
    assert "Download frontend-next dist artifact" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "Select deploy target scope" in workflow
    assert "fetch-depth: 0" in workflow
    assert "github.event.before" in workflow
    assert 'git diff --name-only "$before" "$after"' in workflow
    assert 'git diff --name-only HEAD^ HEAD' in workflow
    assert "python3 scripts/deploy_scope.py" in workflow
    assert "DEPLOY_TARGET_SCOPE=$scope" in workflow
    assert "DEPLOY_CHANGED_FILES<<DEPLOY_FILES" in workflow
    assert "DEPLOY_FRONTEND_HOT_REQUIRED" in workflow
    assert "DEPLOY_FRONTEND_NEXT_REQUIRED" in workflow


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


def test_frontend_next_monitor_cutover_flag_reaches_web_container() -> None:
    compose = read_repo_file("docker-compose.mysql.yml")
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert "FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED: ${FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED:-false}" in compose
    assert "FRONTEND_NEXT_CUTOVER_PATHS: ${FRONTEND_NEXT_CUTOVER_PATHS:-}" in compose
    assert 'upsert_env_value FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED "$FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED"' in deploy_script
    assert 'upsert_env_value FRONTEND_NEXT_CUTOVER_PATHS "$FRONTEND_NEXT_CUTOVER_PATHS"' in deploy_script
    assert "export FRONTEND_NEXT_MONITOR_CUTOVER_ENABLED" in quick_script
    assert "export FRONTEND_NEXT_CUTOVER_PATHS" in quick_script


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
