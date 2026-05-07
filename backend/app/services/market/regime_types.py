from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketBreadthSnapshot:
    breadth_ready: bool
    stock_up_ratio: float
    stock_median_change: float
    largecap_change: float
    smallcap_change: float
    style_divergence: float
    hot_turnover: float
    hot_overlap_ratio: float


@dataclass(frozen=True)
class MarketRegimeSnapshot:
    state: str
    label: str
    description: str
    ranking_bonus: float
    position_multiplier: float
    buy_signal_penalty: float
    t_threshold_shift: float
    positive_threshold_shift: float
    negative_threshold_shift: float
    hot_industries: list[str]
    hot_industry_source: str
    hot_industry_source_text: str
    limit_down_count: int | None
    breadth_ready: bool
    emotion_ready: bool
    positive_industry_ratio: float
    top3_avg_change: float
    median_change: float
    defensive_lead: bool
    stock_up_ratio: float
    stock_median_change: float
    largecap_change: float
    smallcap_change: float
    style_divergence: float
    hot_turnover: float
    limit_up_count: int
    previous_limit_up_count: int
    board_height: int
    previous_board_height: int
    promotion_ratio: float
    broken_board_ratio: float
    promotion_break_gap: float
    promotion_break_pressure: float
    high_flyer_retreat_ratio: float
    high_flyer_gap_speed: float
    hot_overlap_ratio: float
    distribution_pressure: float
    mainline_lifecycle_state: str
    mainline_lifecycle_text: str
    state_strength: float
    regime_score: float
    regime_confidence: float = 0.0
    state_persistence_days: int = 1
    transition_risk: float = 0.0
    snapshot_source: str = "live"
    snapshot_source_text: str = "实时市场快照"


STATE_CONFIG = {
    "broad_rally": {
        "label": "强势主升",
        "description": "行业和个股广度同时走强，主策略可以更积极，但仍保留确认门槛。",
        "ranking_bonus": 4.0,
        "position_multiplier": 1.15,
        "buy_signal_penalty": -2.0,
        "t_threshold_shift": -0.18,
        "positive_threshold_shift": -2.0,
        "negative_threshold_shift": -2.0,
    },
    "weight_support": {
        "label": "震荡轮动",
        "description": "指数可能被权重支撑或热点快速切换，优先做结构票，情绪后排明显降级。",
        "ranking_bonus": -4.0,
        "position_multiplier": 0.65,
        "buy_signal_penalty": 2.5,
        "t_threshold_shift": 0.22,
        "positive_threshold_shift": 4.0,
        "negative_threshold_shift": 4.5,
    },
    "weight_support_active": {
        "label": "震荡轮动-题材活跃",
        "description": "权重稳指数但题材仍有活口，主策略保留，情绪型只留最强确认。",
        "ranking_bonus": -1.2,
        "position_multiplier": 0.82,
        "buy_signal_penalty": 1.0,
        "t_threshold_shift": 0.10,
        "positive_threshold_shift": 1.5,
        "negative_threshold_shift": 2.0,
    },
    "low_volume_wait": {
        "label": "缩量无主线",
        "description": "量能不足、扩散不够且主线不清晰，适合降仓等待，而不是激进出手。",
        "ranking_bonus": -2.0,
        "position_multiplier": 0.75,
        "buy_signal_penalty": 1.5,
        "t_threshold_shift": 0.12,
        "positive_threshold_shift": 2.0,
        "negative_threshold_shift": 2.0,
    },
    "fast_rotation": {
        "label": "轮动过快",
        "description": "热点切换过快，追逐情绪容易失真，优先保留承接更清楚的票。",
        "ranking_bonus": -2.5,
        "position_multiplier": 0.72,
        "buy_signal_penalty": 2.0,
        "t_threshold_shift": 0.15,
        "positive_threshold_shift": 2.5,
        "negative_threshold_shift": 3.0,
    },
    "high_flyer_retreat": {
        "label": "下跌退潮",
        "description": "高位股补跌和退潮显性化，情绪票买点必须显著收紧。",
        "ranking_bonus": -5.0,
        "position_multiplier": 0.55,
        "buy_signal_penalty": 3.5,
        "t_threshold_shift": 0.24,
        "positive_threshold_shift": 4.0,
        "negative_threshold_shift": 4.0,
    },
    "repair": {
        "label": "弱势修复",
        "description": "市场从弱势中修复，但还没进入真正强势主升，优先处理强结构票。",
        "ranking_bonus": 1.5,
        "position_multiplier": 0.95,
        "buy_signal_penalty": -0.5,
        "t_threshold_shift": -0.05,
        "positive_threshold_shift": -1.0,
        "negative_threshold_shift": -1.0,
    },
    "risk_release": {
        "label": "极端风险",
        "description": "市场处于显性风险释放期，新开仓和追逐型做T都应明显收缩。",
        "ranking_bonus": -7.0,
        "position_multiplier": 0.40,
        "buy_signal_penalty": 5.0,
        "t_threshold_shift": 0.35,
        "positive_threshold_shift": 5.0,
        "negative_threshold_shift": 5.0,
    },
}


DEFENSIVE_KEYWORDS = (
    "银行",
    "保险",
    "石油",
    "煤炭",
    "运营商",
    "电力",
    "贵金属",
)


STYLE_PROXY_GROUPS = {
    "large": ("510300", "510050"),
    "small": ("512100", "159915"),
}
