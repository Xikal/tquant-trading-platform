from __future__ import annotations

from app.models.schemas import MicrostructureSnapshot, QuoteSnapshot, SectorSnapshot
from app.services.distribution_signals import DistributionSnapshot
from app.services.market.regime import MarketRegimeSnapshot
from app.services.quant_engine_execution_params import (
    asset_bucket as _asset_bucket,
    bucket_state_params as _bucket_state_params,
    direction_gate_params as _direction_gate_params,
    list_param as _list_param,
    param_float as _param_float,
)


def positive_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    ma20: float,
    slope10: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    params = _direction_gate_params("positive")
    gate = _bucket_state_params(params, asset_bucket, state)
    price_extension_limit = _param_float(gate, "price_extension_limit", 1.035)
    weak_vwap_limit = _param_float(gate, "weak_vwap_limit", 0.992)
    slope_floor = _param_float(gate, "slope_floor", -0.26)
    weak_sector_floor = _param_float(gate, "weak_sector_floor", 44.0)
    weak_buy_pressure_floor = _param_float(gate, "weak_buy_pressure_floor", 44.0)
    distribution_reason = _positive_distribution_block(
        asset_bucket=asset_bucket,
        state=state,
        distribution=distribution,
    )
    if distribution_reason:
        return False, distribution_reason
    if _thematic_positive_state_block(
        asset_bucket=asset_bucket,
        state=state,
        sector=sector,
        microstructure=microstructure,
    ):
        return False, "题材股处在退潮/快速轮动环境，必须等板块和买盘同时转强后再考虑先买后卖。"
    if intraday_structure != str(params.get("required_structure") or "pullback_acceptance"):
        return False, "先买后卖只做回落后有人接盘：必须先靠近分时均价线或5日线，再重新站回分时均价线，且短线低点抬高、回落时成交量缩小。"
    if quote.last_price < vwap_value * _param_float(params, "reclaim_vwap_multiplier", 1.001):
        return False, "需要重新站回分时均价线后再考虑先买后卖。"
    if quote.last_price > ma5 * price_extension_limit:
        return False, "价格离5日线已经偏远，不建议追着买。"
    if quote.last_price < ma20 * _param_float(params, "ma20_floor_multiplier", 0.992):
        return False, "价格已经跌到20日线下方，当前不适合先买后卖。"
    if slope10 < slope_floor:
        return False, "短线趋势转弱，先买后卖的成功条件不足。"
    weak_sector = sector.alignment_score < weak_sector_floor
    if asset_bucket == "weight_stock":
        weak_sector = weak_sector and state not in set(
            _list_param(params, "weight_stock_support_states") or ["weight_support", "weight_support_active"]
        )
    weak_buy_pressure = microstructure.available and microstructure.buy_pressure < weak_buy_pressure_floor
    weak_vwap = quote.last_price < vwap_value * weak_vwap_limit
    if weak_sector and weak_buy_pressure:
        return False, "板块联动和买盘承接同时偏弱，先买后卖成功率不足。"
    if weak_vwap and slope10 < _param_float(params, "weak_vwap_slope_floor", -0.12):
        return False, "价格仍弱于分时均价线，先等回到均价附近再考虑先买后卖。"
    return True, ""


