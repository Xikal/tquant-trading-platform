from __future__ import annotations

from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyExecutionBacktestResponse,
)
from app.repositories.low_buy import DailyHistoryRepository, LowBuyResultRepository
from app.services.low_buy.execution_simulation import (
    bars_from_repository_rows,
    simulate_candidate_execution,
    simulate_liquidity_crisis,
)
from app.services.low_buy.data_quality import DataQualitySnapshot, data_quality_payload
from app.services.low_buy.risk_metrics import _compute_sharpe_from_returns, compute_pbo
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY, Session


class LowBuyExecutionBacktestMixin:
    def execution_backtest(
        self,
        db: Session,
        *,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        lookback_days: int = 60,
        limit: int = 200,
    ) -> LowBuyExecutionBacktestResponse:
        candidates = self._load_backtest_candidates(
            db=db,
            strategy=strategy,
            lookback_days=lookback_days,
            limit=limit,
        )
        rows_by_symbol = {
            symbol: bars_from_repository_rows(rows)
            for symbol, rows in _load_future_daily_rows(db=db, candidates=candidates).items()
        }
        items = [
            simulate_candidate_execution(
                candidate=candidate,
                rows=rows_by_symbol.get(candidate.symbol, []),
            )
            for candidate in candidates
        ]
        diagnostics = _backtest_diagnostic_notes(candidates)
        return _build_backtest_response(
            strategy=strategy,
            lookback_days=lookback_days,
            items=items,
            extra_notes=diagnostics,
        )

    def _load_backtest_candidates(
        self,
        db: Session,
        *,
        strategy: str,
        lookback_days: int,
        limit: int,
    ) -> list[LowBuyCandidateOut]:
        repository = LowBuyResultRepository(db)
        summaries = repository.fetch_recent_scan_summaries(strategy_key=strategy, limit=lookback_days)
        trade_dates = [str(summary.latest_trade_date) for summary in summaries]
        rows = repository.fetch_confirmed_results_for_dates(
            latest_trade_dates=trade_dates,
            strategy_key=strategy,
            limit_per_date=999,
        )
        candidates: list[LowBuyCandidateOut] = []
        for row in rows:
            if not self._candidate_payload_is_current(row.payload_json):
                continue
            try:
                candidates.append(LowBuyCandidateOut.model_validate_json(row.payload_json))
            except Exception:
                continue
        candidates.sort(key=lambda item: (item.confirmed_trade_date or item.quote_timestamp, item.score), reverse=True)
        return candidates[:limit]


def _load_future_daily_rows(
    *,
    db: Session,
    candidates: list[LowBuyCandidateOut],
) -> dict[str, list]:
    if not candidates:
        return {}
    signal_dates = [
        candidate.confirmed_trade_date or candidate.quote_timestamp
        for candidate in candidates
        if candidate.confirmed_trade_date or candidate.quote_timestamp
    ]
    if not signal_dates:
        return {}
    symbols = sorted({candidate.symbol for candidate in candidates})
    return DailyHistoryRepository(db).fetch_rows_for_symbols(
        symbols,
        min(signal_dates),
        "9999-12-31",
    )


def _build_backtest_response(
    *,
    strategy: str,
    lookback_days: int,
    items,
    extra_notes: list[str] | None = None,
) -> LowBuyExecutionBacktestResponse:
    filled = [item for item in items if item.status == "filled"]
    not_filled = [item for item in items if item.status == "not_filled"]
    invalid = [item for item in items if item.status == "invalid"]
    winners = [item for item in filled if item.net_return_pct > 0]
    losers = [item for item in filled if item.net_return_pct < 0]
    stop_losses = [item for item in filled if "止损" in item.exit_reason]
    take_profits = [item for item in filled if "止盈" in item.exit_reason or "防守线" in item.exit_reason]
    time_exits = [item for item in filled if "最长持有" in item.exit_reason]
    gains = sum(max(item.net_return_pct, 0.0) for item in filled)
    losses = abs(sum(min(item.net_return_pct, 0.0) for item in filled))
    avg_win = _avg([item.net_return_pct for item in winners])
    avg_loss_abs = abs(_avg([item.net_return_pct for item in losers]))
    returns_series = [item.net_return_pct if item.status == "filled" else 0.0 for item in items]
    signal_series = [item.status == "filled" for item in items]
    real_sharpe = _compute_sharpe_from_returns(returns_series)
    filled_records = [
        {"symbol": item.symbol, "net_return_pct": item.net_return_pct}
        for item in filled
    ]
    quality_fields = data_quality_payload(
        DataQualitySnapshot()
        if items
        else DataQualitySnapshot("limited", "未找到可回测样本", ("物化样本缺失",))
    )
    return LowBuyExecutionBacktestResponse(
        strategy_key=strategy,
        lookback_days=lookback_days,
        evaluated_signals=len(items),
        filled_signals=len(filled),
        not_filled_signals=len(not_filled),
        invalid_signals=len(invalid),
        win_rate=_rate(len(winners), len(filled)),
        net_win_rate=_rate(len(winners) - len(losers), len(filled)),
        not_filled_rate=_rate(len(not_filled), len(items)),
        stop_loss_count=len(stop_losses),
        stop_loss_rate=_rate(len(stop_losses), len(filled)),
        take_profit_count=len(take_profits),
        take_profit_rate=_rate(len(take_profits), len(filled)),
        time_exit_count=len(time_exits),
        time_exit_rate=_rate(len(time_exits), len(filled)),
        avg_net_return_pct=_avg([item.net_return_pct for item in filled]),
        avg_max_gain_pct=_avg([item.max_gain_pct for item in filled]),
        avg_max_drawdown_pct=_avg([item.max_drawdown_pct for item in filled]),
        max_adverse_pct=min([item.max_drawdown_pct for item in filled], default=0.0),
        avg_loss_pct=-avg_loss_abs,
        win_loss_ratio=round(avg_win / max(avg_loss_abs, 0.01), 3) if winners and losers else 0.0,
        profit_factor=round(gains / max(losses, 0.01), 3) if filled else 0.0,
        **quality_fields,
        pbo=compute_pbo(
            real_sharpe=real_sharpe,
            signal_series=signal_series,
            returns_series=returns_series,
            n_permutations=1000,
        ),
        crisis_scenario=simulate_liquidity_crisis(filled_records),
        notes=[
            "主指标按真实执行口径统计：先判断信号后 2 日是否触达买点，再按止损/止盈/移动防守退出，并扣除 16bps 成本。",
            "未成交信号单独统计，不再把未来最高价触达目标当作主胜率。",
            *(extra_notes or []),
        ],
        items=items,
    )


def _backtest_diagnostic_notes(candidates: list[LowBuyCandidateOut]) -> list[str]:
    if candidates:
        return []
    return [
        "未找到当前版本的确定买入物化样本；请先重建该策略的全量物化结果后再解读回测。",
    ]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _rate(part: int, total: int) -> float:
    return round(part / total * 100, 3) if total > 0 else 0.0
