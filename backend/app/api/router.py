from fastapi import APIRouter

from app.api.routes import (
    admin_metrics,
    admin_users,
    agent,
    agent_quality,
    ai,
    analysis,
    app_mobile,
    auth,
    backtests,
    bff,
    feishu,
    factor_mining,
    feature_flags,
    instruments,
    intraday,
    internal_scan_worker,
    market,
    market_data_sources,
    ml_signals,
    monitor,
    operation_audit,
    paper,
    paper_compare,
    quant_config,
    research,
    runtime_tasks,
    screeners,
    settings,
    strategy_stream,
    strategy_meta,
    v1,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(bff.router, tags=["bff"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(backtests.router, tags=["backtests"])
api_router.include_router(admin_metrics.router, tags=["admin"])
api_router.include_router(admin_users.router, tags=["admin"])
api_router.include_router(instruments.router, tags=["market"])
api_router.include_router(intraday.router, tags=["intraday"])
api_router.include_router(internal_scan_worker.router, tags=["internal"])
api_router.include_router(watchlist.router, tags=["watchlist"])
api_router.include_router(monitor.router, tags=["monitor"])
api_router.include_router(market.router, tags=["market"])
api_router.include_router(market_data_sources.router, tags=["market"])
api_router.include_router(app_mobile.router, tags=["app-mobile"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(ai.router, tags=["ai"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(screeners.router, tags=["screeners"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(strategy_meta.router, tags=["strategy-meta"])
api_router.include_router(strategy_stream.router, tags=["strategy-stream"])
api_router.include_router(agent.router, tags=["agent"])
api_router.include_router(agent_quality.router, tags=["agent"])
api_router.include_router(paper.router, tags=["paper"])
api_router.include_router(paper_compare.router, tags=["paper"])
api_router.include_router(feishu.router, tags=["feishu"])
api_router.include_router(factor_mining.router, tags=["factor-mining"])
api_router.include_router(feature_flags.router, tags=["feature-flags"])
api_router.include_router(quant_config.router, tags=["quant"])
api_router.include_router(operation_audit.router, tags=["admin"])
api_router.include_router(runtime_tasks.router, tags=["runtime-tasks"])
api_router.include_router(ml_signals.router, tags=["ml"])
api_router.include_router(v1.router, tags=["v1"])
