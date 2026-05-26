from __future__ import annotations

import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "docs" / "reports" / "go-rust-performance-acceptance-2026-05-25.json"
BACKEND_PYTHON = Path(
    os.environ.get("BACKEND_PYTHON", "")
).expanduser() if os.environ.get("BACKEND_PYTHON") else Path(shutil.which("python3") or shutil.which("python") or "")
if str(BACKEND_PYTHON) and not BACKEND_PYTHON.is_absolute():
    BACKEND_PYTHON = PROJECT_ROOT / BACKEND_PYTHON
RUST_TARGET_RELEASE_DIR = PROJECT_ROOT / "rust" / "tquant-rs" / "target" / "release" / "deps"

GO_QUOTE_BENCHMARK_NS_PER_OP_MAX = 10_000.0
GO_QUOTE_BENCHMARK_BYTES_PER_OP_MAX = 12_000.0
GO_QUOTE_BENCHMARK_ALLOCS_PER_OP_MAX = 250.0
GO_CHECK_TIMEOUT_SECONDS = 120
GO_QUOTE_BENCHMARK_TIMEOUT_SECONDS = 60
RUST_BENCHMARK_MIN_SPEEDUP = 5.0
RUST_BENCH_REPEAT = 5
RUST_BENCH_DRAWDOWN_SIZE = 300_000
RUST_BENCH_ROLLING_SIZE = 160_000
RUST_BENCH_ATR_SIZE = 120_000
GO_QUOTE_BENCHMARK_COMMAND = [
    "go",
    "test",
    "-run",
    "^$",
    "-bench",
    "^BenchmarkQuoteBatchHandlerCachedPayload$",
    "-benchmem",
    "-benchtime=1s",
    "./...",
]

GO_QUOTE_BENCHMARK_PATTERN = re.compile(
    r"BenchmarkQuoteBatchHandlerCachedPayload-\d+\s+\d+\s+"
    r"(?P<ns_per_op>\d+(?:\.\d+)?) ns/op\s+"
    r"(?P<bytes_per_op>\d+(?:\.\d+)?) B/op\s+"
    r"(?P<allocs_per_op>\d+) allocs/op"
)


def main() -> int:
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "go": _go_checks(),
        "rust": _rust_checks(),
        "python_rust_seam": _python_rust_seam_check(),
    }
    report["ok"] = all(section.get("ok") for section in report.values() if isinstance(section, dict))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(REPORT_PATH))
    return 0 if report["ok"] else 1


def _go_checks() -> dict:
    commands = [
        ("market-read-service", ["go", "test", "./..."], PROJECT_ROOT / "go-services" / "market-read-service", GO_CHECK_TIMEOUT_SECONDS),
        ("bff-gateway", ["go", "test", "./..."], PROJECT_ROOT / "go-services" / "bff-gateway", GO_CHECK_TIMEOUT_SECONDS),
        ("scan-worker", ["go", "test", "./..."], PROJECT_ROOT / "go-services" / "scan-worker", GO_CHECK_TIMEOUT_SECONDS),
    ]
    results = [_run(name, cmd, cwd, timeout=timeout) for name, cmd, cwd, timeout in commands]
    benchmark = _go_quote_benchmark()
    return {
        "ok": all(item["ok"] for item in results) and benchmark["ok"],
        "checks": results,
        "benchmark": benchmark,
    }


def _rust_checks() -> dict:
    cwd = PROJECT_ROOT / "rust" / "tquant-rs"
    return _run(
        "tquant-rs cargo test",
        ["cargo", "test", "--no-default-features"],
        cwd,
        extra_env={"PYO3_USE_ABI3_FORWARD_COMPATIBILITY": "1"},
    )


