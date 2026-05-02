from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.schema_defs.analysis import AiInsight


AiDecisionTask = Literal[
    "stock_explain",
    "daily_review",
    "strategy_attribution",
    "priority_board_summary",
]


class AiDecisionSupportRequest(BaseModel):
    task: AiDecisionTask
    title: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    include_ai: bool = True


class AiDecisionFixedSections(BaseModel):
    can_buy: str = "等到价格"
    why: str = "按量化硬规则执行，不放宽买点。"
    main_risk: str = "未到买点或止损失守时不处理。"
    tomorrow_plan: str = "明天继续按买点、止损和仓位执行。"


class AiDecisionSupportResponse(BaseModel):
    task: AiDecisionTask
    title: str
    insight: AiInsight
    model: str = ""
    provider: str = "auto"
    fixed_sections: AiDecisionFixedSections = AiDecisionFixedSections()
