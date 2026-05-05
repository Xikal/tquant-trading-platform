from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from app.services.backtest.data_provider import BacktestSignal, DailyBar, DataQualityReport


ATTRIBUTION_VERSION = "backtest-attribution-v1"

_INDUSTRY_KEYS = ("sector_name", "industry", "industry_name", "sector", "sector_label")
_MARKET_STATE_KEYS = ("market_state", "market_state_category", "market_regime", "regime")


@dataclass
class _SignalContext:
    symbol: str
    strategy_key: str
    industry: str
    market_state: str
    data_quality: str


@dataclass
class _BucketStats:
    bucket: str
    signal_count: int = 0
    filled_order_count: int = 0
    rejected_order_count: int = 0
    trade_count: int = 0
    win_count: int = 0
    net_pnl: float = 0.0
    fee_amount: float = 0.0
    return_sum_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        avg_return = self.return_sum_pct / self.trade_count if self.trade_count else 0.0
        win_rate = self.win_count / self.trade_count * 100 if self.trade_count else 0.0
        return {
            "bucket": self.bucket,
            "label": self.bucket,
            "signal_count": self.signal_count,
            "filled_order_count": self.filled_order_count,
            "rejected_order_count": self.rejected_order_count,
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "win_rate_pct": round(win_rate, 2),
            "avg_return_pct": round(avg_return, 2),
            "net_pnl": round(self.net_pnl, 2),
            "fee_amount": round(self.fee_amount, 2),
        }


def build_backtest_attribution(
    *,
    signals: Iterable[BacktestSignal],
    histories: dict[str, list[DailyBar]],
    trade_dates: list[str],
    data_quality: DataQualityReport,
    orders: Iterable[Any],
    trades: Iterable[Any],
) -> dict[str, Any]:
    signal_list = list(signals)
    contexts = _build_signal_contexts(
        signals=signal_list,
        histories=histories,
        trade_dates=trade_dates,
        data_quality=data_quality,
    )
    dimensions: dict[str, dict[str, _BucketStats]] = {
        "industry": {},
        "market_state": {},
        "data_quality": {},
    }

    for context in contexts:
        _touch(dimensions["industry"], context.industry).signal_count += 1
        _touch(dimensions["market_state"], context.market_state).signal_count += 1
        _touch(dimensions["data_quality"], context.data_quality).signal_count += 1

    for order in orders:
        if str(getattr(order, "side", "") or "").lower() != "buy":
            continue
        context = _resolve_context(contexts, getattr(order, "symbol", ""), getattr(order, "strategy_key", ""))
        if context is None:
            continue
        status = str(getattr(order, "status", "") or "").lower()
        for bucket in _context_buckets(dimensions, context):
            if status == "filled":
                bucket.filled_order_count += 1
            elif status == "rejected":
                bucket.rejected_order_count += 1

    for trade in trades:
        context = _resolve_context(contexts, getattr(trade, "symbol", ""), getattr(trade, "strategy_key", ""))
        if context is None:
            continue
        for bucket in _context_buckets(dimensions, context):
            bucket.trade_count += 1
            net_pnl = _float(getattr(trade, "net_pnl", 0.0))
            bucket.net_pnl += net_pnl
            bucket.fee_amount += _float(getattr(trade, "fee_amount", 0.0))
            return_pct = _float(getattr(trade, "return_pct", 0.0))
            bucket.return_sum_pct += return_pct
            if net_pnl > 0:
                bucket.win_count += 1

    return {
        "version": ATTRIBUTION_VERSION,
        "industry": _sorted_buckets(dimensions["industry"]),
        "market_state": _sorted_buckets(dimensions["market_state"]),
        "data_quality": _sorted_buckets(dimensions["data_quality"]),
        "data_quality_summary": _quality_summary(data_quality),
        "notes": [
            "行业和市场状态来自 BacktestSignal.metadata，未标注时归入“未分类/未标注”。",
            "数据质量桶基于本次回测已加载日线和 DataQualityReport 生成，不依赖外部数据源。",
        ],
    }


def _build_signal_contexts(
    *,
    signals: list[BacktestSignal],
    histories: dict[str, list[DailyBar]],
    trade_dates: list[str],
    data_quality: DataQualityReport,
) -> list[_SignalContext]:
    return [
        _SignalContext(
            symbol=signal.symbol,
            strategy_key=signal.strategy_key,
            industry=_metadata_label(signal.metadata, _INDUSTRY_KEYS, default="未分类"),
            market_state=_metadata_label(signal.metadata, _MARKET_STATE_KEYS, default="未标注"),
            data_quality=_symbol_quality(signal.symbol, histories.get(signal.symbol, []), trade_dates, data_quality),
        )
        for signal in signals
    ]


def _metadata_label(payload: dict[str, Any], keys: tuple[str, ...], *, default: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _symbol_quality(
    symbol: str,
    bars: list[DailyBar],
    trade_dates: list[str],
    data_quality: DataQualityReport,
) -> str:
    if not bars:
        return "missing_symbol"
    expected_dates = set(trade_dates)
    actual_dates = {bar.trade_date for bar in bars}
    if any(not bar.is_valid for bar in bars):
        return "invalid_bar"
    if any(bar.is_suspended for bar in bars):
        return "suspended_bar"
    if expected_dates - actual_dates:
        return "missing_bar"
    return data_quality.quality_tag if data_quality.quality_tag == "blocked" else "ok"


def _resolve_context(contexts: list[_SignalContext], symbol: str, strategy_key: str) -> _SignalContext | None:
    for context in contexts:
        if context.symbol == symbol and context.strategy_key == strategy_key:
            return context
    for context in contexts:
        if context.symbol == symbol:
            return context
    return None


def _context_buckets(
    dimensions: dict[str, dict[str, _BucketStats]],
    context: _SignalContext,
) -> list[_BucketStats]:
    return [
        _touch(dimensions["industry"], context.industry),
        _touch(dimensions["market_state"], context.market_state),
        _touch(dimensions["data_quality"], context.data_quality),
    ]


def _touch(target: dict[str, _BucketStats], bucket: str) -> _BucketStats:
    label = bucket or "未分类"
    item = target.get(label)
    if item is None:
        item = _BucketStats(bucket=label)
        target[label] = item
    return item


def _sorted_buckets(target: dict[str, _BucketStats]) -> list[dict[str, Any]]:
    buckets = [item.to_dict() for item in target.values()]
    return sorted(
        buckets,
        key=lambda item: (
            item["net_pnl"],
            item["win_rate_pct"],
            item["trade_count"],
            item["signal_count"],
            item["bucket"],
        ),
        reverse=True,
    )


def _quality_summary(data_quality: DataQualityReport) -> dict[str, Any]:
    payload = asdict(data_quality)
    payload["issue_count"] = sum(
        int(payload.get(key) or 0)
        for key in (
            "missing_symbol_count",
            "missing_bar_count",
            "invalid_bar_count",
            "suspended_bar_count",
        )
    )
    return payload


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
