from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_today
from app.models.entities import PaperAccount, PaperPerformanceSnapshot, PaperTrade, PaperTradeTag
from app.services.finance.performance_math import (
    annualized_sharpe_ratio,
    annualized_sortino_ratio,
    risk_free_rate_from_params,
)
from app.services.quant.runtime_parameters import get_backtest_execution


class PaperPerformanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def compute_overall(self, account_id: int, target_date: date | None = None) -> dict:
        account = self.db.get(PaperAccount, account_id)
        trades = self._filtered_trades(account_id, target_date)
        return_records = self._filtered_return_records(account_id, target_date)
        returns = [item.return_pct for item in return_records]
        daily_returns = self._daily_return_series(account_id, account, target_date) if account is not None else []
        risk_free_rate = risk_free_rate_from_params(get_backtest_execution())
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        total = len(returns)
        gross_gains = sum(wins)
        gross_losses = abs(sum(losses))
        directional_stats = _directional_return_stats(return_records)
        total_return_pct = 0.0
        max_drawdown_pct = 0.0
        if account is not None and float(account.initial_cash or 0) > 0:
            total_return_pct = (float(account.total_assets or 0) - float(account.initial_cash)) / float(account.initial_cash) * 100
            max_drawdown_pct = self._compute_equity_curve_drawdown(account_id, account, target_date)
        return_series = daily_returns or returns
        return {
            "total_return_pct": round(total_return_pct, 3),
            "max_drawdown_pct": max_drawdown_pct,
            "win_rate_pct": _rate(len(wins), total),
            "net_win_rate_pct": _rate(len(wins) - len(losses), total),
            "avg_trade_return_pct": round(sum(returns) / total, 3) if total else 0.0,
            "avg_win_pct": round(sum(wins) / len(wins), 3) if wins else 0.0,
            "avg_loss_pct": round(sum(losses) / len(losses), 3) if losses else 0.0,
            "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
            "long_win_rate_pct": directional_stats["long"]["win_rate_pct"],
            "long_profit_factor": directional_stats["long"]["profit_factor"],
            "long_win_loss_ratio": directional_stats["long"]["win_loss_ratio"],
            "short_win_rate_pct": directional_stats["short"]["win_rate_pct"],
            "short_profit_factor": directional_stats["short"]["profit_factor"],
            "short_win_loss_ratio": directional_stats["short"]["win_loss_ratio"],
            "directional_stats": directional_stats,
            "sharpe_ratio": round(_sharpe_ratio(return_series, risk_free_rate), 4),
            "sortino_ratio": round(_sortino_ratio(return_series, risk_free_rate), 4),
            "calmar_ratio": round(_calmar_ratio(total_return_pct, max_drawdown_pct, len(return_series)), 4),
            "risk_free_rate_annual_pct": round(risk_free_rate, 4),
            "stop_loss_rate_pct": 0.0,
            "total_trades": len(trades),
            "avg_hold_days": 0.0,
            "win_loss_ratio": round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)), 3) if wins and losses else None,
        }

    def compute_by_strategy(self, account_id: int, target_date: date | None = None) -> list[dict]:
        return self._grouped(account_id, "strategy_key", target_date=target_date)

    def compute_by_market_state(self, account_id: int, target_date: date | None = None) -> list[dict]:
        return self._grouped(account_id, "market_state", target_date=target_date)

    def compute_by_strategy_market_state(
        self,
        account_id: int,
        target_date: date | None = None,
        start_date: date | None = None,
    ) -> list[dict]:
        buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        for item in self._filtered_return_records(account_id, target_date, start_date=start_date):
            buckets[(item.strategy_key or "未分类", item.market_state or "未分类")].append(item.return_pct)
        result = []
        for (strategy_key, market_state), values in buckets.items():
            wins = [value for value in values if value > 0]
            losses = [value for value in values if value < 0]
            gross_gains = sum(wins)
            gross_losses = abs(sum(losses))
            result.append(
                {
                    "strategy_key": strategy_key,
                    "market_state": market_state,
                    "trades": len(values),
                    "win_rate_pct": _rate(len(wins), len(values)),
                    "net_win_rate_pct": _rate(len(wins) - len(losses), len(values)),
                    "avg_return_pct": round(sum(values) / max(len(values), 1), 3),
                    "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
                }
            )
        return sorted(result, key=lambda item: (item["strategy_key"], -item["trades"], item["market_state"]))

    def compute_by_tag(self, account_id: int, target_date: date | None = None) -> list[dict]:
        tag_map = self._trade_tag_map(account_id)
        buckets: dict[str, list[float]] = defaultdict(list)
        for item in self._filtered_return_records(account_id, target_date):
            for tag in tag_map.get(item.trade_id, []):
                buckets[tag].append(item.return_pct)
        result = []
        for tag, values in sorted(buckets.items()):
            wins = [value for value in values if value > 0]
            losses = [value for value in values if value < 0]
            result.append(
                {
                    "tag": tag,
                    "trades": len(values),
                    "win_rate_pct": _rate(len(wins), len(values)),
                    "net_win_rate_pct": _rate(len(wins) - len(losses), len(values)),
                    "avg_return_pct": round(sum(values) / max(len(values), 1), 3),
                    "total_return_pct": round(sum(values), 3),
                }
            )
        return result

    def compute_strategy_correlation(
        self,
        account_id: int,
        *,
        target_date: date | None = None,
        start_date: date | None = None,
    ) -> dict:
        records = self._filtered_return_records(account_id, target_date, start_date=start_date)
        returns_by_strategy_date: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
        all_dates: set[date] = set()
        for item in records:
            if item.trade_time is None:
                continue
            trade_date = item.trade_time.date()
            strategy_key = item.strategy_key or "未分类"
            returns_by_strategy_date[strategy_key][trade_date] += item.return_pct
            all_dates.add(trade_date)

        strategies = sorted(returns_by_strategy_date)
        dates = sorted(all_dates)
        series_by_strategy = {
            strategy: [returns_by_strategy_date[strategy].get(day, 0.0) for day in dates]
            for strategy in strategies
        }
        matrix: list[list[float | None]] = []
        rows: list[dict] = []
        for left in strategies:
            row_values: list[float | None] = []
            correlations: dict[str, float | None] = {}
            for right in strategies:
                value = _pearson(series_by_strategy[left], series_by_strategy[right])
                row_values.append(value)
                correlations[right] = value
            matrix.append(row_values)
            rows.append({"strategy_key": left, "correlations": correlations})

        notes: list[str] = []
        if len(strategies) < 2 or len(dates) < 2:
            notes.append("成交样本不足，暂不能形成稳定的策略相关性判断。")
        else:
            notes.append("相关性按每日已卖出交易收益聚合，未交易日期按 0 处理，用于组合集中度观察。")
        return {
            "strategies": strategies,
            "sample_days": len(dates),
            "matrix": matrix,
            "rows": rows,
            "notes": notes,
        }

    def compute_sector_etf_t0(self, account_id: int) -> dict:
        records = [
            item
            for item in self._filtered_return_records(account_id, None)
            if item.strategy_key == "sector_etf_t0"
        ]
        trades = [
            item
            for item in self._trades(account_id)
            if item.strategy_key == "sector_etf_t0"
        ]
        wins = [item.return_pct for item in records if item.return_pct > 0]
        losses = [item.return_pct for item in records if item.return_pct < 0]
        gross_gains = sum(wins)
        gross_losses = abs(sum(losses))
        return {
            "simulated_trades": len(trades),
            "simulated_closed_trades": len(records),
            "simulated_win_rate_pct": _rate(len(wins), len(records)),
            "simulated_net_win_rate_pct": _rate(len(wins) - len(losses), len(records)),
            "simulated_avg_return_pct": round(sum(item.return_pct for item in records) / max(len(records), 1), 3),
            "simulated_profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
            "notes": [
                "模拟成交绩效只统计 strategy_key=sector_etf_t0 的已闭合卖出收益。",
                "影子跟踪绩效来自 ETF T+0 机会池观察样本，用于和真实模拟成交对账。",
            ],
            "execution_gate_notes": [
                "自动执行门禁：ETF universe T+0 eligibility + 分钟信号 positive_t_buy + 无风险 flags + 置信度达标。",
                "Go/Rust 只参与读链路和指标加速，ETF 做T 信号和交易约束仍由 Python 主路径判断。",
                "反T卖出当前只展示研究信号，不自动卖出底仓。",
            ],
            "review_trades": self.sector_etf_t0_review_trades(account_id),
        }

    def sector_etf_t0_review_trades(self, account_id: int, limit: int = 20) -> list[dict]:
        trades = [
            item
            for item in reversed(self._trades(account_id))
            if item.strategy_key == "sector_etf_t0"
        ]
        result: list[dict] = []
        for trade in trades[: max(1, min(limit, 100))]:
            price = float(trade.price or 0)
            quantity = int(trade.quantity or 0)
            entry_reason = str(trade.entry_reason or "").strip()
            exit_reason = str(trade.exit_reason or "").strip()
            risk_notes: list[str] = []
            if not entry_reason and trade.side == "buy":
                risk_notes.append("缺少入场原因，无法完整复盘分钟信号与执行门禁。")
            if not exit_reason and trade.side == "sell":
                risk_notes.append("缺少退出原因，无法完整复盘止盈止损或回补原因。")
            if price <= 0 or quantity <= 0:
                risk_notes.append("成交价格或数量异常，需检查模拟盘账本。")
            result.append(
                {
                    "id": int(trade.id),
                    "order_id": int(trade.order_id),
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "price": price,
                    "quantity": quantity,
                    "trade_time": trade.trade_time,
                    "entry_reason": entry_reason,
                    "exit_reason": exit_reason,
                    "market_state": trade.market_state or "",
                    "attribution": _sector_etf_t0_attribution(trade),
                    "execution_summary": f"{trade.side} {quantity} @ {price:.4f}",
                    "risk_notes": risk_notes,
                }
            )
        return result

    def sell_return_records(self, account_id: int) -> list[SellReturnRecord]:
        return self._paired_sell_return_records(account_id)

    def create_daily_snapshot(
        self,
        account_id: int,
        *,
        target_date: date | None = None,
    ) -> PaperPerformanceSnapshot:
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")
        overall = self.compute_overall(account_id, target_date=target_date)
        snapshot_date = target_date or beijing_today()
        row = self.db.execute(
            select(PaperPerformanceSnapshot).where(
                PaperPerformanceSnapshot.account_id == account_id,
                PaperPerformanceSnapshot.snapshot_date == snapshot_date,
            )
        ).scalar_one_or_none()
        if row is None:
            row = PaperPerformanceSnapshot(account_id=account_id, snapshot_date=snapshot_date)
            self.db.add(row)
        row.total_assets = account.total_assets
        row.cumulative_return_pct = overall["total_return_pct"]
        row.max_drawdown_pct = overall["max_drawdown_pct"]
        row.win_rate_pct = overall["win_rate_pct"]
        row.net_win_rate_pct = overall["net_win_rate_pct"]
        row.profit_factor = overall["profit_factor"]
        row.stop_loss_rate_pct = overall["stop_loss_rate_pct"]
        row.trade_count = overall["total_trades"]
        self.db.commit()
        self.db.refresh(row)
        return row

    def _compute_equity_curve_drawdown(
        self,
        account_id: int,
        account: PaperAccount,
        target_date: date | None = None,
    ) -> float:
        statement = select(PaperPerformanceSnapshot).where(PaperPerformanceSnapshot.account_id == account_id)
        if target_date is not None:
            statement = statement.where(PaperPerformanceSnapshot.snapshot_date <= target_date)
        snapshots = self.db.execute(statement.order_by(PaperPerformanceSnapshot.snapshot_date.asc())).scalars().all()
        values = [float(item.total_assets or 0) for item in snapshots if float(item.total_assets or 0) > 0]
        if target_date is None or target_date >= beijing_today():
            current = float(account.total_assets or 0)
            if current > 0:
                values.append(current)
        if not values:
            return float(getattr(account, "max_drawdown_pct", 0.0) or 0.0)
        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            if peak > 0:
                max_drawdown = min(max_drawdown, (value - peak) / peak * 100)
        if target_date is None or target_date >= beijing_today():
            account.max_drawdown_pct = Decimal(str(round(max_drawdown, 4)))
            self.db.flush()
        return round(max_drawdown, 3)

    def _daily_return_series(
        self,
        account_id: int,
        account: PaperAccount,
        target_date: date | None = None,
    ) -> list[float]:
        statement = select(PaperPerformanceSnapshot).where(PaperPerformanceSnapshot.account_id == account_id)
        if target_date is not None:
            statement = statement.where(PaperPerformanceSnapshot.snapshot_date <= target_date)
        snapshots = self.db.execute(statement.order_by(PaperPerformanceSnapshot.snapshot_date.asc())).scalars().all()
        dated_values: list[tuple[date, float]] = [
            (item.snapshot_date, float(item.total_assets or 0))
            for item in snapshots
            if float(item.total_assets or 0) > 0
        ]
        if target_date is None or target_date >= beijing_today():
            current_assets = float(account.total_assets or 0)
            if current_assets > 0:
                current_date = beijing_today()
                if dated_values and dated_values[-1][0] == current_date:
                    dated_values[-1] = (current_date, current_assets)
                else:
                    dated_values.append((current_date, current_assets))
        values = [value for _, value in dated_values]
        return [
            (current - previous) / previous * 100
            for previous, current in zip(values, values[1:])
            if previous > 0
        ]

    def _grouped(self, account_id: int, field: str, target_date: date | None = None) -> list[dict]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for item in self._filtered_return_records(account_id, target_date):
            buckets[item.group_key(field)].append(item.return_pct)
        result = []
        for key, values in buckets.items():
            wins = [value for value in values if value > 0]
            losses = [value for value in values if value < 0]
            gross_gains = sum(wins)
            gross_losses = abs(sum(losses))
            result.append(
                {
                    "key": key,
                    "trades": len(values),
                    "win_rate_pct": _rate(len(wins), len(values)),
                    "net_win_rate_pct": _rate(len(wins) - len(losses), len(values)),
                    "avg_return_pct": round(sum(values) / max(len(values), 1), 3),
                    "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
                }
            )
        return result

    def _paired_sell_return_records(self, account_id: int) -> list[SellReturnRecord]:
        trades = self._trades(account_id)
        avg_cost_by_symbol: dict[str, Decimal] = {}
        qty_by_symbol: dict[str, int] = {}
        returns: list[SellReturnRecord] = []
        for trade in trades:
            qty = int(trade.quantity or 0)
            price = Decimal(str(trade.price or 0))
            if trade.side == "buy":
                old_qty = qty_by_symbol.get(trade.symbol, 0)
                old_cost = avg_cost_by_symbol.get(trade.symbol, Decimal("0"))
                total_qty = old_qty + qty
                avg_cost_by_symbol[trade.symbol] = ((old_cost * old_qty) + (price * qty)) / max(total_qty, 1)
                qty_by_symbol[trade.symbol] = total_qty
                continue
            cost = avg_cost_by_symbol.get(trade.symbol, Decimal("0"))
            if cost > 0:
                returns.append(
                    SellReturnRecord(
                        trade_id=trade.id,
                        return_pct=float((price - cost) / cost * 100),
                        strategy_key=trade.strategy_key or "未分类",
                        market_state=trade.market_state or "未分类",
                        trade_time=trade.trade_time,
                        direction="long",
                    )
                )
            qty_by_symbol[trade.symbol] = max(0, qty_by_symbol.get(trade.symbol, 0) - qty)
        return returns

    def _trades(self, account_id: int) -> list[PaperTrade]:
        return (
            self.db.execute(select(PaperTrade).where(PaperTrade.account_id == account_id).order_by(PaperTrade.trade_time.asc()))
            .scalars()
            .all()
        )

    def _filtered_return_records(
        self,
        account_id: int,
        target_date: date | None,
        *,
        start_date: date | None = None,
    ) -> list[SellReturnRecord]:
        records = self._paired_sell_return_records(account_id)
        if target_date is None:
            if start_date is None:
                return records
            return [item for item in records if item.trade_time and item.trade_time.date() >= start_date]
        return [item for item in records if item.trade_time and item.trade_time.date() == target_date]

    def _filtered_trades(self, account_id: int, target_date: date | None) -> list[PaperTrade]:
        trades = self._trades(account_id)
        if target_date is None:
            return trades
        return [item for item in trades if item.trade_time and item.trade_time.date() == target_date]

    def _trade_tag_map(self, account_id: int) -> dict[int, list[str]]:
        rows = (
            self.db.execute(
                select(PaperTradeTag).where(PaperTradeTag.account_id == account_id)
            )
            .scalars()
            .all()
        )
        mapping: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            mapping[int(row.trade_id)].append(row.tag)
        return mapping


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 3) if total > 0 else 0.0


