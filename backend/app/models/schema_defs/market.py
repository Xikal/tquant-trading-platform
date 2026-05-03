from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MarketBreadthResponse(BaseModel):
    updated_at: str
    state: str = ""
    state_text: str = ""
    breadth_ready: bool = False
    emotion_ready: bool = False
    stock_up_ratio: float = 0.0
    stock_median_change: float = 0.0
    largecap_change: float = 0.0
    smallcap_change: float = 0.0
    style_divergence: float = 0.0
    limit_up_count: int = 0
    limit_down_count: Optional[int] = None
    broken_board_ratio: float = 0.0
    promotion_ratio: float = 0.0
    board_height: int = 0
    hot_industries: list[str] = Field(default_factory=list)
    hot_turnover: float = 0.0
    hot_overlap_ratio: float = 0.0
    data_quality_text: str = ""
