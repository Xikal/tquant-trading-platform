from __future__ import annotations

import importlib
import importlib.machinery
import logging
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUST_TARGET_DIR = PROJECT_ROOT / "rust" / "tquant-rs" / "target" / "debug" / "deps"


def rust_max_drawdown(equity: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        return float(module.max_drawdown([float(value) for value in equity]))
    except Exception:
        logger.warning("rust max_drawdown failed; falling back to python", exc_info=True)
        return None


def rust_rolling_mean(values: Sequence[float], window: int) -> list[float] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        return [float(value) for value in module.rolling_mean([float(value) for value in values], int(window))]
    except Exception:
        logger.warning("rust rolling_mean failed; falling back to python", exc_info=True)
        return None


def rust_atr_wilder(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        return [
            float(value)
            for value in module.atr_wilder(
                [float(value) for value in highs],
                [float(value) for value in lows],
                [float(value) for value in closes],
                int(period),
            )
        ]
    except Exception:
        logger.warning("rust atr_wilder failed; falling back to python", exc_info=True)
        return None


def rust_available() -> bool:
    return _load_rust_module() is not None


def _load_rust_module():
    if not get_settings().rust_finance_math_enabled:
        return None
    try:
        return importlib.import_module("tquant_rs")
    except Exception:
        module = _load_local_rust_module()
        if module is not None:
            return module
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
