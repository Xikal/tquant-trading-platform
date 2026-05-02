from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import (
    DailyBarSnapshot,
    LowBuyPoolSnapshot,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    LowBuyStrategyPerformanceSnapshot,
    LowBuyStrategyPerformanceWindowSnapshot,
    SystemSetting,
)
from app.models.schemas import (
    LowBuyCandidateOut,
    LowBuyCloseReviewItemOut,
    LowBuyHistoryResponse,
    LowBuyHistorySectionOut,
    LowBuyPerformanceBucketOut,
    LowBuyQuoteRefreshOut,
    LowBuyScreenerResponse,
    LowBuyStrategyPerformanceOut,
)
from app.services.market_data import DataSourceError, MarketDataService, guess_market
from app.services.settings_service import SettingsService

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


@dataclass
class BoardCandidate:
    symbol: str
    name: str
    board_date: str
    board_count: int
    amount: float
    industry: str


@dataclass(frozen=True)
class LowBuyThresholds:
    """低吸策略集中阈值配置。"""

    STOP_LOSS_HARD_MULTIPLIER: float = 0.988
    STOP_LOSS_SOFT_MULTIPLIER: float = 0.992
    STOP_LOSS_DIVERGENCE_MULTIPLIER: float = 0.985
    ENTRY_ZONE_HALF_WIDTH_PCT: float = 0.008
    ENTRY_ZONE_TOLERANCE_PCT: float = 0.015
    CORE_TIER_WEIGHT: float = 1.0
    AUXILIARY_TIER_WEIGHT: float = 0.65
    MAX_FACTOR_BONUS: float = 8.0
    DEEP_PULLBACK_NON_CORE_POSITION_CAP: float = 10.0
    MIN_DAILY_AMOUNT_CORE: float = 50_000_000.0
    MIN_DAILY_AMOUNT_AUXILIARY: float = 30_000_000.0
    PULLBACK_HEALTH_OPTIMAL_DAYS: tuple[int, int] = (3, 4)
    PULLBACK_HEALTH_MAX_SCORE: float = 94.0
    PULLBACK_HEALTH_MIN_SCORE: float = 48.0
    PULLBACK_HEALTH_DAY_DECAY: float = 9.0
    TREND_FATIGUE_STRONG_TREND_BLOCK: float = 6.0
    MIN_SIGNAL_SCORE_BUY: int = 75
    MIN_TRADABILITY_SCORE_BUY: int = 70
    MIN_SAMPLE_SIZE_RELIABLE: int = 30
    MIN_SAMPLE_SIZE_DISPLAY: int = 20
    NEW_STRATEGY_AGE_DAYS: int = 90
    NEW_STRATEGY_WEIGHT_REDUCTION: float = 0.5
    MAX_SYMBOLS_QUOTE_REFRESH: int = 60
    QUOTE_REFRESH_INTERVAL_TIER1: int = 30
    QUOTE_REFRESH_INTERVAL_TIER2: int = 60
    QUOTE_REFRESH_INTERVAL_TIER3: int = 120
    FACTOR_WEIGHTS: dict[str, float] = field(
        default_factory=lambda: {
            "deep_pullback_factor": 1.0,
            "trend_rebound_factor": 0.8,
            "sector_density_factor": 1.2,
            "shrink_quality_factor": 1.0,
            "gap_risk_factor": 1.5,
            "volatility_regime_factor": 0.7,
            "time_efficiency_factor": 0.6,
            "signal_freshness_factor": 0.5,
            "sector_flow_factor": 0.7,
            "big_order_flow_factor": 0.4,
            "price_structure_factor": 0.9,
            "event_risk_factor": 0.6,
            "absorption_quality_factor": 0.5,
        }
    )


LOW_BUY_THRESHOLDS = LowBuyThresholds()


DEFAULT_PRODUCTION_LOW_BUY_STRATEGY = "first_board"


