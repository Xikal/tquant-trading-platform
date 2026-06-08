from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from scripts.deploy_scope import resolve_deploy_scope  # noqa: E402


def test_frontend_next_only_routes_to_frontend_next() -> None:
    result = resolve_deploy_scope(["frontend-next/src/features/paper/PaperPage.tsx"])

    assert result.scope == "frontend-next"
    assert result.units == ("frontend-next",)
    assert result.requires_frontend_next_build is True
    assert result.requires_backend_restart is False
    assert result.requires_migration is False


def test_frontend_legacy_only_routes_to_frontend_legacy() -> None:
    result = resolve_deploy_scope(["frontend/src/features/paper/PaperTradingPage.tsx"])

    assert result.scope == "frontend-legacy"
    assert result.requires_legacy_frontend_build is True
    assert result.requires_frontend_next_build is False


def test_backend_api_only_routes_to_backend_api() -> None:
    result = resolve_deploy_scope(["backend/app/api/routes/paper.py"])

    assert result.scope == "backend-api"
    assert result.requires_backend_restart is True
    assert result.requires_frontend_next_build is False


def test_backend_main_routes_to_backend_api() -> None:
    result = resolve_deploy_scope(["backend/app/main.py"])

    assert result.scope == "backend-api"
    assert result.requires_backend_restart is True
    assert result.requires_migration is False


def test_migration_routes_to_db_migration_and_backend_api() -> None:
    result = resolve_deploy_scope(["backend/alembic/versions/20260609_add_table.py"])

    assert result.scope == "db-migration,backend-api"
    assert result.units == ("db-migration", "backend-api")
    assert result.requires_migration is True
    assert result.requires_backend_restart is True


def test_worker_only_routes_to_worker() -> None:
    result = resolve_deploy_scope(["backend/app/services/runtime/task_scheduler.py"])

    assert result.scope == "worker"
    assert result.requires_worker_restart is True
    assert result.requires_backend_restart is False


def test_go_only_routes_to_go() -> None:
    result = resolve_deploy_scope(["go-services/bff/main.go"])

    assert result.scope == "go"
    assert result.requires_go_restart is True
    assert result.requires_backend_restart is False


def test_docs_only_does_not_trigger_business_deploy() -> None:
    result = resolve_deploy_scope(["docs/reports/frontend-next.md"])

    assert result.scope == "ops-docs"
    assert result.units == ("ops-docs",)
    assert result.requires_backend_restart is False
    assert result.requires_frontend_next_build is False


def test_strategy_policy_blocks_auto_deploy() -> None:
    result = resolve_deploy_scope(["strategy_policy.py"])

    assert result.scope == "blocked"
    assert result.blocked is True
    assert "strategy_policy.py" in result.reason


def test_mixed_frontend_next_and_backend_routes_to_both_units() -> None:
    result = resolve_deploy_scope(["frontend-next/src/index.tsx", "backend/app/api/routes/paper.py"])

    assert result.scope == "backend-api,frontend-next"
    assert result.units == ("backend-api", "frontend-next")
    assert result.requires_backend_restart is True
    assert result.requires_frontend_next_build is True


def test_frontend_next_and_frontend_nginx_routes_to_frontend_next_and_ops() -> None:
    result = resolve_deploy_scope(["frontend-next/src/index.tsx", "deploy/frontend/nginx.conf"])

    assert result.scope == "frontend-next,ops"
    assert result.units == ("frontend-next", "ops")
    assert result.requires_frontend_next_build is True
    assert result.requires_ops_reload is True
    assert result.requires_backend_restart is False
    assert result.requires_migration is False


def test_unknown_file_falls_back_to_all() -> None:
    result = resolve_deploy_scope(["some-new-root-file.txt"])

    assert result.scope == "all"
    assert result.requires_migration is True
    assert result.requires_frontend_next_build is True


def test_cli_outputs_shell_assignments(tmp_path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_text("frontend-next/src/index.tsx\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "python3",
            "scripts/deploy_scope.py",
            "--changed-files-from",
            str(changed),
            "--format",
            "shell",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "DEPLOY_RESOLVED_SCOPE=frontend-next" in completed.stdout
    assert "DEPLOY_RESOLVED_UNITS=frontend-next" in completed.stdout


def test_cli_outputs_json() -> None:
    completed = subprocess.run(
        ["python3", "scripts/deploy_scope.py", "backend/app/api/routes/paper.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["scope"] == "backend-api"
    assert payload["requires_backend_restart"] is True
