from __future__ import annotations

from typing import Any

HEAVY_RESEARCH_TASK_TYPES = (
    "low_buy_execution_backtest",
    "legacy_research_backtest",
    "etf_t0_minute_backtest",
    "etf_t0_research_report",
    "backtest_portfolio_optimization",
    "backtest_position_policy_research",
    "ml_signal_build_samples",
    "ml_signal_train",
    "factor_mining_iterate",
    "analysis_batch",
    "paper_smart_t_backtest",
    "paper_backtest_comparison",
)
ML_HEAVY_TASK_TYPES = {"ml_signal_build_samples", "ml_signal_train"}
FACTOR_HEAVY_TASK_TYPES = {"factor_mining_iterate"}


def execute_heavy_research_task(task_type: str, payload: dict[str, Any], db) -> dict[str, Any]:  # noqa: ANN001
    if task_type == "low_buy_execution_backtest":
        from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
        from app.services.low_buy_screener import LowBuyScreenerService

        response = LowBuyScreenerService().execution_backtest(
            db=db,
            strategy=str(payload.get("strategy") or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY),
            lookback_days=max(5, min(int(payload.get("lookback_days") or 60), 260)),
            limit=max(1, min(int(payload.get("limit") or 200), 1000)),
        )
        return response.model_dump(mode="json")

    if task_type == "legacy_research_backtest":
        from app.models.schema_defs.research import BacktestRequest
        from app.services.analysis_service import AnalysisService
        from app.services.market_data import MarketDataService

        request = BacktestRequest.model_validate(payload)
        instrument = MarketDataService().get_instrument(db, request.symbol)
        response = AnalysisService().run_backtest(
            db,
            request,
            instrument,
            owner_user_id=int(payload["owner_user_id"]) if payload.get("owner_user_id") else None,
        )
        return response.model_dump(mode="json")

    if task_type == "etf_t0_minute_backtest":
        from app.models.schema_defs.backtest import EtfT0BacktestRequest
        from app.models.schemas import KlineBar
        from app.services.etf.t0_backtest import run_etf_t0_backtest

        request = EtfT0BacktestRequest.model_validate(payload)
        report = run_etf_t0_backtest(
            symbol=request.symbol,
            name=request.name,
            bars=_etf_bars(request.bars, KlineBar),
            quantity=request.quantity,
            min_signal_bars=request.min_signal_bars,
            max_trades_per_day=request.max_trades_per_day,
            params=request.params,
        )
        return report.to_dict()

    if task_type == "etf_t0_research_report":
        from app.models.schema_defs.backtest import EtfT0ResearchRequest
        from app.models.schemas import KlineBar
        from app.services.etf.t0_backtest import EtfT0MarketRegimeSegment, run_etf_t0_research_report

        request = EtfT0ResearchRequest.model_validate(payload)
        report = run_etf_t0_research_report(
            symbol=request.symbol,
            name=request.name,
            bars=_etf_bars(request.bars, KlineBar),
            quantity=request.quantity,
            min_signal_bars=request.min_signal_bars,
            max_trades_per_day=request.max_trades_per_day,
            params=request.params,
            vwap_deviation_values=request.vwap_deviation_values,
            oversold_rsi_values=request.oversold_rsi_values,
            market_regime_segments=[
                EtfT0MarketRegimeSegment(regime=item.regime, start_time=item.start_time, end_time=item.end_time)
                for item in request.market_regime_segments
            ]
            or None,
        )
        return report.to_dict()

    if task_type == "backtest_portfolio_optimization":
        from app.services.portfolio_heuristic_optimizer import optimize_strategy_portfolio

        return optimize_strategy_portfolio(db, run_id=int(payload["run_id"]), method=str(payload.get("method") or "hrp"))

    if task_type == "backtest_position_policy_research":
        from app.services.position_policy_research import run_position_policy_research

        return run_position_policy_research(
            db,
            run_id=int(payload["run_id"]),
            train_shadow=bool(payload.get("train_shadow", False)),
        )

    if task_type == "ml_signal_build_samples":
        from app.models.schema_defs.phase4 import MLSignalSampleBuildRequest
        from app.services.ml_signal import MLSignalService

        response = MLSignalService(db).build_samples(MLSignalSampleBuildRequest.model_validate(payload))
        return response.model_dump(mode="json")

    if task_type == "ml_signal_train":
        from app.models.schema_defs.phase4 import MLSignalTrainRequest
        from app.services.ml_signal import MLSignalService

        response = MLSignalService(db).train(MLSignalTrainRequest.model_validate(payload))
        return response.model_dump(mode="json")

    if task_type == "factor_mining_iterate":
        from app.models.schema_defs.factor_mining import FactorIterationRequest
        from app.services.factor_mining.orchestrator import FactorMiningOrchestrator

        request = FactorIterationRequest.model_validate(payload)
        response = FactorMiningOrchestrator(db).iterate(
            hypothesis=request.hypothesis,
            rounds=request.rounds,
            evaluation=request.evaluation,
        )
        return response.model_dump(mode="json")

    if task_type == "analysis_batch":
        from app.models.schema_defs.analysis import AnalysisRequest
        from app.services.analysis_service import AnalysisService

        requests = [AnalysisRequest.model_validate(item) for item in payload.get("items") or []]
        if not requests:
            return {"ok": False, "status": "blocked", "reason": "analysis_batch requires items"}
        responses = AnalysisService().analyze_batch(db, requests)
        return {"ok": True, "items": [item.model_dump(mode="json") for item in responses], "count": len(responses)}

    if task_type == "paper_smart_t_backtest":
        from app.services.paper.smart_t_backtest import SmartTBacktestService

        report = SmartTBacktestService(db).run(
            start_date=payload.get("start_date") or None,
            end_date=payload.get("end_date") or None,
            strategies=[str(item) for item in payload.get("strategies") or []] or None,
            max_signals_per_day=max(1, min(int(payload.get("max_signals_per_day") or 20), 100)),
            forward_days=max(1, min(int(payload.get("forward_days") or 3), 10)),
            sample_limit=max(0, min(int(payload.get("sample_limit") or 50), 200)),
        )
        return {
            **report.__dict__,
            "threshold_stats": [item.__dict__ for item in report.threshold_stats],
            "samples": [item.__dict__ for item in report.samples],
        }

    if task_type == "paper_backtest_comparison":
        from app.services.paper.backtest_compare import PaperBacktestComparisonService

        response = PaperBacktestComparisonService(db).compare(
            account_id=int(payload["account_id"]),
            backtest_run_id=int(payload["backtest_run_id"]),
            deviation_threshold_pct=float(payload.get("deviation_threshold_pct") or 20.0),
        )
        return response.model_dump(mode="json")

    raise ValueError(f"unknown heavy research task: {task_type}")


def _etf_bars(items, kline_bar_cls):  # noqa: ANN001
    return [
        kline_bar_cls(
            timestamp=item.timestamp,
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=item.volume,
            amount=item.amount,
        )
        for item in items
    ]