def _python_rust_seam_check() -> dict:
    if not BACKEND_PYTHON.exists():
        return {
            "ok": False,
            "metric": "rust_python_extension_import",
            "notes": f"missing backend python: {BACKEND_PYTHON}",
        }
    build = _run(
        "tquant-rs cargo build release",
        ["cargo", "build", "--release", "--features", "extension-module"],
        PROJECT_ROOT / "rust" / "tquant-rs",
        extra_env={"PYO3_USE_ABI3_FORWARD_COMPATIBILITY": "1"},
    )
    if not build["ok"]:
        build["metric"] = "rust_python_extension_import"
        build["notes"] = "rust build failed before import benchmark"
        return build

    module_info = _import_rust_module(BACKEND_PYTHON, target_dir=RUST_TARGET_RELEASE_DIR)
    if not module_info["ok"]:
        return module_info

    bench = _run_rust_module_benchmark(BACKEND_PYTHON)
    if not bench["ok"]:
        return bench

    payload = bench["payload"]
    expected_drawdown = _python_max_drawdown(_equity_values(RUST_BENCH_DRAWDOWN_SIZE))
    speedups = bench["speedups"]
    speedup_ok = min(speedups.values()) >= RUST_BENCHMARK_MIN_SPEEDUP
    ok = (
        module_info["payload"] == {
            "drawdown": 0.25,
            "rolling": 4,
            "atr": 3,
            "rsi": 83.3333,
            "vwap": 10.5,
            "rank_ic": -1.0,
        }
        and abs(float(payload["drawdown"]) - expected_drawdown) < 1e-8
        and payload["rolling_len"] == RUST_BENCH_ROLLING_SIZE
        and payload["atr_len"] == RUST_BENCH_ATR_SIZE
        and payload["python_rolling_len"] == RUST_BENCH_ROLLING_SIZE
        and payload["python_atr_len"] == RUST_BENCH_ATR_SIZE
        and speedup_ok
    )
    return {
        "ok": ok,
        "metric": "rust_python_extension_import_and_parity",
        "speedup_threshold": RUST_BENCHMARK_MIN_SPEEDUP,
        "drawdown": round(float(payload["drawdown"]), 6),
        "expected_drawdown": round(expected_drawdown, 6),
        "speedups": {key: round(value, 3) for key, value in speedups.items()},
        "timings_ms": bench["timings_ms"],
        "rolling_len": payload["rolling_len"],
        "atr_len": payload["atr_len"],
        "import_elapsed_ms": module_info["elapsed_ms"],
        "backend_python": str(BACKEND_PYTHON),
        "notes": "Rust abi3 extension imports under backend python, matches python parity, and clears the release benchmark threshold.",
    }


def _import_rust_module(python: Path, *, target_dir: Path) -> dict:
    script = (
        "import json, tquant_rs; "
        "payload = {"
        "'drawdown': tquant_rs.max_drawdown([100.0, 120.0, 90.0]), "
        "'rolling': len(tquant_rs.rolling_mean([1.0, 2.0, 3.0, 4.0], 2)), "
        "'atr': len(tquant_rs.atr_wilder([10.0, 11.0, 12.0], [9.0, 9.5, 10.0], [9.5, 10.5, 11.0], 2)), "
        "'rsi': round(tquant_rs.rsi_wilder([10.0, 11.0, 12.0, 11.0, 13.0], 3), 4), "
        "'vwap': round(tquant_rs.vwap([10.0, 11.0], [100.0, 100.0]), 4), "
        "'rank_ic': round(tquant_rs.rank_ic([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]), 4)"
        "}; "
        "print(json.dumps(payload))"
    )
    return _run_rust_module_script(python, script, "rust_python_extension_import", target_dir=target_dir)


