from __future__ import annotations

import importlib
import importlib.machinery
import logging
import math
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from threading import Lock

from app.core.config import get_settings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUST_TARGET_DIR = PROJECT_ROOT / "rust" / "tquant-rs" / "target" / "debug" / "deps"
_METRICS_LOCK = Lock()
_METRICS: dict[str, int] = {
    "hits": 0,
    "fallbacks": 0,
    "disabled": 0,
    "errors": 0,
}


def rust_max_drawdown(equity: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        values = _finite_float_list(equity)
        value = float(module.max_drawdown(values))
        _increment("hits")
        return value
    except Exception:
        _increment("errors")
        logger.warning("rust max_drawdown failed; falling back to python", exc_info=True)
        return None


def rust_rolling_mean(values: Sequence[float], window: int) -> list[float | None] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        cleaned = _float_list_or_none(values)
        if cleaned is None:
            return None
        value = _optional_float_list(module.rolling_mean(cleaned, int(window)))
        _increment("hits")
        return value
    except Exception:
        _increment("errors")
        logger.warning("rust rolling_mean failed; falling back to python", exc_info=True)
        return None


def rust_atr_wilder(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        high_values = _float_list_or_none(highs)
        low_values = _float_list_or_none(lows)
        close_values = _float_list_or_none(closes)
        if high_values is None or low_values is None or close_values is None:
            return None
        value = _optional_float_list(
            module.atr_wilder(
                high_values,
                low_values,
                close_values,
                int(period),
            )
        )
        _increment("hits")
        return value
    except Exception:
        _increment("errors")
        logger.warning("rust atr_wilder failed; falling back to python", exc_info=True)
        return None


def rust_rsi_wilder(values: Sequence[float], period: int) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        cleaned = _float_list_or_none(values)
        if cleaned is None:
            return None
        value = module.rsi_wilder(cleaned, int(period))
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust rsi_wilder failed; falling back to python", exc_info=True)
        return None


def rust_vwap(prices: Sequence[float], volumes: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        pairs = _finite_pairs(prices, volumes)
        if not pairs:
            return None
        value = module.vwap([item[0] for item in pairs], [item[1] for item in pairs])
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust vwap failed; falling back to python", exc_info=True)
        return None


def rust_rank_ic(factors: Sequence[float], returns: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        pairs = _finite_pairs(factors, returns)
        if len(pairs) < 2:
            return None
        value = module.rank_ic([item[0] for item in pairs], [item[1] for item in pairs])
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust rank_ic failed; falling back to python", exc_info=True)
        return None


def rust_available() -> bool:
    return _load_rust_module() is not None


def rust_math_metrics_snapshot() -> dict[str, int]:
    with _METRICS_LOCK:
        return dict(_METRICS)


def _optional_float_list(values: Sequence[object]) -> list[float | None]:
    return [None if value is None else float(value) for value in values]


def _finite_float_list(values: Sequence[object]) -> list[float]:
    result: list[float] = []
    for item in values:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            result.append(value)
    return result


def _float_list_or_none(values: Sequence[object]) -> list[float] | None:
    result: list[float] = []
    for item in values:
        try:
            value = float(item)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        result.append(value)
    return result


def _finite_pairs(left: Sequence[object], right: Sequence[object]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for left_item, right_item in zip(left, right):
        try:
            left_value = float(left_item)
            right_value = float(right_item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(left_value) and math.isfinite(right_value):
            pairs.append((left_value, right_value))
    return pairs


def _load_rust_module():
    if not get_settings().rust_finance_math_enabled:
        _increment("disabled")
        return None
    try:
        return importlib.import_module("tquant_rs")
    except Exception:
        module = _load_local_rust_module() if os.getenv("TQUANT_RUST_MATH_LOCAL_IMPORT") == "1" else None
        if module is not None:
            return module
        _increment("fallbacks")
        logger.info("optional rust finance module is not available", exc_info=True)
        return None


def _load_local_rust_module():
    suffixes = importlib.machinery.EXTENSION_SUFFIXES
    candidates = [
        RUST_TARGET_DIR / f"libtquant_rs{suffix}" for suffix in suffixes
    ] + [
        RUST_TARGET_DIR / "libtquant_rs.dylib",
        RUST_TARGET_DIR / "libtquant_rs.so",
    ]
    module_path = next((path for path in candidates if path.exists()), None)
    if module_path is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        link_suffix = next((suffix for suffix in suffixes if suffix.startswith(".abi3")), suffixes[0])
        link_path = Path(tmp) / f"tquant_rs{link_suffix}"
        os.symlink(module_path, link_path)
        sys.path.insert(0, tmp)
        try:
            return importlib.import_module("tquant_rs")
        except Exception:
            logger.info("local rust finance module import failed", exc_info=True)
            return None
        finally:
            if sys.path and sys.path[0] == tmp:
                sys.path.pop(0)


def _increment(key: str) -> None:
    with _METRICS_LOCK:
        _METRICS[key] = int(_METRICS.get(key, 0)) + 1
