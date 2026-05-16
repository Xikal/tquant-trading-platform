from __future__ import annotations

from app.models.schema_defs.factor_mining import FactorHypothesisOut

_TOPICS = [
    ("vwap_discount_reversal", "分时 VWAP 折价反弹", "价格低于 VWAP 后缩量企稳，短线反弹概率提升", ["close_price", "volume", "amount"]),
    ("volume_dryup_quality", "连续缩量质量", "连续缩量但收盘未破位，说明抛压衰减", ["close_price", "volume"]),
    ("limitup_retrace_strength", "涨停后缩量回调强度", "涨停后低量回踩且不破 MA10，动能延续", ["close_price", "high_price", "volume"]),
    ("late_money_strength", "尾盘资金强度", "尾盘成交占比提升且价格不回落，暗示次日承接", ["close_price", "amount"]),
    ("ma20_reclaim_power", "MA20 收复力度", "回踩后快速收复 MA20，支撑有效", ["close_price", "low_price"]),
    ("low_point_rising", "分时低点抬高", "回调低点逐步抬升，洗盘概率高于出货", ["low_price", "close_price"]),
    ("gap_risk_absorption", "跳空风险吸收", "缺口后低位震荡且成交缩小，恐慌释放接近尾声", ["open_price", "close_price", "volume"]),
    ("sector_relative_strength", "板块相对强弱", "个股回调幅度小于板块，说明相对承接强", ["close_price", "pct_chg"]),
    ("turnover_cooling", "换手降温质量", "高换手后温和降温，筹码交换更充分", ["volume", "amount"]),
    ("pre_limitup_accumulation", "涨停前预热结构", "涨停前多日小阳放量，资金提前埋伏", ["open_price", "close_price", "volume"]),
]


def local_hypotheses(topic: str, count: int) -> list[FactorHypothesisOut]:
    topic_text = topic.strip() or "A股短线低吸"
    items: list[FactorHypothesisOut] = []
    categories = ["price", "volume", "sentiment", "event", "sector"]
    for index in range(count):
        key, name, base_hypothesis, deps = _TOPICS[index % len(_TOPICS)]
        suffix = index // len(_TOPICS) + 1
        factor_key = f"{key}_{suffix}" if suffix > 1 else key
        items.append(
            FactorHypothesisOut(
                factor_name=f"{name}{'' if suffix == 1 else f' #{suffix}'}",
                factor_key=factor_key,
                hypothesis=f"{base_hypothesis}。研究主题：{topic_text}。",
                data_deps=deps,
                direction="higher_better",
                category=categories[index % len(categories)],
                limitations=["需要严格使用 T 日以前数据", "必须经过样本外验证", "不应直接进入生产交易"],
                source="local_template",
            )
        )
    return items


def synth_formula_for_hypothesis(factor_key: str) -> str:
    key = factor_key.lower()
    if "vwap" in key:
        return _FORMULA_VWAP_DISCOUNT
    if "volume" in key or "dryup" in key or "turnover" in key:
        return _FORMULA_VOLUME_DRYUP
    if "ma20" in key or "reclaim" in key:
        return _FORMULA_MA20_RECLAIM
    return _FORMULA_PRICE_VOLUME_BALANCE


_FORMULA_VWAP_DISCOUNT = """
def compute_factor(bars):
    close = bars["close_price"].astype(float)
    amount = bars["amount"].astype(float)
    volume = bars["volume"].astype(float).replace(0, np.nan)
    vwap = (amount / volume).replace([np.inf, -np.inf], np.nan)
    discount = (vwap.shift(1) - close) / vwap.shift(1).replace(0, np.nan)
    stability = close.pct_change().rolling(3, min_periods=2).std().fillna(0.0)
    return (discount - stability).replace([np.inf, -np.inf], np.nan).fillna(0.0)
""".strip()

_FORMULA_VOLUME_DRYUP = """
def compute_factor(bars):
    close = bars["close_price"].astype(float)
    volume = bars["volume"].astype(float)
    vol_ma5 = volume.rolling(5, min_periods=3).mean().shift(1)
    dryup = 1.0 - volume / vol_ma5.replace(0, np.nan)
    support = close / close.rolling(10, min_periods=5).mean().shift(1) - 1.0
    return (dryup - support.abs()).replace([np.inf, -np.inf], np.nan).fillna(0.0)
""".strip()

_FORMULA_MA20_RECLAIM = """
def compute_factor(bars):
    close = bars["close_price"].astype(float)
    low = bars["low_price"].astype(float)
    ma20 = close.rolling(20, min_periods=10).mean().shift(1)
    reclaim = close / ma20.replace(0, np.nan) - 1.0
    drawdown = low / close.rolling(20, min_periods=10).max().shift(1).replace(0, np.nan) - 1.0
    return (reclaim - drawdown.abs() * 0.3).replace([np.inf, -np.inf], np.nan).fillna(0.0)
""".strip()

_FORMULA_PRICE_VOLUME_BALANCE = """
def compute_factor(bars):
    close = bars["close_price"].astype(float)
    volume = bars["volume"].astype(float)
    momentum = close.pct_change(5).shift(1)
    vol_slope = volume.pct_change(5).shift(1)
    return (momentum - vol_slope.abs() * 0.2).replace([np.inf, -np.inf], np.nan).fillna(0.0)
""".strip()
