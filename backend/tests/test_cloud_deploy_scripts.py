from __future__ import annotations

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
    assert "RUN_LOCAL_CHECKS=1" in quick_script
    assert "RUN_FRONTEND_BUILD=1" in quick_script
    assert "--fast-risk-accepted" in quick_script
    assert "fast mode requires --fast-risk-accepted" in quick_script


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


def test_cloud_deploy_starts_runtime_scheduler_container() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert "tquant-runtime-scheduler-mysql" in deploy_script
    assert "runtime-scheduler" in deploy_script
    assert "app runtime-scheduler runtime-worker backtest-worker analytics-worker" in deploy_script
    assert "tquant-runtime-scheduler-mysql" in quick_script


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
