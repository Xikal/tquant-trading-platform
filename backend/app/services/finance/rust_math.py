from __future__ import annotations

import importlib
import importlib.machinery
import logging
import os
import sys
import tempfile
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from threading import Lock

from app.core.config import get_settings
from app.services.finance import rust_math_fallbacks as fallback

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUST_TARGET_DIR = PROJECT_ROOT / "rust" / "tquant-rs" / "target" / "debug" / "deps"
_METRICS_LOCK = Lock()
_METRICS: dict[str, int] = {
    "hits": 0,
    "fallbacks": 0,
    "disabled": 0,
    "errors": 0,
    "cache_hits": 0,
    "cache_misses": 0,
}
_DERIVED_CACHE_LOCK = Lock()
_DERIVED_CACHE_MAX_SIZE = 512
_DERIVED_CACHE_MAX_INPUT_POINTS = 512
_DERIVED_CACHE: OrderedDict[tuple[object, ...], object] = OrderedDict()
_CACHE_MISS = object()
_UNCACHEABLE = object()


def max_drawdown(equity: Sequence[float]) -> float:
    return _cached(
        _cache_key(_cache_scope(), "max_drawdown", _finite_tuple(equity)),
        lambda: _rust_or_python(lambda: rust_max_drawdown(equity), lambda: fallback.max_drawdown(equity)),
    )


def rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    return _cached(
        _cache_key(_cache_scope(), "rolling_mean", int(window), _strict_tuple(values)),
        lambda: _rust_or_python(lambda: rust_rolling_mean(values, window), lambda: fallback.rolling_mean(values, window)),
    )


def rolling_std(values: Sequence[float], window: int) -> list[float | None]:
    return _cached(
        _cache_key(_cache_scope(), "rolling_std", int(window), _strict_tuple(values)),
        lambda: _rust_or_python(lambda: rust_rolling_std(values, window), lambda: fallback.rolling_std(values, window)),
    )


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    return _cached(
        _cache_key(
            _cache_scope(),
            "atr",
            int(period),
            _strict_tuple(highs),
            _strict_tuple(lows),
            _strict_tuple(closes),
        ),
        lambda: _rust_or_python(
            lambda: rust_atr_wilder(highs, lows, closes, period),
            lambda: fallback.atr_wilder(highs, lows, closes, period),
        ),
    )


def rsi_wilder(values: Sequence[float], period: int) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "rsi_wilder", int(period), _strict_tuple(values)),
        lambda: _rust_or_python(lambda: rust_rsi_wilder(values, period), lambda: fallback.rsi_wilder(values, period)),
    )


def vwap(prices: Sequence[float], volumes: Sequence[float]) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "vwap", _finite_pair_tuple(prices, volumes)),
        lambda: _rust_or_python(lambda: rust_vwap(prices, volumes), lambda: fallback.vwap(prices, volumes)),
    )


def bollinger_bands(
    values: Sequence[float],
    window: int,
    num_std: float = 2.0,
) -> list[tuple[float, float, float] | None]:
    return _cached(
        _cache_key(_cache_scope(), "bollinger_bands", int(window), float(num_std), _strict_tuple(values)),
        lambda: _rust_or_python(
            lambda: rust_bollinger_bands(values, window, num_std),
            lambda: fallback.bollinger_bands(values, window, num_std),
        ),
    )


def beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "beta", _finite_pair_tuple(asset_returns, benchmark_returns)),
        lambda: _rust_or_python(
            lambda: rust_beta(asset_returns, benchmark_returns),
            lambda: fallback.beta(asset_returns, benchmark_returns),
        ),
    )


def correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "correlation", _finite_pair_tuple(left, right)),
        lambda: _rust_or_python(lambda: rust_correlation(left, right), lambda: fallback.correlation(left, right)),
    )


def rank_ic(factors: Sequence[float], returns: Sequence[float]) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "rank_ic", _finite_pair_tuple(factors, returns)),
        lambda: _rust_or_python(lambda: rust_rank_ic(factors, returns), lambda: fallback.rank_ic(factors, returns)),
    )


def volatility(returns: Sequence[float], periods_per_year: float = 252.0) -> float | None:
    return _cached(
        _cache_key(_cache_scope(), "volatility", float(periods_per_year), _strict_tuple(returns)),
        lambda: _rust_or_python(
            lambda: rust_volatility(returns, periods_per_year),
            lambda: fallback.volatility(returns, periods_per_year),
        ),
    )


