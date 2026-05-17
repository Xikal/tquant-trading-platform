from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.schemas import (
    LowBuyDailyDecisionOut,
    LowBuyPriorityBoardItemOut,
    LowBuySimpleBucketOut,
)
from app.services.low_buy.holding_policy import strategy_exit_plan_text, strategy_max_holding_days
from app.services.low_buy.strategy_policy import strategy_layer

BLOCKED_MARKETS = frozenset({"risk_release", "high_flyer_retreat"})
CAUTIOUS_MARKETS = frozenset({"fast_rotation", "weight_support", "low_volume_wait"})
GOOD_MARKETS = frozenset({"broad_rally", "repair", "neutral"})

BUCKET_LABELS = {
    "buy_now": ("确定可买", "价格和结构已经满足，只看前排并控制仓位。"),
    "wait_price": ("等到价格", "结构还可以，但必须等价格到买点或承接确认。"),
    "give_up": ("放弃观察", "没有达到执行条件，先不参与。"),
}

MARKET_PLAIN_TEXT = {
    "broad_rally": "强势主升，可提高关注",
    "repair": "弱势修复，只适合小仓试错",
    "fast_rotation": "轮动太快，只做最强主线",
    "weight_support": "指数被权重托住，题材股别追高",
    "high_flyer_retreat": "高位退潮，先别买",
    "risk_release": "风险释放中，空仓等待",
    "low_volume_wait": "缩量无主线，等放量确认",
    "neutral": "环境一般，小仓观察",
}


class BoardLike(Protocol):
    market_state: str
    immediate_count: int
    focus_count: int
    track_count: int


@dataclass(frozen=True)
class RecommendationWindow:
    days: int
    max_days: int
    remaining_days: int


def market_plain_text(market_state: str) -> str:
    return MARKET_PLAIN_TEXT.get(market_state or "neutral", "环境一般，小仓观察")


def simple_bucket_key(item: LowBuyPriorityBoardItemOut) -> str:
    if item.buy_signal_state in {"buy_now", "soft_buy_now"} and strategy_layer(item.strategy_key) == "production":
        return "buy_now"
    if item.buy_signal_state in {"observe_confirmed", "near_entry"}:
        return "wait_price"
    return "give_up"


def simple_bucket_text(bucket_key: str) -> str:
    return BUCKET_LABELS.get(bucket_key, BUCKET_LABELS["give_up"])[0]


def next_action_text(item: LowBuyPriorityBoardItemOut) -> str:
    bucket = simple_bucket_key(item)
    if bucket == "buy_now":
        position = item.suggested_position_pct
        position_text = f"先试 {position:.1f}% 仓位" if position > 0 else "先小仓试错"
        return f"价格在买点区内，{position_text}，跌破止损立即退出。"
    if bucket == "wait_price":
        if item.next_watch_price:
            return f"等回到 {item.next_watch_price:.3f} 附近，并出现止跌再考虑。"
        return "等价格进入买点区，并出现止跌承接再考虑。"
    if item.buy_signal_state == "avoid":
        return item.blocked_reason or "风险不合格，今天不处理。"
    return "只记录，不追高，不提前买。"


def exit_plan_text(item: LowBuyPriorityBoardItemOut) -> str:
    return strategy_exit_plan_text(item.strategy_key, item.stop_loss)


def recommendation_window_text(
    *,
    strategy_title: str,
    recommendation_days: int,
    max_holding_days: int,
) -> str:
    if recommendation_days <= 0:
        return ""
    window = _recommendation_window(recommendation_days, max_holding_days)
    if window.remaining_days <= 0:
        return f"{strategy_title}第 {window.days} 天，已达到建议验证窗口 {window.max_days} 天；未转强应降级或退出。"
    return f"{strategy_title}第 {window.days} 天，建议验证窗口 {window.max_days} 天；剩余 {window.remaining_days} 天。"


def build_daily_decision(board: BoardLike) -> LowBuyDailyDecisionOut:
    market_state = board.market_state or "neutral"
    plain_text = market_plain_text(market_state)
    if market_state in BLOCKED_MARKETS:
        return LowBuyDailyDecisionOut(
            key="wait",
            title="空仓等待",
            message="今天不适合新开仓，优先处理持仓或空仓等待。",
            market_plain_text=plain_text,
            risk_level="high",
            action_steps=["不新增买入", "持仓只按止损和减仓规则处理", "等待市场转修复"],
        )
    if board.immediate_count > 0 and market_state in GOOD_MARKETS:
        return LowBuyDailyDecisionOut(
            key="tradable",
            title="可交易",
            message="今天可以小仓试错，只看确定可买里的前 1-3 只。",
            market_plain_text=plain_text,
            risk_level="low" if market_state == "broad_rally" else "medium",
            action_steps=["只看确定可买", "先小仓", "提前设好止损"],
        )
    if board.focus_count > 0 or board.track_count > 0 or market_state in CAUTIOUS_MARKETS:
        return LowBuyDailyDecisionOut(
            key="observe_only",
            title="只观察",
            message="今天先等价格和承接，不追高，不提前买。",
            market_plain_text=plain_text,
            risk_level="medium",
            action_steps=["等价格到买点", "等止跌确认", "不追高"],
        )
    return LowBuyDailyDecisionOut(
        key="wait",
        title="空仓等待",
        message="今天没有明确机会，不适合新开仓。",
        market_plain_text=plain_text,
        risk_level="medium",
        action_steps=["等待下一轮信号", "复查持仓风险"],
    )


def build_simple_buckets(items: list[LowBuyPriorityBoardItemOut]) -> list[LowBuySimpleBucketOut]:
    grouped = {"buy_now": [], "wait_price": [], "give_up": []}
    for item in items:
        grouped[simple_bucket_key(item)].append(item.symbol)
    return [
        LowBuySimpleBucketOut(
            key=key,  # type: ignore[arg-type]
            title=BUCKET_LABELS[key][0],
            description=BUCKET_LABELS[key][1],
            count=len(symbols),
            symbols=symbols[:10],
        )
        for key, symbols in grouped.items()
    ]


def enrich_priority_item(item: LowBuyPriorityBoardItemOut) -> LowBuyPriorityBoardItemOut:
    bucket = simple_bucket_key(item)
    duration_text = recommendation_window_text(
        strategy_title=item.strategy_title,
        recommendation_days=int(item.recommendation_days or 0),
        max_holding_days=strategy_max_holding_days(item.strategy_key),
    )
    return item.model_copy(
        update={
            "simple_bucket": bucket,
            "simple_bucket_text": simple_bucket_text(bucket),
            "next_action_text": next_action_text(item),
            "exit_plan_text": exit_plan_text(item),
            "recommendation_duration_text": duration_text or item.recommendation_duration_text,
        }
    )


def enrich_priority_items(items: list[LowBuyPriorityBoardItemOut]) -> list[LowBuyPriorityBoardItemOut]:
    return [enrich_priority_item(item) for item in items]


def _recommendation_window(recommendation_days: int, max_holding_days: int) -> RecommendationWindow:
    days = max(int(recommendation_days or 0), 0)
    max_days = max(int(max_holding_days or 0), 1)
    return RecommendationWindow(days=days, max_days=max_days, remaining_days=max(max_days - days, 0))
