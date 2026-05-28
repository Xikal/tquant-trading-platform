#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_ORDER = {"core": 1, "full": 2, "release": 3}
SENSITIVE_COMPACT_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "databaseurl",
)


@dataclass(frozen=True)
class RegressionStep:
    step_id: str
    name: str
    profile: str
    dimensions: tuple[str, ...]
    command: tuple[str, ...] = ()
    cwd: Path = PROJECT_ROOT
    timeout_seconds: int = 300
    env: dict[str, str] = field(default_factory=dict)
    runner: Callable[["RegressionStep", argparse.Namespace], "StepResult"] | None = None


@dataclass
class StepResult:
    step_id: str
    name: str
    profile: str
    dimensions: list[str]
    command: str
    cwd: str
    ok: bool
    skipped: bool
    exit_code: int | None
    elapsed_ms: int
    output_tail: str
    error: str = ""


def main() -> int:
    args = parse_args()
    started = time.time()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    steps = select_steps(build_steps(args), args)
    results: list[StepResult] = []
    for step in steps:
        result = step.runner(step, args) if step.runner else run_process_step(step, args)
        results.append(result)
        print(f"{'PASS' if result.ok else 'FAIL'} {step.step_id} {result.elapsed_ms}ms")
        if args.fail_fast and not result.ok:
            break
    report = build_report(args, results, started)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    json_path = report_dir / f"full-regression-{stamp}.json"
    md_path = report_dir / f"full-regression-{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0 if report["ok"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-platform regression and release QA gates.")
    parser.add_argument("--profile", choices=PROFILE_ORDER, default="core")
    parser.add_argument("--report-dir", default=str(PROJECT_ROOT / ".runtime" / "full-regression"))
    parser.add_argument("--only", action="append", default=[], help="Run only matching step id. Can be repeated.")
    parser.add_argument("--skip", action="append", default=[], help="Skip matching step id. Can be repeated.")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--frontend-port", type=int, default=4173)
    parser.add_argument("--cloud-verify", action="store_true", help="Include remote cloud health/performance verification.")
    return parser.parse_args()


def build_steps(args: argparse.Namespace) -> list[RegressionStep]:
    backend_python = resolve_backend_python()
    python_env = {"PYTHONPATH": str(PROJECT_ROOT / "backend")}
    return [
        RegressionStep(
            "backend_compile",
            "Backend compile check",
            "core",
            ("backend", "architecture"),
            (str(backend_python), "-m", "compileall", "app"),
            PROJECT_ROOT / "backend",
            180,
            python_env,
        ),
        RegressionStep(
            "backend_pytest",
            "Backend full pytest suite",
            "core",
            ("backend_api", "strategy_logic", "risk", "paper", "backtest", "ml", "security", "persistence"),
            (str(backend_python), "-m", "pytest", "backend/tests"),
            PROJECT_ROOT,
            900,
            python_env,
        ),
        RegressionStep(
            "warning_budget",
            "Backend pytest warning budget",
            "core",
            ("backend", "observability", "warning_budget"),
            (str(resolve_python()), "scripts/warning_budget.py", "backend/tests"),
            PROJECT_ROOT,
            900,
            python_env,
        ),
        RegressionStep(
            "frontend_lint",
            "Frontend lint and guard checks",
            "core",
            ("frontend", "privacy", "architecture"),
            ("npm", "run", "lint"),
            PROJECT_ROOT / "frontend",
            240,
        ),
        RegressionStep(
            "frontend_unit",
            "Frontend unit and page tests",
            "core",
            ("frontend", "ui", "mobile", "usability"),
            ("npm", "test", "--", "--run"),
            PROJECT_ROOT / "frontend",
            300,
        ),
        RegressionStep(
            "frontend_build",
            "Frontend production build",
            "core",
            ("frontend", "performance", "bundle"),
            ("npm", "run", "build"),
            PROJECT_ROOT / "frontend",
            420,
        ),
        RegressionStep(
            "go_bff_test",
            "Go bff-gateway tests",
            "core",
            ("go", "bff", "api"),
            ("go", "test", "./..."),
            PROJECT_ROOT / "go-services" / "bff-gateway",
            180,
        ),
        RegressionStep(
            "go_market_read_test",
            "Go market-read-service tests",
            "core",
            ("go", "market_data", "cache", "concurrency"),
            ("go", "test", "./..."),
            PROJECT_ROOT / "go-services" / "market-read-service",
            180,
        ),
        RegressionStep(
            "go_scan_worker_test",
            "Go scan-worker tests",
            "core",
            ("go", "scan_worker", "strategy_orchestration"),
            ("go", "test", "./..."),
            PROJECT_ROOT / "go-services" / "scan-worker",
            180,
        ),
        RegressionStep(
            "rust_cargo_test",
            "Rust tquant-rs tests",
            "core",
            ("rust", "finance_math", "parity"),
            ("cargo", "test"),
            PROJECT_ROOT / "rust" / "tquant-rs",
            300,
            {"PYO3_USE_ABI3_FORWARD_COMPATIBILITY": "1"},
        ),
        RegressionStep(
            "frontend_responsive_smoke",
            "Authenticated responsive UI smoke",
            "full",
            ("frontend", "ui", "mobile", "usability", "routing"),
            runner=run_frontend_responsive_smoke,
            timeout_seconds=240,
        ),
        RegressionStep(
            "api_smoke",
            "App API smoke",
            "full",
            ("backend_api", "mobile_api", "functionality"),
            ("./scripts/app_api_smoke.sh",),
            PROJECT_ROOT,
            240,
        ),
        RegressionStep(
            "qa_smoke_deep",
            "Workspace QA smoke with deep checks",
            "full",
            ("backend_api", "settings", "watchlist", "strategy_logic", "paper", "backtest", "persistence"),
            ("./scripts/qa_smoke.sh",),
            PROJECT_ROOT,
            900,
            {"QA_DEEP": "1"},
        ),
        RegressionStep(
            "go_rust_acceptance",
            "Go/Rust performance acceptance",
            "full",
            ("go", "rust", "performance", "production_path"),
            (str(resolve_python()), "scripts/verify_go_rust_performance_acceptance.py"),
            PROJECT_ROOT,
            900,
            {"BACKEND_PYTHON": str(backend_python)},
        ),
        RegressionStep(
            "prod_preflight",
            "Production preflight including native release checks",
            "release",
            ("deployment", "healthcheck", "native", "persistence"),
            ("./scripts/prod_preflight.sh",),
            PROJECT_ROOT,
            1200,
        ),
        RegressionStep(
            "cloud_verify",
            "Cloud deployment health and performance verification",
            "release",
            ("deployment", "healthcheck", "observability", "performance"),
            ("./scripts/quick_cloud_deploy.sh", "--verify-only", "--performance-verify"),
            PROJECT_ROOT,
            900,
        ),
    ]