def _run_rust_module_benchmark(python: Path) -> dict:
    script = textwrap.dedent(
        f"""
        import json
        import statistics
        import time
        import tquant_rs

        def equity_values(size):
            values = []
            equity = 100.0
            for index in range(size):
                equity *= 1.0 + __import__("math").sin(index / 17.0) * 0.001
                if index % 911 == 0:
                    equity *= 0.94
                values.append(equity)
            return values

        def python_max_drawdown(items):
            peak = 0.0
            max_drawdown = 0.0
            for value in items:
                if value > peak:
                    peak = value
                if peak > 0.0:
                    drawdown = (peak - value) / peak
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
            return max_drawdown

        def python_rolling_mean(items, window):
            result = []
            for index in range(len(items)):
                if index + 1 < window:
                    result.append(None)
                else:
                    window_slice = items[index + 1 - window:index + 1]
                    result.append(sum(window_slice) / window)
            return result

        def python_atr_wilder(highs, lows, closes, period):
            length = min(len(highs), len(lows), len(closes))
            if period == 0 or length < period + 1:
                return [None] * length
            true_ranges = []
            for index in range(1, length):
                high_low = highs[index] - lows[index]
                high_close = abs(highs[index] - closes[index - 1])
                low_close = abs(lows[index] - closes[index - 1])
                true_ranges.append(max(high_low, high_close, low_close))
            result = [None] * length
            atr = sum(true_ranges[:period]) / period
            result[period] = atr
            for index in range(period, len(true_ranges)):
                atr = (atr * (period - 1) + true_ranges[index]) / period
                result[index + 1] = atr
            return result

        def bench(func, *args):
            timings = []
            result = None
            for _ in range({RUST_BENCH_REPEAT}):
                started = time.perf_counter()
                result = func(*args)
                timings.append((time.perf_counter() - started) * 1000)
            return result, statistics.median(timings)

        values = equity_values({RUST_BENCH_DRAWDOWN_SIZE})
        rolling_values = equity_values({RUST_BENCH_ROLLING_SIZE})
        atr_values = equity_values({RUST_BENCH_ATR_SIZE})

        python_drawdown, python_drawdown_ms = bench(python_max_drawdown, values)
        rust_drawdown, rust_drawdown_ms = bench(tquant_rs.max_drawdown, values)
        python_rolling, python_rolling_ms = bench(python_rolling_mean, rolling_values, 20)
        rust_rolling, rust_rolling_ms = bench(tquant_rs.rolling_mean, rolling_values, 20)
        python_atr, python_atr_ms = bench(python_atr_wilder, atr_values, atr_values, atr_values, 14)
        rust_atr, rust_atr_ms = bench(tquant_rs.atr_wilder, atr_values, atr_values, atr_values, 14)

        payload = {{
            'drawdown': rust_drawdown,
            'rolling_len': len(rust_rolling),
            'atr_len': len(rust_atr),
            'python_drawdown': python_drawdown,
            'python_rolling_len': len(python_rolling),
            'python_atr_len': len(python_atr),
        }}
        timings = {{
            'python_drawdown_ms': python_drawdown_ms,
            'rust_drawdown_ms': rust_drawdown_ms,
            'python_rolling_ms': python_rolling_ms,
            'rust_rolling_ms': rust_rolling_ms,
            'python_atr_ms': python_atr_ms,
            'rust_atr_ms': rust_atr_ms,
        }}
        print(json.dumps({{'payload': payload, 'timings': timings}}))
        """
    )
    result = _run_rust_module_script(python, script, "rust_python_extension_benchmark", target_dir=RUST_TARGET_RELEASE_DIR)
    if not result["ok"]:
        return result
    outer_payload = result["payload"]
    payload = outer_payload["payload"]
    timings = outer_payload["timings"]
    speedups = {
        "max_drawdown": _speedup_ratio(timings["python_drawdown_ms"], timings["rust_drawdown_ms"]),
        "rolling_mean": _speedup_ratio(timings["python_rolling_ms"], timings["rust_rolling_ms"]),
        "atr_wilder": _speedup_ratio(timings["python_atr_ms"], timings["rust_atr_ms"]),
    }
    result["payload"] = payload
    result["speedups"] = speedups
    result["timings_ms"] = timings
    result["ok"] = min(speedups.values()) >= RUST_BENCHMARK_MIN_SPEEDUP
    return result


