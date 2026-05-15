from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.market_data import MarketDataService


class AppMobileInstrumentMixin:
    def search_instruments(
        self,
        db: Session,
        *,
        keyword: str = "",
        kind: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        market_data = MarketDataService()
        if market_data.get_total_instruments(db, kind="all") == 0:
            try:
                market_data.sync_instruments(db, "all")
            except Exception:
                # 移动端搜索不应因冷启动同步失败直接报错，继续走本地已落库数据。
                pass
        items = market_data.search_instruments(
            db,
            keyword=keyword,
            kind=kind,
            page=page,
            page_size=page_size,
        )
        total = market_data.get_total_instruments(db, kind=kind)
        return {
            "items": [item.model_dump() for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
