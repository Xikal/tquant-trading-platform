from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import paper_account, paper_auto_trading, paper_orders, paper_performance

router = APIRouter(prefix="/paper")
router.include_router(paper_account.router)
router.include_router(paper_orders.router)
router.include_router(paper_performance.router)
router.include_router(paper_auto_trading.router)