PLAYBOOKS: dict[str, dict[str, Any]] = {
    "classic_retrace": {
        "title": "原始低吸法",
        "subtitle": "历史研究 · 十日涨停 + 缩量回踩 + 均线支撑",
        "logic": "只看近十日强势启动后的缩量回踩，先确认结构，再等价格进入低吸区。",
        "notes": [
            "十日内有涨停启动，回调 2-4 天最优。",
            "回踩 5 日或 10 日线附近，量能持续萎缩。",
            "价格进入低吸区后，才会切换成确定买入。",
        ],
    },
    "ma_support": {
        "title": "均线支撑",
        "subtitle": "辅助因子 · 回踩 5/10/20 日线，只做上升趋势票",
        "logic": "只抓回踩关键均线的强势股，不做跌破趋势线的下跌中继。",
        "notes": [
            "5/10 日线优先，20 日线仅用于波段承接。",
            "股价必须仍站在 20/60 日线上方，均线多头排列。",
            "未到买点区之前一律只标记为继续观察。",
        ],
    },
    "first_board": {
        "title": "首板回调",
        "subtitle": "核心生产 · 首板后第一次健康回踩",
        "logic": "只看首板后的第一次回踩，核心是守住首板关键价，不接转弱票。",
        "notes": [
            "优先首板，不做高连板高位接力。",
            "回踩不能破首板低点或关键开盘价。",
            "价格回到买点区时才显示确定买入。",
        ],
    },
    "volume_shrink": {
        "title": "量能低吸",
        "subtitle": "核心生产 · 启动放量，回调缩量，量价关系最好",
        "logic": "利用放量启动后的缩量回踩结构，专抓主力建仓后洗盘。",
        "notes": [
            "启动日量能必须明显高于前 5 日均量。",
            "回调过程量能阶梯式收缩，不能再次放量杀跌。",
            "到价前不追，缩量和位置同时满足再动手。",
        ],
    },
    "late_session_strong_support": {
        "title": "收盘强势承接",
        "subtitle": "生产观察 · 日线强收盘 + 盘中均价确认，次日冲高兑现",
        "logic": "先用日线收盘位置和量能选出强承接候选，盘中再看分时均价和尾盘是否转弱，只做隔日惯性冲高。",
        "notes": [
            "候选来自日线收盘强度，执行前必须补看分时均价或尾盘承接。",
            "次日冲高 1.5%-3% 优先兑现，最晚 T+2 退出。",
            "板块退潮、收盘转弱或长上影弱收，一律放弃。",
        ],
    },
    "core_midcap_vwap_ma5_retrace": {
        "title": "中军VWAP/均线回踩",
        "subtitle": "生产观察 · 主线中军回踩 5/10 日线，盘中站回 VWAP 才执行",
        "logic": "只做主线板块容量核心股第一次健康回踩 5 日线或 10 日线后的 1-2 日修复；日线先入池，盘中必须重新站回分时均价并有低点抬高。",
        "notes": [
            "个股成交额要大，趋势不能破，回踩不能放量破位。",
            "靠近 5 日线或 10 日线后，只在分时均价确认承接时小仓执行。",
            "次日没有修复或跌破 5 日线，立即退出。",
        ],
    },
    "sector_mainline_first_divergence_low_buy": {
        "title": "主线首分歧低吸",
        "subtitle": "生产观察 · 板块主线第一次分歧，只做核心前排",
        "logic": "在主线板块首次分歧释放时，只低吸龙头、强跟随或容量中军，博弈资金回流。",
        "notes": [
            "必须是强主线或次主线，后排杂毛不做。",
            "只做第一次健康分歧，连续分歧或退潮不接。",
            "收盘承接或次日弱转强确认，仓位轻，失败立即退出。",
        ],
    },
    "breakout_support": {
        "title": "位置支撑",
        "subtitle": "辅助因子 · 突破前高/缺口后回踩不破",
        "logic": "只看突破后的前高支撑、箱体下沿和关键缺口，不接失守支撑的票。",
        "notes": [
            "突破位回踩不破才有低吸价值。",
            "越靠近关键支撑，盈亏比越高。",
            "跌破支撑位就取消计划，不做猜底。",
        ],
    },
    "limit_up_breakout_retrace": {
        "title": "涨停突破回踩",
        "subtitle": "研究验证 · 平台突破 + 缩量洗盘 + 二次转强",
        "logic": "只做低位平台放量涨停突破后的首轮缩量回踩，必须在关键位止跌并二次转强。",
        "notes": [
            "必须先有 20-60 日平台整理，再出现放量涨停突破。",
            "回调只接受 1-5 日缩量洗盘，不接受放量阴跌或跌回平台内部。",
            "信号宁可少，也只在关键支撑位止跌后再给确定买入。",
        ],
    },
    "divergence_consensus": {
        "title": "分歧转一致",
        "subtitle": "研究验证 · 底部涨停 + 分歧缩量 + 倍量突破",
        "logic": "先识别底部放量涨停，再观察巨量分歧后的缩量横盘，只在放量阳线突破分歧高点时给右侧确认。",
        "notes": [
            "必须先有低位平台和首板放量启动，不追涨停当天。",
            "涨停后需要出现分歧沉淀，横盘缩量不能演变成放量下跌。",
            "买点只认放量阳线突破巨量分歧高点，跌回横盘下沿即失效。",
        ],
    },
    "deep_pullback": {
        "title": "深度低吸",
        "subtitle": "已降级为因子 · 龙头错杀回撤，风险更高",
        "logic": "只做强趋势股的错杀回撤，不做普通弱势票的深跌接刀。",
        "notes": [
            "回撤通常在 -3% 到 -8% 区间，高风险高波动。",
            "必须仍在 20 日线附近，且量能没有失控放大。",
            "一旦跌破止损线，直接放弃，不加仓硬扛。",
        ],
    },
    "trend_rebound": {
        "title": "趋势龙回头",
        "subtitle": "已降级为因子 · N 字回拉 / 龙头回头",
        "logic": "只做上升趋势中的二次上攻预备段，核心是趋势没坏、回踩有承接。",
        "notes": [
            "前面必须已经有明显主升浪或大阳启动。",
            "回调后仍在 10 日、20 日线之上，趋势不破。",
            "价格到位后才发出确定买入，不追高。",
        ],
    },
}

STRATEGY_ALIASES: dict[str, str] = {
    # Backward-compatible keys used by older web/app bundles.
    "volume_pullback": "volume_shrink",
    "position_support": "breakout_support",
    "dragon_head_retrace": "trend_rebound",
}


def normalize_low_buy_strategy(strategy: str | None) -> str:
    cleaned = (strategy or DEFAULT_PRODUCTION_LOW_BUY_STRATEGY).strip()
    return STRATEGY_ALIASES.get(cleaned, cleaned)

PERFORMANCE_LOOKBACK_DAYS = 60
RECENT_PERFORMANCE_LOOKBACK_DAYS = 20
PERFORMANCE_FORWARD_DAYS = 5
LOW_BUY_PERFORMANCE_SNAPSHOT_VERSION = 6
INTRADAY_STRUCTURE_START_HOUR = 10
INTRADAY_STRUCTURE_START_MINUTE = 30
LOW_BUY_RESULT_VERSION = 8