def rust_max_drawdown(equity: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        values = fallback.finite_float_list(equity)
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
        cleaned = fallback.float_list_or_none(values)
        if cleaned is None:
            return None
        value = fallback.optional_float_list(module.rolling_mean(cleaned, int(window)))
        _increment("hits")
        return value
    except Exception:
        _increment("errors")
        logger.warning("rust rolling_mean failed; falling back to python", exc_info=True)
        return None


def rust_rolling_std(values: Sequence[float], window: int) -> list[float | None] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        cleaned = fallback.float_list_or_none(values)
        if cleaned is None:
            return None
        value = fallback.optional_float_list(module.rolling_std(cleaned, int(window)))
        _increment("hits")
        return value
    except Exception:
        _increment("errors")
        logger.warning("rust rolling_std failed; falling back to python", exc_info=True)
        return None


def rust_volatility(returns: Sequence[float], periods_per_year: float = 252.0) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        cleaned = fallback.float_list_or_none(returns)
        if cleaned is None:
            return None
        value = module.volatility(cleaned, float(periods_per_year))
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust volatility failed; falling back to python", exc_info=True)
        return None


def rust_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        pairs = fallback.finite_pairs(left, right)
        if len(pairs) < 2:
            return None
        value = module.correlation([item[0] for item in pairs], [item[1] for item in pairs])
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust correlation failed; falling back to python", exc_info=True)
        return None


def rust_beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        pairs = fallback.finite_pairs(asset_returns, benchmark_returns)
        if len(pairs) < 2:
            return None
        value = module.beta([item[0] for item in pairs], [item[1] for item in pairs])
        _increment("hits")
        return None if value is None else float(value)
    except Exception:
        _increment("errors")
        logger.warning("rust beta failed; falling back to python", exc_info=True)
        return None


def rust_bollinger_bands(
    values: Sequence[float],
    window: int,
    num_std: float = 2.0,
) -> list[tuple[float, float, float] | None] | None:
    module = _load_rust_module()
    if module is None:
        return None
    try:
        cleaned = fallback.float_list_or_none(values)
        if cleaned is None:
            return None
        raw_values = module.bollinger_bands(cleaned, int(window), float(num_std))
        result: list[tuple[float, float, float] | None] = []
        for item in raw_values:
            if item is None:
                result.append(None)
                continue
            upper, middle, lower = item
            result.append((float(upper), float(middle), float(lower)))
        _increment("hits")
        return result
    except Exception:
        _increment("errors")
        logger.warning("rust bollinger_bands failed; falling back to python", exc_info=True)
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
        high_values = fallback.float_list_or_none(highs)
        low_values = fallback.float_list_or_none(lows)
        close_values = fallback.float_list_or_none(closes)
        if high_values is None or low_values is None or close_values is None:
            return None
        value = fallback.optional_float_list(
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
        cleaned = fallback.float_list_or_none(values)
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
        pairs = fallback.finite_pairs(prices, volumes)
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
        pairs = fallback.finite_pairs(factors, returns)
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
        snapshot = dict(_METRICS)
    with _DERIVED_CACHE_LOCK:
        snapshot["cache_size"] = len(_DERIVED_CACHE)
    fallback_total = snapshot.get("fallbacks", 0) + snapshot.get("disabled", 0) + snapshot.get("errors", 0)
    total = snapshot.get("hits", 0) + fallback_total
    snapshot["fallback_ratio_bps"] = int(round(fallback_total / total * 10000)) if total else 0
    return snapshot


def _rust_or_python(rust_loader, python_loader):  # noqa: ANN001
    rust_value = rust_loader()
    if rust_value is not None:
        return rust_value
    return python_loader()


def _cached(key: tuple[object, ...] | None, loader):  # noqa: ANN001
    if key is None:
        return loader()
    with _DERIVED_CACHE_LOCK:
        if key in _DERIVED_CACHE:
            value = _DERIVED_CACHE.pop(key)
            _DERIVED_CACHE[key] = value
        else:
            value = _CACHE_MISS
    if value is not _CACHE_MISS:
        _increment("cache_hits")
        return _cache_value_copy(value)
    _increment("cache_misses")
    value = loader()
    with _DERIVED_CACHE_LOCK:
        _DERIVED_CACHE[key] = _cache_value_copy(value)
        while len(_DERIVED_CACHE) > _DERIVED_CACHE_MAX_SIZE:
            _DERIVED_CACHE.popitem(last=False)
    return value


def _cache_value_copy(value):  # noqa: ANN001
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _cache_scope() -> bool:
    return bool(get_settings().rust_finance_math_enabled)


def _cache_key(*parts: object) -> tuple[object, ...] | None:
    if any(part is _UNCACHEABLE for part in parts):
        return None
    return tuple(parts)


def _strict_tuple(values: Sequence[object]) -> tuple[object, ...] | object:
    if not _cacheable_lengths(values):
        return _UNCACHEABLE
    cleaned = fallback.float_list_or_none(values)
    if cleaned is None:
        return ("invalid", len(values), tuple(str(item) for item in values))
    return tuple(cleaned)


def _finite_tuple(values: Sequence[object]) -> tuple[float, ...] | object:
    if not _cacheable_lengths(values):
        return _UNCACHEABLE
    return tuple(fallback.finite_float_list(values))


def _finite_pair_tuple(left: Sequence[object], right: Sequence[object]) -> tuple[tuple[float, float], ...] | object:
    if not _cacheable_lengths(left, right):
        return _UNCACHEABLE
    return tuple(fallback.finite_pairs(left, right))


def _cacheable_lengths(*series: Sequence[object]) -> bool:
    total = 0
    for values in series:
        try:
            length = len(values)
        except TypeError:
            return False
        total += max(int(length), 0)
        if total > _DERIVED_CACHE_MAX_INPUT_POINTS:
            return False
    return True


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
