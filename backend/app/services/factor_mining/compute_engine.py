from __future__ import annotations

import ast
import atexit
import inspect
import math
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


class FactorSafetyError(ValueError):
    pass


@dataclass(frozen=True)
class FactorComputeResult:
    values: pd.DataFrame
    elapsed_seconds: float


_DENIED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ClassDef,
    ast.Lambda,
)
_DENIED_CALLS = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "breakpoint",
    "globals",
    "locals",
    "vars",
}
_DENIED_ATTRS = {
    "system",
    "popen",
    "remove",
    "unlink",
    "rmdir",
    "mkdir",
    "makedirs",
    "rename",
    "replace",
    "read",
    "write",
    "connect",
    "request",
    "urlopen",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sql",
    "read_stata",
    "read_table",
    "to_csv",
    "to_excel",
    "to_feather",
    "to_hdf",
    "to_json",
    "to_orc",
    "to_parquet",
    "to_pickle",
    "to_sql",
}
_PROCESS_POOL: ProcessPoolExecutor | None = None
_PROCESS_POOL_WORKERS = 0
_SANDBOX_MEMORY_BYTES = 512 * 1024 * 1024


class FactorComputeEngine:
    """Restricted Python factor executor.

    Generated code must define ``compute_factor(bars: pd.DataFrame) -> pd.Series``.
    ``bars`` is one symbol's point-in-time ordered history, so rolling windows
    cannot accidentally read future rows.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_rows: int = 2_000_000,
        parallel_workers: int = 4,
        parallel_symbol_threshold: int = 50,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows
        self.parallel_workers = max(0, int(parallel_workers))
        self.parallel_symbol_threshold = max(1, int(parallel_symbol_threshold))

    def validate(self, formula_code: str) -> None:
        tree = ast.parse(formula_code)
        _validate_module_body(tree)
        has_compute_factor = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "compute_factor":
                has_compute_factor = True
            if isinstance(node, _DENIED_NODES):
                raise FactorSafetyError(f"不允许的语法: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise FactorSafetyError("不允许访问双下划线名称")
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("__") or node.attr in _DENIED_ATTRS:
                    raise FactorSafetyError(f"不允许访问属性: {node.attr}")
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in _DENIED_CALLS:
                    raise FactorSafetyError(f"不允许调用: {name}")
        if not has_compute_factor:
            raise FactorSafetyError("公式必须定义 compute_factor(bars)")

    def compute(self, formula_code: str, bars: pd.DataFrame) -> FactorComputeResult:
        self.validate(formula_code)
        if len(bars) > self.max_rows:
            raise FactorSafetyError("因子计算数据量超过安全上限")
        started = time.monotonic()
        ordered = bars.sort_values(["symbol", "trade_date"])
        symbols = [str(item) for item in ordered["symbol"].drop_duplicates().tolist()]
        if self.parallel_workers <= 0:
            return FactorComputeResult(_compute_factor_batch(formula_code, ordered, apply_limits=False), time.monotonic() - started)
        return self._compute_parallel(formula_code, ordered, symbols, started)

    def _compute_parallel(
        self,
        formula_code: str,
        ordered: pd.DataFrame,
        symbols: list[str],
        started: float,
    ) -> FactorComputeResult:
        frames: list[pd.DataFrame] = []
        worker_count = self.parallel_workers if len(symbols) >= self.parallel_symbol_threshold else 1
        chunk_size = max(1, math.ceil(len(symbols) / worker_count))
        symbol_chunks = [symbols[index : index + chunk_size] for index in range(0, len(symbols), chunk_size)]
        pool = _get_process_pool(worker_count)
        futures = [
            pool.submit(
                _compute_factor_batch,
                formula_code,
                ordered[ordered["symbol"].isin(chunk)].copy(),
            )
            for chunk in symbol_chunks
        ]
        for future in as_completed(futures, timeout=self.timeout_seconds):
            if time.monotonic() - started > self.timeout_seconds:
                raise TimeoutError("因子计算超时")
            frames.append(future.result())
        if not frames:
            return FactorComputeResult(pd.DataFrame(), time.monotonic() - started)
        return FactorComputeResult(pd.concat(frames, ignore_index=True), time.monotonic() - started)

    @staticmethod
    def _compile_namespace(formula_code: str) -> dict[str, Any]:
        return _compile_namespace(formula_code)


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _validate_module_body(tree: ast.Module) -> None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "compute_factor":
            continue
        if isinstance(node, ast.Assign) and all(isinstance(target, ast.Name) and target.id.isupper() for target in node.targets):
            if _is_literal_constant(node.value):
                continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        raise FactorSafetyError("公式只允许在顶层定义 compute_factor 和常量")


def _is_literal_constant(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str, bool, type(None))):
        return True
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_is_literal_constant(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_literal_constant(key)) and _is_literal_constant(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _compute_factor_batch(formula_code: str, bars: pd.DataFrame, *, apply_limits: bool = True) -> pd.DataFrame:
    if apply_limits:
        _apply_resource_limits()
    namespace = _compile_namespace(formula_code)
    compute_factor = namespace.get("compute_factor")
    if not callable(compute_factor):
        raise FactorSafetyError("公式必须定义 compute_factor(bars)")
    frames: list[pd.DataFrame] = []
    for symbol, group in bars.groupby("symbol", sort=False):
        series = compute_factor(group.copy())
        if not isinstance(series, pd.Series):
            raise FactorSafetyError("compute_factor 必须返回 pd.Series")
        values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
        frames.append(
            pd.DataFrame(
                {
                    "symbol": str(symbol),
                    "trade_date": group["trade_date"].to_numpy(),
                    "factor_value": values.reindex(group.index).to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _compile_namespace(formula_code: str) -> dict[str, Any]:
    safe_globals = {
        "__builtins__": {"abs": abs, "max": max, "min": min, "round": round, "float": float, "len": len},
        "np": np,
        "pd": pd,
        "math": math,
    }
    namespace: dict[str, Any] = {}
    exec(compile(formula_code, "<factor_code>", "exec"), safe_globals, namespace)
    return namespace


def _get_process_pool(max_workers: int) -> ProcessPoolExecutor:
    global _PROCESS_POOL, _PROCESS_POOL_WORKERS
    workers = max(1, int(max_workers or 1))
    if _PROCESS_POOL is not None and _PROCESS_POOL_WORKERS == workers:
        return _PROCESS_POOL
    if _PROCESS_POOL is not None:
        _PROCESS_POOL.shutdown(wait=False, cancel_futures=True)
    kwargs: dict[str, Any] = {"max_workers": workers, "initializer": _apply_resource_limits}
    if "max_tasks_per_child" in inspect.signature(ProcessPoolExecutor).parameters:
        kwargs["max_tasks_per_child"] = 100
    _PROCESS_POOL = ProcessPoolExecutor(**kwargs)
    _PROCESS_POOL_WORKERS = workers
    return _PROCESS_POOL


def _apply_resource_limits() -> None:
    if platform.system().lower() == "darwin":
        return
    try:
        import resource

        hard = resource.getrlimit(resource.RLIMIT_AS)[1]
        limit = _SANDBOX_MEMORY_BYTES if hard < 0 else min(_SANDBOX_MEMORY_BYTES, int(hard))
        resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
    except Exception:
        return


def _shutdown_process_pool() -> None:
    global _PROCESS_POOL
    if _PROCESS_POOL is not None:
        _PROCESS_POOL.shutdown(wait=False, cancel_futures=True)
        _PROCESS_POOL = None


atexit.register(_shutdown_process_pool)