def _run_rust_module_script(python: Path, script: str, metric: str, *, target_dir: Path) -> dict:
    suffixes = _target_extension_suffixes(python)
    if not suffixes:
        return {
            "ok": False,
            "metric": metric,
            "notes": f"unable to query extension suffixes for {python}",
        }
    candidates = [target_dir / f"libtquant_rs{suffix}" for suffix in suffixes] + [
        target_dir / "libtquant_rs.dylib",
        target_dir / "libtquant_rs.so",
    ]
    module_path = next((path for path in candidates if path.exists()), None)
    if module_path is None:
        return {
            "ok": False,
            "metric": metric,
            "notes": f"missing built module in {target_dir}",
        }
    with tempfile.TemporaryDirectory() as tmp:
        link_suffix = next((suffix for suffix in suffixes if suffix.startswith(".abi3")), suffixes[0])
        link = Path(tmp) / f"tquant_rs{link_suffix}"
        if link.exists():
            link.unlink()
        os.symlink(module_path, link)
        started = time.perf_counter()
        completed = subprocess.run(
            [str(python), "-c", f"import sys; sys.path.insert(0, {tmp!r}); {script}"],
            cwd=tmp,
            env={**os.environ, "TQUANT_RUST_MATH_LOCAL_IMPORT": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
    if completed.returncode != 0:
        return {
            "ok": False,
            "metric": metric,
            "elapsed_ms": round(elapsed_ms, 3),
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "notes": f"failed to import {module_path.name} under {python}",
        }
    payload = json.loads(completed.stdout.strip() or "{}")
    return {
        "ok": True,
        "metric": metric,
        "elapsed_ms": round(elapsed_ms, 3),
        "payload": payload,
    }


def _go_quote_benchmark() -> dict:
    cwd = PROJECT_ROOT / "go-services" / "market-read-service"
    if shutil.which("go") is None:
        return {"ok": False, "name": "market-read-service benchmark", "notes": "go executable not found"}
    try:
        env = os.environ.copy()
        env.update(_go_env())
        completed = subprocess.run(
            GO_QUOTE_BENCHMARK_COMMAND,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=GO_QUOTE_BENCHMARK_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        return {
            "ok": False,
            "name": "market-read-service benchmark",
            "command": " ".join(GO_QUOTE_BENCHMARK_COMMAND),
            "timeout_seconds": GO_QUOTE_BENCHMARK_TIMEOUT_SECONDS,
            "ns_per_op": None,
            "bytes_per_op": None,
            "allocs_per_op": None,
            "thresholds": {
                "ns_per_op_max": GO_QUOTE_BENCHMARK_NS_PER_OP_MAX,
                "bytes_per_op_max": GO_QUOTE_BENCHMARK_BYTES_PER_OP_MAX,
                "allocs_per_op_max": GO_QUOTE_BENCHMARK_ALLOCS_PER_OP_MAX,
            },
            "stdout_tail": stdout[-1000:],
            "stderr_tail": stderr[-1000:],
        }
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    result = _parse_go_quote_benchmark(output)
    ok = completed.returncode == 0 and result is not None and all(
        [
            result["ns_per_op"] <= GO_QUOTE_BENCHMARK_NS_PER_OP_MAX,
            result["bytes_per_op"] <= GO_QUOTE_BENCHMARK_BYTES_PER_OP_MAX,
            result["allocs_per_op"] <= GO_QUOTE_BENCHMARK_ALLOCS_PER_OP_MAX,
        ]
    )
    return {
        "ok": ok,
        "name": "market-read-service benchmark",
        "command": " ".join(GO_QUOTE_BENCHMARK_COMMAND),
        "ns_per_op": result["ns_per_op"] if result else None,
        "bytes_per_op": result["bytes_per_op"] if result else None,
        "allocs_per_op": result["allocs_per_op"] if result else None,
        "thresholds": {
            "ns_per_op_max": GO_QUOTE_BENCHMARK_NS_PER_OP_MAX,
            "bytes_per_op_max": GO_QUOTE_BENCHMARK_BYTES_PER_OP_MAX,
            "allocs_per_op_max": GO_QUOTE_BENCHMARK_ALLOCS_PER_OP_MAX,
        },
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    }


def _parse_go_quote_benchmark(output: str) -> dict[str, float] | None:
    for line in output.splitlines():
        match = GO_QUOTE_BENCHMARK_PATTERN.search(line)
        if not match:
            continue
        return {
            "ns_per_op": float(match.group("ns_per_op")),
            "bytes_per_op": float(match.group("bytes_per_op")),
            "allocs_per_op": float(match.group("allocs_per_op")),
        }
    return None


def _go_env() -> dict[str, str]:
    env = {"GOTELEMETRY": "off"}
    if os.environ.get("CI", "").lower() not in {"1", "true", "yes"}:
        env.update(
            {
                "GOTOOLCHAIN": "local",
                "GOPROXY": "off",
                "GOSUMDB": "off",
            }
        )
    return env


def _target_extension_suffixes(python: Path) -> list[str]:
    completed = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.machinery, json; print(json.dumps(importlib.machinery.EXTENSION_SUFFIXES))",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    try:
        suffixes = json.loads(completed.stdout.strip() or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in suffixes if isinstance(item, str)]


def _run(name: str, command: list[str], cwd: Path, extra_env: dict[str, str] | None = None, timeout: int | None = None) -> dict:
    started = time.perf_counter()
    env = os.environ.copy()
    env.update(_go_env())
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False, env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        return {
            "name": name,
            "command": " ".join(command),
            "ok": False,
            "elapsed_ms": round(elapsed_ms, 3),
            "timeout_seconds": timeout,
            "stdout_tail": stdout[-1000:],
            "stderr_tail": stderr[-1000:],
        }
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "name": name,
        "command": " ".join(command),
        "ok": completed.returncode == 0,
        "elapsed_ms": round(elapsed_ms, 3),
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
    }


def _equity_values(size: int) -> list[float]:
    values: list[float] = []
    equity = 100.0
    for index in range(size):
        equity *= 1.0 + math.sin(index / 17.0) * 0.001
        if index % 911 == 0:
            equity *= 0.94
        values.append(equity)
    return values


def _python_max_drawdown(values: list[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)
    return max_drawdown


def _speedup_ratio(python_ms: float, rust_ms: float) -> float:
    if rust_ms <= 0:
        return float("inf")
    return python_ms / rust_ms


if __name__ == "__main__":
    raise SystemExit(main())