def _sector_etf_t0_attribution(trade: PaperTrade) -> str:
    if trade.side == "buy":
        reason = str(trade.entry_reason or "").strip()
        return reason or "正T买入成交：需回看订单 signal_snapshot 确认分钟信号、ETF eligibility 和风控门禁。"
    if trade.side == "sell":
        reason = str(trade.exit_reason or "").strip()
        return reason or "ETF T0 卖出/回补成交：需回看退出原因确认止盈、止损或时间退出。"
    return "ETF T0 成交：需结合订单和持仓批次复盘。"


def _sharpe_ratio(returns: list[float], risk_free_rate_annual_pct: float) -> float:
    return annualized_sharpe_ratio(
        [value / 100.0 for value in returns],
        risk_free_rate_annual_pct=risk_free_rate_annual_pct,
    )


def _sortino_ratio(returns: list[float], risk_free_rate_annual_pct: float) -> float:
    return annualized_sortino_ratio(
        [value / 100.0 for value in returns],
        risk_free_rate_annual_pct=risk_free_rate_annual_pct,
    )


def _calmar_ratio(total_return_pct: float, max_drawdown_pct: float, periods: int) -> float:
    if periods <= 0 or max_drawdown_pct >= 0:
        return 0.0
    total_return = total_return_pct / 100
    if total_return <= -1:
        annualized_return_pct = -100.0
    else:
        annualized_return_pct = ((1 + total_return) ** (252 / periods) - 1) * 100
    return annualized_return_pct / abs(max_drawdown_pct)