def select_steps(steps: list[RegressionStep], args: argparse.Namespace) -> list[RegressionStep]:
    selected = [
        step
        for step in steps
        if PROFILE_ORDER[step.profile] <= PROFILE_ORDER[args.profile]
        and (step.step_id != "cloud_verify" or args.cloud_verify)
    ]
    if args.only:
        selected = [step for step in selected if any(pattern in step.step_id for pattern in args.only)]
    if args.skip:
        selected = [step for step in selected if not any(pattern in step.step_id for pattern in args.skip)]
    return selected


def run_process_step(step: RegressionStep, args: argparse.Namespace) -> StepResult:
    del args
    started = time.monotonic()
    env = os.environ.copy()
    env.update(step.env)
    try:
        completed = subprocess.run(
            list(step.command),
            cwd=step.cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=step.timeout_seconds,
        )
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return StepResult(
            step.step_id,
            step.name,
            step.profile,
            list(step.dimensions),
            command_text(step.command),
            str(step.cwd),
            completed.returncode == 0,
            False,
            completed.returncode,
            elapsed_ms(started),
            redact(tail(output)),
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return StepResult(
            step.step_id,
            step.name,
            step.profile,
            list(step.dimensions),
            command_text(step.command),
            str(step.cwd),
            False,
            False,
            None,
            elapsed_ms(started),
            redact(tail(str(output))),
            error=f"timeout after {step.timeout_seconds}s",
        )
    except FileNotFoundError as exc:
        return StepResult(
            step.step_id,
            step.name,
            step.profile,
            list(step.dimensions),
            command_text(step.command),
            str(step.cwd),
            False,
            False,
            None,
            elapsed_ms(started),
            "",
            error=str(exc),
        )


def run_frontend_responsive_smoke(step: RegressionStep, args: argparse.Namespace) -> StepResult:
    started = time.monotonic()
    port = int(args.frontend_port)
    base_url = f"http://127.0.0.1:{port}"
    runtime_dir = PROJECT_ROOT / ".runtime" / "full-regression"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    preview_log = runtime_dir / "frontend-preview.log"
    env = os.environ.copy()
    env.update({
        "FRONTEND_SMOKE_URL": base_url,
        "SMOKE_MOCK_AUTH": "1",
        "SMOKE_REQUIRE_AUTH": "1",
    })
    preview = subprocess.Popen(
        ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT / "frontend",
        stdout=preview_log.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_url(base_url, timeout_seconds=30)
        completed = subprocess.run(
            ["npm", "run", "smoke:responsive"],
            cwd=PROJECT_ROOT / "frontend",
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=step.timeout_seconds,
        )
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        if preview_log.exists():
            output += "\n[preview]\n" + preview_log.read_text(encoding="utf-8", errors="replace")
        return StepResult(
            step.step_id,
            step.name,
            step.profile,
            list(step.dimensions),
            "npm run preview && npm run smoke:responsive",
            str(PROJECT_ROOT / "frontend"),
            completed.returncode == 0,
            False,
            completed.returncode,
            elapsed_ms(started),
            redact(tail(output)),
        )
    except Exception as exc:
        output = preview_log.read_text(encoding="utf-8", errors="replace") if preview_log.exists() else ""
        return StepResult(
            step.step_id,
            step.name,
            step.profile,
            list(step.dimensions),
            "npm run preview && npm run smoke:responsive",
            str(PROJECT_ROOT / "frontend"),
            False,
            False,
            None,
            elapsed_ms(started),
            redact(tail(output)),
            error=str(exc),
        )
    finally:
        preview.terminate()
        try:
            preview.wait(timeout=10)
        except subprocess.TimeoutExpired:
            preview.kill()


def wait_for_url(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"frontend preview did not become ready: {last_error}")


def build_report(args: argparse.Namespace, results: list[StepResult], started: float) -> dict:
    dimensions: dict[str, dict[str, int]] = {}
    for result in results:
        for dimension in result.dimensions:
            bucket = dimensions.setdefault(dimension, {"passed": 0, "failed": 0, "skipped": 0})
            if result.skipped:
                bucket["skipped"] += 1
            elif result.ok:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
    failed = [item for item in results if not item.ok and not item.skipped]
    return {
        "ok": not failed,
        "profile": args.profile,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int((time.time() - started) * 1000),
        "summary": {
            "total": len(results),
            "passed": sum(1 for item in results if item.ok),
            "failed": len(failed),
            "skipped": sum(1 for item in results if item.skipped),
        },
        "coverage_dimensions": dimensions,
        "results": [item.__dict__ for item in results],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Full Regression Report",
        "",
        f"- Profile: `{report['profile']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Result: `{'PASS' if report['ok'] else 'FAIL'}`",
        f"- Steps: {report['summary']['passed']} passed / {report['summary']['failed']} failed / {report['summary']['skipped']} skipped",
        "",
        "## Coverage Dimensions",
        "",
    ]
    for name, stats in sorted(report["coverage_dimensions"].items()):
        lines.append(f"- `{name}`: {stats['passed']} passed, {stats['failed']} failed, {stats['skipped']} skipped")
    lines.extend(["", "## Step Results", ""])
    for item in report["results"]:
        status = "PASS" if item["ok"] else "SKIP" if item["skipped"] else "FAIL"
        lines.append(f"### {status} {item['step_id']}")
        lines.append("")
        lines.append(f"- Name: {item['name']}")
        lines.append(f"- Dimensions: {', '.join(item['dimensions'])}")
        lines.append(f"- Command: `{item['command']}`")
        lines.append(f"- Elapsed: {item['elapsed_ms']} ms")
        if item.get("error"):
            lines.append(f"- Error: {item['error']}")
        if item.get("output_tail"):
            lines.extend(["", "```text", item["output_tail"], "```"])
        lines.append("")
    return "\n".join(lines)


def resolve_backend_python() -> Path:
    local = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"
    if local.exists():
        return local
    return resolve_python()


def resolve_python() -> Path:
    return Path(sys.executable).resolve()


def command_text(command: tuple[str, ...]) -> str:
    return " ".join(command)


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def tail(text: str, max_chars: int = 6000) -> str:
    return text[-max_chars:].strip()


def redact(text: str) -> str:
    lines = []
    for line in text.splitlines():
        compact = re.sub(r"[^a-z0-9]", "", line.lower())
        if any(key in compact for key in SENSITIVE_COMPACT_KEYS):
            match = re.match(r"^([^:=]+[:=]).*$", line)
            lines.append(f"{match.group(1)} <redacted>" if match else "<redacted>")
        else:
            lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
