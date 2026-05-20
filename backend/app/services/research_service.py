from __future__ import annotations

import json
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AnalysisLog, BacktestRun, SignalReplay
from app.models.schemas import (
    AnalysisResponse,
    BacktestRequest,
    BacktestResponse,
    BacktestTrade,
    KlineBar,
    QuoteSnapshot,
    ReplayOut,
)
from app.services.quant_engine import QuantEngine


class ResearchService:
    def __init__(self) -> None:
        self.engine = QuantEngine()

    def persist_analysis(self, db: Session, analysis: AnalysisResponse) -> int:
        row = AnalysisLog(
            symbol=analysis.symbol,
            action=analysis.suggestion.action,
            signal_score=analysis.suggestion.signal_score,
            risk_level=analysis.suggestion.risk_level,
            payload_json=analysis.model_dump_json(),
        )
        db.add(row)
        db.flush()

        replay = SignalReplay(
            analysis_log_id=row.id,
            symbol=analysis.symbol,
            outcome="pending",
            review_notes="等待后续复盘或手工更新。",
        )
        db.add(replay)
        db.commit()
        return int(row.id)

    def list_replays(self, db: Session, limit: int = 100) -> list[ReplayOut]:
        rows = db.execute(
            select(SignalReplay).order_by(SignalReplay.id.desc()).limit(limit)
        ).scalars().all()
        return [
            ReplayOut(
                id=row.id,
                symbol=row.symbol,
                outcome=row.outcome,
                pnl_pct=row.pnl_pct,
                max_favorable_excursion=row.max_favorable_excursion,
                max_adverse_excursion=row.max_adverse_excursion,
                review_notes=row.review_notes,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def run_backtest(
        self,
        db: Session,
        request: BacktestRequest,
        bars: list[KlineBar],
        quote_factory,
        runtime_context_factory,
        risk_config: dict[str, Any],
        owner_user_id: int | None = None,
    ) -> BacktestResponse:
        window = 60 if request.bar_period == "1m" else 48
        trades: list[BacktestTrade] = []

        for index in range(window, len(bars) - 3):
            subset = bars[max(0, index - window) : index + 1]
            quote = quote_factory(subset)
            context = runtime_context_factory(subset, quote)
            metrics, suggestion, _, _ = self.engine.evaluate(
                quote=quote,
                bars=subset,
                rules=context["rules"],
                sector=context["sector"],
                events=context["events"],
                microstructure=context["microstructure"],
                request=context["request"],
                risk_config=risk_config,
                market_regime=context.get("market_regime"),
            )
            if suggestion.action == "hold" or suggestion.entry_price is None or suggestion.exit_price is None:
                continue

            future_bars = bars[index + 1 : index + 4]
            if not future_bars:
                continue
            realized_exit = future_bars[-1].close
            entry = suggestion.entry_price
            expected_exit = suggestion.exit_price

            if suggestion.action == "positive_t":
                pnl_pct = ((min(max(bar.high for bar in future_bars), expected_exit) - entry) / entry) * 100
            else:
                pnl_pct = ((entry - max(min(bar.low for bar in future_bars), expected_exit)) / entry) * 100

            trades.append(
                BacktestTrade(
                    timestamp=subset[-1].timestamp,
                    action=suggestion.action,
                    entry_price=entry,
                    exit_price=round(realized_exit, 3),
                    pnl_pct=round(pnl_pct, 3),
                    signal_score=suggestion.signal_score,
                )
            )

        total_trades = len(trades)
        pnl_list = [trade.pnl_pct for trade in trades]
        wins = [value for value in pnl_list if value > 0]
        losses = [abs(value) for value in pnl_list if value < 0]
        win_rate = (len(wins) / total_trades * 100) if total_trades else 0.0
        avg_pnl = mean(pnl_list) if pnl_list else 0.0
        profit_factor = (sum(wins) / sum(losses)) if losses else float(sum(wins) > 0)
        max_drawdown = self._max_drawdown(pnl_list)
        walk_forward_score = self._walk_forward_score(pnl_list, request.walk_forward_windows)

        response = BacktestResponse(
            symbol=request.symbol,
            total_trades=total_trades,
            win_rate=round(win_rate, 2),
            avg_pnl_pct=round(avg_pnl, 3),
            profit_factor=round(float(profit_factor), 3),
            max_drawdown=round(max_drawdown, 3),
            walk_forward_score=round(walk_forward_score, 3),
            trades=trades[-120:],
        )

        run = BacktestRun(
            name=f"{request.symbol}-{request.bar_period}-walkforward",
            owner_user_id=owner_user_id,
            params_json=request.model_dump_json(),
            result_json=response.model_dump_json(),
        )
        db.add(run)
        db.commit()
        response.run_id = run.id
        return response

    @staticmethod
    def _max_drawdown(pnl_list: list[float]) -> float:
        peak = 0.0
        equity = 0.0
        max_dd = 0.0
        for pnl in pnl_list:
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        return max_dd

    @staticmethod
    def _walk_forward_score(pnl_list: list[float], windows: int) -> float:
        if not pnl_list:
            return 0.0
        windows = max(1, windows)
        size = max(1, len(pnl_list) // windows)
        scores = []
        for start in range(0, len(pnl_list), size):
            chunk = pnl_list[start : start + size]
            if not chunk:
                continue
            scores.append(sum(chunk) / len(chunk))
        return mean(scores) if scores else 0.0


def quote_from_bars(symbol: str, name: str, market: str, instrument_type: str, bars: list[KlineBar]) -> QuoteSnapshot:
    last = bars[-1]
    prev_close = bars[-2].close if len(bars) > 1 else last.open
    change_amount = last.close - prev_close
    change_pct = (change_amount / prev_close * 100) if prev_close else 0.0
    return QuoteSnapshot(
        symbol=symbol,
        name=name,
        market=market,
        instrument_type=instrument_type,
        last_price=last.close,
        change_pct=round(change_pct, 3),
        change_amount=round(change_amount, 3),
        open_price=last.open,
        high_price=last.high,
        low_price=last.low,
        prev_close=prev_close,
        volume=last.volume,
        amount=last.amount,
        turnover_rate=last.turnover,
        volume_ratio=None,
        timestamp=last.timestamp,
    )
