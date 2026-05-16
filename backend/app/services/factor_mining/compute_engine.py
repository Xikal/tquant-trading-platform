from __future__ import annotations

import ast
import math
import time
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


class FactorComputeEngine:
    """Restricted Python factor executor.

    Generated code must define ``compute_factor(bars: pd.DataFrame) -> pd.Series``.
    ``bars`` is one symbol's point-in-time ordered history, so rolling windows
    cannot accidentally read future rows.
    """

    def __init__(self, *, timeout_seconds: float = 30.0, max_rows: int = 2_000_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows

    def validate(self, formula_code: str) -> None:
        tree = ast.parse(formula_code)
        for node in ast.walk(tree):
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

    def compute(self, formula_code: str, bars: pd.DataFrame) -> FactorComputeResult:
        self.validate(formula_code)
        if len(bars) > self.max_rows:
            raise FactorSafetyError("因子计算数据量超过安全上限")
        namespace = self._compile_namespace(formula_code)
        compute_factor = namespace.get("compute_factor")
        if not callable(compute_factor):
            raise FactorSafetyError("公式必须定义 compute_factor(bars)")
        started = time.monotonic()
        frames: list[pd.DataFrame] = []
        for symbol, group in bars.sort_values(["symbol", "trade_date"]).groupby("symbol", sort=False):
            if time.monotonic() - started > self.timeout_seconds:
                raise TimeoutError("因子计算超时")
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
        if not frames:
            return FactorComputeResult(pd.DataFrame(), time.monotonic() - started)
        return FactorComputeResult(pd.concat(frames, ignore_index=True), time.monotonic() - started)

    def _compile_namespace(self, formula_code: str) -> dict[str, Any]:
        safe_globals = {
            "__builtins__": {"abs": abs, "max": max, "min": min, "round": round, "float": float, "len": len},
            "np": np,
            "pd": pd,
            "math": math,
        }
        namespace: dict[str, Any] = {}
        exec(compile(formula_code, "<factor_code>", "exec"), safe_globals, namespace)
        return namespace


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""