def _directional_return_stats(records: list[SellReturnRecord]) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, list[float]] = {"long": [], "short": []}
    for record in records:
        key = "short" if record.direction == "short" else "long"
        grouped[key].append(record.return_pct)
    return {direction: _return_stats(values) for direction, values in grouped.items()}


def _return_stats(values: list[float]) -> dict[str, float | None]:
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_gains = sum(wins)
    gross_losses = abs(sum(losses))
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trade_count": len(values),
        "win_rate_pct": _rate(len(wins), len(values)),
        "profit_factor": round(gross_gains / gross_losses, 3) if gross_losses > 0 else None,
        "win_loss_ratio": round(avg_win / avg_loss, 3) if avg_win > 0 and avg_loss > 0 else None,
    }


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_var = sum((a - left_mean) ** 2 for a in left)
    right_var = sum((b - right_mean) ** 2 for b in right)
    denominator = (left_var * right_var) ** 0.5
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


@dataclass(frozen=True)
class SellReturnRecord:
    trade_id: int
    return_pct: float
    strategy_key: str
    market_state: str
    trade_time: datetime
    direction: str = "long"

    def group_key(self, field: str) -> str:
        if field == "strategy_key":
            return self.strategy_key or "未分类"
        if field == "market_state":
            return self.market_state or "未分类"
        return "未分类"