def positive_light_direction_gate(
    quote: QuoteSnapshot,
    ma5: float,
    ma20: float,
    slope10: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if asset_bucket == "thematic_stock" and state in {"high_flyer_retreat", "risk_release"}:
        return False, "退潮或风险释放时，题材股不放宽先买后卖条件。"
    if distribution.false_breakout_flag or distribution.distribution_risk_score >= (7.6 if asset_bucket == "etf" else 6.4):
        return False, "出货或假突破风险偏高，不能放宽先买后卖。"
    if intraday_structure not in {"pullback_acceptance", "sharp_drop_repair"}:
        return False, "小仓试做只接受回落有人接盘，或急跌后重新收回分时均价线的结构。"
    if quote.last_price < vwap_value * (0.999 if asset_bucket == "etf" else 1.0):
        return False, "小仓试做也必须至少回到分时均价线附近。"
    if quote.last_price > ma5 * (1.045 if asset_bucket == "etf" else 1.032):
        return False, "价格离5日线过远，小仓也不追。"
    if quote.last_price < ma20 * 0.985:
        return False, "价格弱于20日线，小仓试做的成功率不足。"
    if slope10 < (-0.36 if asset_bucket == "etf" else -0.22):
        return False, "短线斜率仍偏弱，先等承接继续确认。"
    if sector.alignment_score < (42.0 if asset_bucket != "thematic_stock" else 50.0):
        return False, "板块联动不足，小仓试做不放宽。"
    if microstructure.available and microstructure.buy_pressure < (40.0 if asset_bucket == "etf" else 46.0):
        return False, "买盘承接不足，小仓试做也不放宽。"
    return True, "急跌修复或回落接盘已接近成立，只允许小仓先买后卖，并继续看分时均价线是否守住。"


def positive_prepare_gate(
    quote: QuoteSnapshot,
    ma5: float,
    vwap_value: float,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
    distribution: DistributionSnapshot,
    market_regime: MarketRegimeSnapshot | None = None,
    intraday_structure: str = "",
) -> tuple[bool, str]:
    asset_bucket = _asset_bucket(quote, sector)
    state = market_regime.state if market_regime is not None else "low_volume_wait"
    if asset_bucket == "thematic_stock" and state in {"high_flyer_retreat", "risk_release"}:
        return False, "市场退潮时，非 ETF 只保留严格确认后的先买后卖信号。"
    if distribution.false_breakout_flag or distribution.distribution_risk_score >= 7.5:
        return False, "出货风险偏高，不提前提示先买后卖。"
    anchor = min(ma5, vwap_value)
    near_anchor = anchor > 0 and quote.low_price <= anchor * 1.006 and quote.last_price >= anchor * 0.996
    structure_near = intraday_structure in {"sharp_drop_repair", "range_contraction", "balanced_intraday"}
    if near_anchor and structure_near:
        return True, "价格已靠近分时均价线或5日线支撑区，等重新站稳分时均价线并低点抬高后再先买后卖。"
    if microstructure.available and microstructure.buy_pressure >= 55 and quote.last_price >= vwap_value * 0.997:
        return True, "买盘承接转强但结构还未完全确认，先列为先买后卖预备信号。"
    return False, "先买后卖条件尚未接近。"


def _positive_distribution_block(
    *,
    asset_bucket: str,
    state: str,
    distribution: DistributionSnapshot,
) -> str:
    params = _direction_gate_params("positive_distribution_block")
    if distribution.false_breakout_flag:
        return "分时出现假突破回落，不适合逆着出货迹象追买。"
    reversal_score = _param_float(
        params,
        "etf_reversal_score" if asset_bucket == "etf" else "stock_reversal_score",
        8.2 if asset_bucket == "etf" else 7.0,
    )
    if distribution.intraday_reversal_flag and distribution.distribution_risk_score >= reversal_score:
        return "分时冲高回落明显，先等卖压释放。"
    weak_stall_context = state in set(
        _list_param(params, "weak_stall_states") or ["fast_rotation", "high_flyer_retreat", "risk_release"]
    )
    if distribution.stall_after_volume_flag and asset_bucket == "thematic_stock" and weak_stall_context:
        return "放量但价格涨不动，且市场环境偏弱，先买后卖成功率不足。"
    distribution_score = _param_float(
        params,
        "etf_distribution_score" if asset_bucket == "etf" else "stock_distribution_score",
        8.8 if asset_bucket == "etf" else 7.8,
    )
    if distribution.distribution_risk_score >= distribution_score:
        return "当前出货风险偏高，应等待更强承接。"
    return ""


def _thematic_positive_state_block(
    *,
    asset_bucket: str,
    state: str,
    sector: SectorSnapshot,
    microstructure: MicrostructureSnapshot,
) -> bool:
    params = _direction_gate_params("thematic_state_block")
    blocked_states = set(_list_param(params, "blocked_states") or ["fast_rotation", "high_flyer_retreat", "risk_release"])
    if asset_bucket != "thematic_stock" or state not in blocked_states:
        return False
    if not microstructure.available:
        return sector.alignment_score < _param_float(params, "sector_floor", 55.0)
    return sector.alignment_score < _param_float(params, "sector_floor", 55.0) or microstructure.buy_pressure < _param_float(
        params, "buy_pressure_floor", 55.0
    )
