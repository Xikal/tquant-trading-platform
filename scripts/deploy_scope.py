#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable


ORDERED_UNITS = ("db-migration", "backend-api", "worker", "go", "frontend-next", "ops")
SUPPORTED_EXPLICIT_SCOPES = {"auto", "all", *ORDERED_UNITS, "ops-docs", "verify-only"}
RETIRED_EXPLICIT_SCOPES = {"frontend-hot", "frontend-legacy"}
DOC_ONLY_PATHS = ("docs/",)
STRATEGY_POLICY_PATHS = {"strategy_policy.py", "backend/app/services/low_buy/strategy_policy.py"}


@dataclass(frozen=True)
class DeployScope:
    scope: str
    units: tuple[str, ...]
    requires_migration: bool = False
    requires_backend_restart: bool = False
    requires_frontend_next_build: bool = False
    requires_worker_restart: bool = False
    requires_go_restart: bool = False
    requires_ops_reload: bool = False
    blocked: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "units": list(self.units),
            "requires_migration": self.requires_migration,
            "requires_backend_restart": self.requires_backend_restart,
            "requires_frontend_next_build": self.requires_frontend_next_build,
            "requires_worker_restart": self.requires_worker_restart,
            "requires_go_restart": self.requires_go_restart,
            "requires_ops_reload": self.requires_ops_reload,
            "blocked": self.blocked,
            "reason": self.reason,
        }


def normalize_changed_files(paths: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        value = path.strip()
        if not value:
            continue
        normalized.append(str(PurePosixPath(value.replace("\\", "/"))))
    return sorted(set(normalized))


def resolve_deploy_scope(paths: Iterable[str], explicit_scope: str = "auto") -> DeployScope:
    if explicit_scope in RETIRED_EXPLICIT_SCOPES:
        return DeployScope(
            scope="blocked",
            units=(),
            blocked=True,
            reason=f"{explicit_scope} is retired; deploy frontend-next instead",
        )
    if explicit_scope not in SUPPORTED_EXPLICIT_SCOPES:
        return DeployScope(
            scope="blocked",
            units=(),
            blocked=True,
            reason=f"invalid explicit scope: {explicit_scope}",
        )
    if explicit_scope != "auto":
        return _scope_from_units((explicit_scope,), reason=f"explicit scope: {explicit_scope}")

    changed = normalize_changed_files(paths)
    if not changed:
        return _scope_from_units(("all",), reason="no changed files")

    if any(path in STRATEGY_POLICY_PATHS for path in changed):
        return DeployScope(
            scope="blocked",
            units=(),
            blocked=True,
            reason="strategy_policy.py requires explicit human review before deployment",
        )

    units: set[str] = set()
    docs_only = True
    for path in changed:
        classified = _classify_path(path)
        if classified == "all":
            return _scope_from_units(("all",), reason=f"unclassified path requires full deploy: {path}")
        if classified not in {"ops-docs", "verify-only"}:
            docs_only = False
        if classified == "db-migration":
            units.update(("db-migration", "backend-api"))
        elif classified == "backend-api":
            units.add("backend-api")
        elif classified == "worker":
            units.add("worker")
        elif classified == "go":
            units.add("go")
        elif classified == "frontend-next":
            units.add("frontend-next")
        elif classified == "frontend-retired":
            units.add("ops-docs")
        elif classified == "ops":
            units.add("ops")

    if not units:
        return _scope_from_units(("ops-docs" if docs_only else "verify-only",), reason="docs-only or verification-only changes")
    return _scope_from_units(tuple(unit for unit in ORDERED_UNITS if unit in units), reason="changed files classified")


def _classify_path(path: str) -> str:
    if path.startswith("frontend-next/"):
        return "frontend-next"
    if path.startswith("frontend/"):
        return "frontend-retired"
    if path.startswith("go-services/"):
        return "go"
    if path.startswith("backend/alembic/") or path.startswith("backend/app/models/"):
        return "db-migration"
    if _is_worker_path(path):
        return "worker"
    if path == "backend/app/main.py":
        return "backend-api"
    if path.startswith("backend/app/api/") or path.startswith("backend/app/services/") or path.startswith("backend/app/core/"):
        return "backend-api"
    if path.startswith("backend/deploy/"):
        return "backend-api"
    if _is_ops_path(path):
        return "ops"
    if path.startswith(DOC_ONLY_PATHS) or path in {"AGENTS.md", "IMPLEMENTATION_PLAN.md"}:
        return "ops-docs"
    if path.startswith("backend/tests/"):
        return "ops"
    return "all"


def _is_worker_path(path: str) -> bool:
    worker_markers = (
        "backend/app/workers/",
        "backend/scripts/analytics_worker.py",
        "backend/scripts/backtest_worker.py",
        "backend/scripts/",
        "scripts/backtest_worker.py",
        "scripts/analytics_worker.py",
    )
    if path.startswith("backend/app/services/runtime/"):
        return True
    return any(path.startswith(marker) for marker in worker_markers) and "deploy" not in path


def _is_ops_path(path: str) -> bool:
    ops_prefixes = (
        ".github/",
        "deploy/",
        "scripts/",
    )
    ops_exact = {
        ".env.deploy.local.example",
        ".gitignore",
        "Makefile",
        "docker-compose.mysql.yml",
        "docker-compose.separated.yml",
    }
    return path in ops_exact or path.startswith(ops_prefixes)


def _scope_from_units(units: tuple[str, ...], reason: str) -> DeployScope:
    if not units:
        return DeployScope(scope="verify-only", units=(), reason=reason)
    if "all" in units:
        units = ("all",)
        scope = "all"
    else:
        units = tuple(dict.fromkeys(units))
        scope = ",".join(units)
    return DeployScope(
        scope=scope,
        units=units,
        requires_migration="db-migration" in units or "all" in units,
        requires_backend_restart="backend-api" in units or "all" in units,
        requires_frontend_next_build="frontend-next" in units or "all" in units,
        requires_worker_restart="worker" in units or "all" in units,
        requires_go_restart="go" in units or "all" in units,
        requires_ops_reload="ops" in units or "all" in units,
        reason=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve deployment scope from changed files.")
    parser.add_argument("--scope", default="auto", help="Explicit scope or auto.")
    parser.add_argument("--changed-files-from", help="File containing newline-separated changed paths.")
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    parser.add_argument("paths", nargs="*", help="Changed paths when --changed-files-from is not used.")
    args = parser.parse_args(argv)

    paths = args.paths
    if args.changed_files_from:
        paths = [line.rstrip("\n") for line in open(args.changed_files_from, encoding="utf-8")]
    result = resolve_deploy_scope(paths, explicit_scope=args.scope)
    if args.format == "shell":
        print(f"DEPLOY_RESOLVED_SCOPE={result.scope}")
        print(f"DEPLOY_RESOLVED_UNITS={' '.join(result.units)}")
        print(f"DEPLOY_SCOPE_BLOCKED={1 if result.blocked else 0}")
        print(f"DEPLOY_SCOPE_REASON={result.reason}")
    else:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 2 if result.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
