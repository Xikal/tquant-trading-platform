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
from app.services.low_buy.execution_simulation import DailyExecutionBar, bars_from_repository_rows, simulate_candidate_execution
from app.services.low_buy.position_sizing import compute_kelly_position
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
            signal_index = self._daily_bar_index(bars, row.latest_trade_date)
            if signal_index is None:
                pending_signals += 1
                continue
            forward = bars[signal_index + 1 : signal_index + 1 + PERFORMANCE_FORWARD_DAYS]
            if len(forward) < PERFORMANCE_FORWARD_DAYS:
                pending_signals += 1
                continue

            execution = simulate_candidate_execution(
                candidate=candidate.model_copy(update={"confirmed_trade_date": row.latest_trade_date}),
                rows=bars,
            )
            filled = execution.status == "filled"
            return_1d = self._filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 1) if filled else 0.0
            return_2d = self._filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 2) if filled else 0.0
            return_3d = self._filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 3) if filled else 0.0
            return_4d = self._filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 4) if filled else 0.0
            return_5d = self._filled_close_return(bars, execution.entry_trade_date, execution.entry_price, 5) if filled else 0.0
            max_gain_5d = execution.max_gain_pct if filled else 0.0
            max_drawdown_5d = execution.max_drawdown_pct if filled else 0.0
            records.append(
                {
                    "symbol": candidate.symbol,
                    "sector_name": candidate.sector_name or "未分类",
                    "retracement_bucket": self._to_retracement_bucket(candidate.retracement_days),
                    "market_state": candidate.market_state if '"market_state"' in payload_json else "历史未标注",
                    "industry_tier": candidate.industry_tier if '"industry_tier"' in payload_json else "历史未标注",
                    "filled": filled,
                    "not_filled": execution.status == "not_filled",
                    "stop_loss": filled and "止损" in execution.exit_reason,
                    "net_return": execution.net_return_pct if filled else 0.0,
                    "return_1d": return_1d,
                    "return_2d": return_2d,
                    "return_3d": return_3d,
                    "return_4d": return_4d,
                    "return_5d": return_5d,
                    "max_gain_5d": max_gain_5d,
                    "max_drawdown_5d": max_drawdown_5d,
                    "legacy_target_hit": filled and max_gain_5d >= target_profit_pct,
                    "hit": filled and execution.net_return_pct > 0,
                }
            )

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

    @staticmethod
    def _daily_bar_index(rows: list[DailyExecutionBar], trade_date: str) -> int | None:
        for index, row in enumerate(rows):
            if row.trade_date == trade_date:
                return index
        return None

    def _filled_close_return(
        self,
        rows: list[DailyExecutionBar],
        entry_trade_date: str | None,
        entry_price: float,
        holding_days: int,
    ) -> float:
        if not entry_trade_date or entry_price <= 0:
            return 0.0
        entry_index = self._daily_bar_index(rows, entry_trade_date)
        if entry_index is None:
            return 0.0
        target_index = min(entry_index + max(holding_days, 1) - 1, len(rows) - 1)
        return (rows[target_index].close_price / entry_price - 1) * 100

    def _filter_current_performance_rows(self, rows):
        payload_is_current = getattr(self, "_candidate_payload_is_current", None)
        if not callable(payload_is_current):
            return list(rows)
        return [row for row in rows if payload_is_current(row.payload_json)]

    def _empty_strategy_performance(self, target_profit_pct: float, lookback_days: int = 0, note: str | None = None) -> LowBuyStrategyPerformanceOut:
        notes = [
            "主命中率按真实执行净收益胜率统计。",
            "净胜优势按盈利笔数减亏损笔数后的成交占比统计。",
            f"5 日内最高价触及 {target_profit_pct:.1f}% 目标仅作为辅助冲高参考。",
        ]
        if note:
            notes.append(note)
        return LowBuyStrategyPerformanceOut(
            snapshot_version=LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION,
            lookback_days=lookback_days,
            target_profit_pct=round(target_profit_pct, 2),
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            attribution_notes=notes,
        )

    def _build_performance_buckets(
        self,
        records: list[dict[str, Any]],
        key: str,
        limit: int | None = 3,
        sort_return_field: str = "avg_return_3d",
    ) -> list[LowBuyPerformanceBucketOut]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            label = str(item.get(key) or "未分类")
            grouped.setdefault(label, []).append(item)
        buckets: list[LowBuyPerformanceBucketOut] = []
        for label, items in grouped.items():
            sample_count = len(items)
            hit_count = sum(1 for item in items if item["hit"])
            buckets.append(
                LowBuyPerformanceBucketOut(
                    label=label,
                    sample_count=sample_count,
                    hit_count=hit_count,
                    hit_rate=round(hit_count / sample_count * 100, 2),
                    avg_return_3d=round(sum(item["return_3d"] for item in items) / sample_count, 2),
                    avg_return_5d=round(sum(item["return_5d"] for item in items) / sample_count, 2),
                )
            )
        buckets.sort(
            key=lambda item: (
                item.avg_return_5d if sort_return_field == "avg_return_5d" else item.avg_return_3d,
                item.hit_rate,
                item.sample_count,
            ),
            reverse=True,
        )
        if limit is None:
            return buckets
        return buckets[:limit]

    @staticmethod
    def _to_retracement_bucket(retracement_days: int) -> str:
        if retracement_days <= 2:
            return "1-2天回调"
        if retracement_days <= 4:
            return "3-4天回调"
        return "5-7天回调"

    @staticmethod
    def _load_stock_profit_target_pct(db: Session) -> float:
        try:
            settings = SettingsService(db).get_payload()
            return float(settings.strategy_min_profit_stock_pct or settings.strategy_min_profit_pct or 3.0)
        except Exception:
            return 3.0
