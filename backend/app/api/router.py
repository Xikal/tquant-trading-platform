from fastapi import APIRouter

from app.api.routes import (
    admin_metrics,
    admin_users,
    agent,
    ai,
    analysis,
    app_mobile,
    auth,
    backtests,
    feishu,
    instruments,
    intraday,
    market,
    monitor,
    paper,
    research,
    screeners,
    settings,
    v1,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(backtests.router, tags=["backtests"])
api_router.include_router(admin_metrics.router, tags=["admin"])
api_router.include_router(admin_users.router, tags=["admin"])
api_router.include_router(instruments.router, tags=["market"])
api_router.include_router(intraday.router, tags=["intraday"])
api_router.include_router(watchlist.router, tags=["watchlist"])
api_router.include_router(monitor.router, tags=["monitor"])
api_router.include_router(market.router, tags=["market"])
api_router.include_router(app_mobile.router, tags=["app-mobile"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(ai.router, tags=["ai"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(screeners.router, tags=["screeners"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(agent.router, tags=["agent"])
api_router.include_router(paper.router, tags=["paper"])
api_router.include_router(feishu.router, tags=["feishu"])
api_router.include_router(v1.router, tags=["v1"])
