from __future__ import annotations

from app.repositories.low_buy import DailyHistoryRepository, LowBuyPerformanceRepository, LowBuyResultRepository
from app.services.low_buy.shared import (
    Any,
    LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
    LowBuyCandidateOut,
    LowBuyPerformanceBucketOut,
    LowBuyStrategyPerformanceOut,
    PERFORMANCE_FORWARD_DAYS,
    PERFORMANCE_LOOKBACK_DAYS,
    RECENT_PERFORMANCE_LOOKBACK_DAYS,
    Session,
    SettingsService,
    datetime,
)
from app.services.low_buy.portfolio_risk import build_portfolio_risk
from app.services.low_buy.execution_simulation import DailyExecutionBar, bars_from_repository_rows
from app.services.low_buy.performance_records import build_performance_record
from app.services.low_buy.position_sizing import compute_kelly_position
from app.services.low_buy.performance_stats import (
    build_performance_buckets,
    empty_strategy_performance,
)
from app.services.low_buy.risk_metrics import compute_cvar


class LowBuyPerformanceMixin:
    def _attach_strategy_performance(self, db: Session, payload, build_if_missing: bool = False):
        performance = self._resolve_strategy_performance(
            db=db,
            strategy=payload.strategy_key,
            latest_trade_date=payload.latest_trade_date,
            build_if_missing=build_if_missing,
        )
        return self._attach_loaded_strategy_performance(payload, performance)

    def _resolve_strategy_performance(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        build_if_missing: bool = False,
    ) -> LowBuyStrategyPerformanceOut:
        performance = self._load_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        )
        if performance is None and build_if_missing:
            performance = self._build_strategy_performance_snapshot(
                db=db,
                strategy=strategy,
                latest_trade_date=latest_trade_date,
            )
        if performance is not None:
            return performance
        return self._empty_strategy_performance(
            target_profit_pct=self._load_stock_profit_target_pct(db),
            lookback_days=PERFORMANCE_LOOKBACK_DAYS,
            note="绩效归因缓存仍在补齐，先显示占位统计。",
        )

    def _attach_loaded_strategy_performance(
        self,
        payload,
        performance: LowBuyStrategyPerformanceOut,
    ):
        confirmed_candidates = self._apply_strategy_performance_to_candidates(
            payload.confirmed_candidates,
            performance,
        )
        candidates = self._apply_strategy_performance_to_candidates(
            payload.candidates,
            performance,
        )
        return payload.model_copy(
            update={
                "performance": performance,
                "confirmed_candidates": confirmed_candidates,
                "candidates": candidates,
                "portfolio_risk": build_portfolio_risk(
                    confirmed_candidates + candidates,
                    market_state=getattr(payload, "market_state", "low_volume_wait"),
                ),
                "history_sections": self._apply_strategy_performance_to_history_sections(
                    payload.history_sections,
                    performance,
                ),
            }
        )

    def _apply_strategy_performance_to_history_sections(
        self,
        sections,
        performance: LowBuyStrategyPerformanceOut | None,
    ):
        return [
            section.model_copy(
                update={
                    "candidates": self._apply_strategy_performance_to_candidates(
                        section.candidates,
                        performance,
                    )
                }
            )
            for section in sections
        ]

    def _apply_strategy_performance_to_candidates(
        self,
        candidates: list[LowBuyCandidateOut],
        performance: LowBuyStrategyPerformanceOut | None,
    ) -> list[LowBuyCandidateOut]:
        positioner = getattr(self, "_apply_candidate_positioning", None)
        if positioner is None:
            return [item.model_copy(deep=True) for item in candidates]
        return [positioner(item.model_copy(deep=True), performance) for item in candidates]

    def _load_strategy_performance_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        lookback_days: int = PERFORMANCE_LOOKBACK_DAYS,
    ) -> LowBuyStrategyPerformanceOut | None:
        row = LowBuyPerformanceRepository(db).fetch(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            lookback_days=lookback_days,
        )
        if row is None or not row.payload_json or row.lookback_days != lookback_days:
            return None
        try:
            payload = LowBuyStrategyPerformanceOut.model_validate_json(row.payload_json)
        except Exception:
            return None
        if payload.snapshot_version != LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION:
            return None
        return payload

    def _save_strategy_performance_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        payload: LowBuyStrategyPerformanceOut,
    ) -> None:
        serialized = payload.model_dump_json()
        values = {
            "lookback_days": payload.lookback_days,
            "signal_count": payload.signal_count,
            "evaluated_signals": payload.evaluated_signals,
            "pending_signals": payload.pending_signals,
            "hit_count": payload.hit_count,
            "hit_rate": payload.hit_rate,
            "win_rate_1d": payload.win_rate_1d,
            "win_rate_2d": payload.win_rate_2d,
            "win_rate_3d": payload.win_rate_3d,
            "win_rate_4d": payload.win_rate_4d,
            "win_rate_5d": payload.win_rate_5d,
            "avg_return_1d": payload.avg_return_1d,
            "avg_return_2d": payload.avg_return_2d,
            "avg_return_3d": payload.avg_return_3d,
            "avg_return_4d": payload.avg_return_4d,
            "avg_return_5d": payload.avg_return_5d,
            "avg_max_gain_5d": payload.avg_max_gain_5d,
            "avg_max_drawdown_5d": payload.avg_max_drawdown_5d,
            "payload_json": serialized,
        }
        LowBuyPerformanceRepository(db).save(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
            lookback_days=payload.lookback_days,
            values=values,
        )
        db.commit()

    def _build_strategy_performance_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
    ) -> LowBuyStrategyPerformanceOut:
        primary = self._compute_strategy_performance(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            lookback_days=PERFORMANCE_LOOKBACK_DAYS,
            persist=True,
        )
        self._ensure_recent_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        )
        return primary

    def _ensure_recent_strategy_performance_snapshot(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
    ) -> LowBuyStrategyPerformanceOut:
        cached = self._load_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            lookback_days=RECENT_PERFORMANCE_LOOKBACK_DAYS,
        )
        if cached is not None:
            return cached
        return self._compute_strategy_performance(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            lookback_days=RECENT_PERFORMANCE_LOOKBACK_DAYS,
            persist=True,
        )

    def _compute_strategy_performance(
        self,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        lookback_days: int,
        persist: bool,
    ) -> LowBuyStrategyPerformanceOut:
        recent_trade_dates = [
            item
            for item in self._get_recent_trade_dates(lookback_days + PERFORMANCE_FORWARD_DAYS + 40)
            if item < latest_trade_date
        ][-lookback_days:]
        target_profit_pct = self._load_stock_profit_target_pct(db)
        if not recent_trade_dates:
            empty = self._empty_strategy_performance(target_profit_pct=target_profit_pct)
            if persist:
                self._save_strategy_performance_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=latest_trade_date,
                    payload=empty,
                )
            return empty

        rows = LowBuyResultRepository(db).fetch_confirmed_results_for_dates(
            latest_trade_dates=recent_trade_dates,
            strategy_key=strategy,
            limit_per_date=999,
        )
        rows = self._filter_current_performance_rows(rows)
        if not rows:
            empty = self._empty_strategy_performance(
                target_profit_pct=target_profit_pct,
                lookback_days=len(recent_trade_dates),
                note=f"最近 {len(recent_trade_dates)} 个交易日没有触发确定买入样本。",
            )
            if persist:
                self._save_strategy_performance_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=latest_trade_date,
                    payload=empty,
                )
            return empty

        rows_by_symbol = self._load_performance_daily_bars(
            db=db,
            rows=rows,
            start_date=min(recent_trade_dates),
            latest_trade_date=latest_trade_date,
        )
        records: list[dict[str, Any]] = []
        pending_signals = 0
        for row in rows:
            try:
                candidate = LowBuyCandidateOut.model_validate_json(row.payload_json)
            except Exception:
                continue
            payload_json = row.payload_json or ""
            bars = rows_by_symbol.get(row.symbol, [])
            record = build_performance_record(
                row=row,
                candidate=candidate,
                bars=bars,
                payload_json=payload_json,
                target_profit_pct=target_profit_pct,
            )
            if record is None:
                pending_signals += 1
                continue
            records.append(record)

        if not records:
            empty = self._empty_strategy_performance(
                target_profit_pct=target_profit_pct,
                lookback_days=len(recent_trade_dates),
                note="已有确定买入信号，但还没有足够的后续行情完成归因。",
            )
            empty = empty.model_copy(update={"signal_count": len(rows), "pending_signals": len(rows)})
            if persist:
                self._save_strategy_performance_snapshot(
                    db=db,
                    strategy=strategy,
                    latest_trade_date=latest_trade_date,
                    payload=empty,
                )
            return empty

        evaluated_signals = len(records)
        filled_signals = sum(1 for item in records if item["filled"])
        not_filled_signals = sum(1 for item in records if item["not_filled"])
        hit_count = sum(1 for item in records if item["hit"])
        filled_records = [item for item in records if item["filled"]]
        net_returns = [item["net_return"] for item in filled_records]
        winning_returns = [value for value in net_returns if value > 0]
        losing_returns = [value for value in net_returns if value < 0]
        loss_count = sum(1 for value in net_returns if value < 0)
        gross_gains = sum(max(value, 0.0) for value in net_returns)
        gross_losses = abs(sum(min(value, 0.0) for value in net_returns))
        avg_win_pct = round(sum(winning_returns) / max(len(winning_returns), 1), 2)
        avg_loss_pct = round(sum(losing_returns) / max(len(losing_returns), 1), 2)
        kelly = compute_kelly_position(
            win_rate=hit_count / max(filled_signals, 1),
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
        )
        performance = LowBuyStrategyPerformanceOut(
            snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
            lookback_days=len(recent_trade_dates),
            signal_count=len(rows),
            evaluated_signals=evaluated_signals,
            filled_signals=filled_signals,
            not_filled_signals=not_filled_signals,
            pending_signals=len(rows) - evaluated_signals,
            hit_count=hit_count,
            hit_rate=round(hit_count / max(filled_signals, 1) * 100, 2),
            net_win_rate=round((hit_count - loss_count) / max(filled_signals, 1) * 100, 2),
            not_filled_rate=round(not_filled_signals / evaluated_signals * 100, 2),
            stop_loss_rate=round(sum(1 for item in records if item["stop_loss"]) / max(filled_signals, 1) * 100, 2),
            avg_net_return_pct=round(sum(net_returns) / max(len(net_returns), 1), 2),
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            profit_factor=round(gross_gains / max(gross_losses, 0.01), 3) if net_returns else 0.0,
            cvar_5pct=compute_cvar(net_returns, confidence=0.95),
            kelly_half_position_pct=round(kelly.half_kelly * 100, 2),
            win_rate_1d=round(sum(1 for item in filled_records if item["return_1d"] > 0) / max(filled_signals, 1) * 100, 2),
            win_rate_2d=round(sum(1 for item in filled_records if item["return_2d"] > 0) / max(filled_signals, 1) * 100, 2),
            win_rate_3d=round(sum(1 for item in filled_records if item["return_3d"] > 0) / max(filled_signals, 1) * 100, 2),
            win_rate_4d=round(sum(1 for item in filled_records if item["return_4d"] > 0) / max(filled_signals, 1) * 100, 2),
            win_rate_5d=round(sum(1 for item in filled_records if item["return_5d"] > 0) / max(filled_signals, 1) * 100, 2),
            avg_return_1d=round(sum(item["return_1d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_return_2d=round(sum(item["return_2d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_return_3d=round(sum(item["return_3d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_return_4d=round(sum(item["return_4d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_return_5d=round(sum(item["return_5d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_max_gain_5d=round(sum(item["max_gain_5d"] for item in filled_records) / max(filled_signals, 1), 2),
            avg_max_drawdown_5d=round(sum(item["max_drawdown_5d"] for item in filled_records) / max(filled_signals, 1), 2),
            target_profit_pct=round(target_profit_pct, 2),
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            attribution_notes=[
                "主命中率按真实执行口径统计：信号后 2 日内触达买点才计入成交，退出按止损/止盈/移动防守并扣除 16bps 成本。",
                "净胜优势按（盈利笔数 - 亏损笔数）/ 成交笔数统计，0 收益不计入亏损。",
                f"5 日内最高价触及 {target_profit_pct:.1f}% 目标仅作为辅助冲高参考，不再作为主胜率。",
                "1/2/3/4/5 日收益只统计真实成交后的收盘收益，未成交样本只计入未成交率。",
                "市场状态和行业层级拆解只参与排序与仓位修正，不替代原始买点条件。",
            ],
            sector_attribution=self._build_performance_buckets(filled_records, key="sector_name"),
            retracement_attribution=self._build_performance_buckets(filled_records, key="retracement_bucket"),
            market_state_attribution=self._build_performance_buckets(
                filled_records,
                key="market_state",
                limit=None,
                sort_return_field="avg_return_5d",
            ),
            industry_tier_attribution=self._build_performance_buckets(
                filled_records,
                key="industry_tier",
                limit=None,
                sort_return_field="avg_return_3d",
            ),
        )
        if persist:
            self._save_strategy_performance_snapshot(
                db=db,
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                payload=performance,
            )
        return performance

    @staticmethod
    def _load_performance_daily_bars(
        *,
        db: Session,
        rows,
        start_date: str,
        latest_trade_date: str,
    ) -> dict[str, list[DailyExecutionBar]]:
        symbols = sorted({row.symbol for row in rows})
        raw_rows = DailyHistoryRepository(db).fetch_rows_for_symbols(
            symbols=symbols,
            start_date_iso=start_date,
            latest_trade_date=latest_trade_date,
        )
        return {
            symbol: bars_from_repository_rows(symbol_rows)
            for symbol, symbol_rows in raw_rows.items()
        }

    def _filter_current_performance_rows(self, rows):
        payload_is_current = getattr(self, "_candidate_payload_is_current", None)
        if not callable(payload_is_current):
            return list(rows)
        return [row for row in rows if payload_is_current(row.payload_json)]

    def _empty_strategy_performance(self, target_profit_pct: float, lookback_days: int = 0, note: str | None = None) -> LowBuyStrategyPerformanceOut:
        return empty_strategy_performance(
            target_profit_pct=target_profit_pct,
            lookback_days=lookback_days,
            note=note,
        )

    def _build_performance_buckets(
        self,
        records: list[dict[str, Any]],
        key: str,
        limit: int | None = 3,
        sort_return_field: str = "avg_return_3d",
    ) -> list[LowBuyPerformanceBucketOut]:
        return build_performance_buckets(records, key=key, limit=limit, sort_return_field=sort_return_field)

    @staticmethod
    def _load_stock_profit_target_pct(db: Session) -> float:
        try:
            settings = SettingsService(db).get_payload()
            return float(settings.strategy_min_profit_stock_pct or settings.strategy_min_profit_pct or 3.0)
        except Exception:
            return 3.0
