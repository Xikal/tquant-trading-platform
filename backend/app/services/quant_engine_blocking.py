from __future__ import annotations

from typing import Any

from app.models.schemas import QuoteSnapshot
from app.services.quant_engine_common import config_float, has_invalid_trade_snapshot, price_limit_pct


def hard_blocking_rules(
    quote: QuoteSnapshot,
    amplitude: float,
    atr_value: float,
    tradability_score: float,
    event_penalty_value: float,
    scenario: str,
    has_latest_bar: bool,
    risk_config: dict[str, Any],
) -> list[str]:
    rules: list[str] = []
    if scenario == "pre_open_auction":
        rules.append("当前处于开盘前/集合竞价阶段，建议等待 09:30 后连续竞价再做T。")
        return rules
    if has_invalid_trade_snapshot(quote):
        if scenario == "open_price_discovery" and quote.last_price <= 0 and quote.amount <= 0 and quote.volume <= 0:
            rules.append("当前处于开盘前/集合竞价阶段，免费行情尚未形成有效成交快照。")
        else:
            rules.append("行情数据异常，无法计算有效交易区间。")
        return rules
    if not has_latest_bar:
        rules.append("分钟线不足，无法完成分时做T判断。")
    if tradability_score < 42:
        rules.append("当前流动性/振幅不足，不适合高频做T。")

    min_amount = (
        config_float(risk_config, "strategy_min_amount_stock", 30_000_000.0)
        if quote.instrument_type == "stock"
        else config_float(risk_config, "strategy_min_amount_etf", 15_000_000.0)
    )
    if quote.amount < min_amount:
        rules.append(f"当前成交额低于 {int(min_amount/1_0000)} 万，暂不建议做T。")
    if amplitude < config_float(risk_config, "strategy_min_amplitude_pct", 0.6):
        rules.append("日内振幅过窄，价差空间不足。")
    if amplitude >= config_float(risk_config, "strategy_max_amplitude_pct", 15.0):
        rules.append("日内振幅过大，波动超出做T安全区间。")
    atr_ratio = atr_value / max(quote.last_price, 0.01) * 100
    if atr_ratio >= config_float(risk_config, "strategy_max_atr_pct", 4.0):
        rules.append("波动率过高，当前不适合执行做T。")

    limit_pct = price_limit_pct(
        quote.symbol,
        quote.instrument_type,
        is_st=str(quote.name or "").upper().startswith(("ST", "*ST")),
    )
    if limit_pct > 0 and abs(quote.change_pct) >= limit_pct * 0.9:
        rules.append("标的接近涨跌停限制，成交与回转风险较高。")
    open_phase_min = config_float(risk_config, "strategy_open_phase_min_tradability", 60.0)
    if scenario == "open_price_discovery" and tradability_score < open_phase_min:
        rules.append("开盘定价阶段噪声较大，建议等待结构稳定后再参与。")
    if event_penalty_value >= 25:
        rules.append("事件风险偏高，建议缩量或观望。")
    return rules
