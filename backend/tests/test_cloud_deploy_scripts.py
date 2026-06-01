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


def test_cloud_deploy_distinguishes_nginx_sni_from_public_domain_reachability() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")

    assert "VERIFY_PUBLIC_DOMAIN" in deploy_script
    assert "verify_https_remote" in deploy_script
    assert "--resolve \"${CLOUD_DOMAIN}:443:127.0.0.1\"" in deploy_script
    assert "https_sni_loopback:ok" in deploy_script
    assert "public_domain:warning" in deploy_script
