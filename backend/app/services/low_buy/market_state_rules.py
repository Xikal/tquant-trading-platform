from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LowBuyMarketAdjustment:
    score_penalty: float
    candidate_penalty_weight: float
    position_multiplier: float
    execution_blocked: bool
    market_state_strength: float
    extra_risks: list[str]
    extra_tags: list[str]


@dataclass(frozen=True)
class StrategyMarketProfile:
    score_penalty: float
    candidate_penalty_weight: float
    ranking_bonus: float
    position_multiplier: float
    soft_buy_allowed: bool
    hard_buy_allowed: bool
    execution_blocked: bool
    market_state_strength: float
    notes: list[str]


_NEGATIVE_STATES = {
    "weight_support",
    "weight_support_active",
    "low_volume_wait",
    "fast_rotation",
    "high_flyer_retreat",
    "risk_release",
}
_POSITIVE_STATES = {"broad_rally", "repair"}

_DEFAULT_STATE_RULES: dict[str, dict[str, object]] = {
    "broad_rally": {
        "score_penalty": 0.0,
        "candidate_penalty_weight": 0.18,
        "ranking_bonus": 1.0,
        "position_multiplier": 1.08,
        "soft_buy_allowed": True,
        "hard_buy_allowed": True,
        "soft_max_strength": 1.0,
        "hard_max_strength": 1.0,
        "notes": ["市场扩散明显，确认后的低吸可以更积极处理。"],
    },
    "repair": {
        "score_penalty": 0.8,
        "candidate_penalty_weight": 0.28,
        "ranking_bonus": 0.5,
        "position_multiplier": 0.96,
        "soft_buy_allowed": True,
        "hard_buy_allowed": True,
        "soft_max_strength": 0.92,
        "hard_max_strength": 0.86,
        "notes": ["市场在修复，但广度仍不稳定，优先保留强结构票。"],
    },
    "low_volume_wait": {
        "score_penalty": 1.8,
        "candidate_penalty_weight": 0.42,
        "ranking_bonus": -0.8,
        "position_multiplier": 0.82,
        "soft_buy_allowed": True,
        "hard_buy_allowed": True,
        "soft_max_strength": 0.72,
        "hard_max_strength": 0.62,
        "notes": ["缩量无主线环境下，低吸只保留最强位置和承接。"],
    },
    "fast_rotation": {
        "score_penalty": 2.2,
        "candidate_penalty_weight": 0.40,
        "ranking_bonus": -1.2,
        "position_multiplier": 0.78,
        "soft_buy_allowed": False,
        "hard_buy_allowed": True,
        "soft_max_strength": 0.0,
        "hard_max_strength": 0.58,
        "notes": ["热点轮动过快，优先保留结构型而非扩散型机会。"],
    },
    "weight_support": {
        "score_penalty": 2.5,
        "candidate_penalty_weight": 0.46,
        "ranking_bonus": -1.5,
        "position_multiplier": 0.76,
        "soft_buy_allowed": False,
        "hard_buy_allowed": True,
        "soft_max_strength": 0.0,
        "hard_max_strength": 0.65,
        "notes": ["指数偏强但个股广度弱，追逐型买点需要显著降级。"],
    },
    "weight_support_active": {
        "score_penalty": 1.4,
        "candidate_penalty_weight": 0.30,
        "ranking_bonus": -0.5,
        "position_multiplier": 0.88,
        "soft_buy_allowed": True,
        "hard_buy_allowed": True,
        "soft_max_strength": 0.70,
        "hard_max_strength": 0.82,
        "notes": ["指数稳住但题材仍活，保留结构票，情绪票只留最强确认。"],
    },
    "high_flyer_retreat": {
        "score_penalty": 3.0,
        "candidate_penalty_weight": 0.56,
        "ranking_bonus": -1.8,
        "position_multiplier": 0.68,
        "soft_buy_allowed": False,
        "hard_buy_allowed": False,
        "soft_max_strength": 0.0,
        "hard_max_strength": 0.0,
        "notes": ["高位退潮期以防守为主，新信号需要显著收紧。"],
    },
    "risk_release": {
        "score_penalty": 4.8,
        "candidate_penalty_weight": 0.72,
        "ranking_bonus": -3.2,
        "position_multiplier": 0.42,
        "soft_buy_allowed": False,
        "hard_buy_allowed": False,
        "execution_blocked": True,
        "soft_max_strength": 0.0,
        "hard_max_strength": 0.0,
        "notes": ["风险释放期整体降级，不鼓励新增低吸。"],
    },
}

_STRATEGY_OVERRIDES: dict[str, dict[str, dict[str, object]]] = {
    "classic_retrace": {
        "repair": {"position_multiplier": 1.0, "hard_max_strength": 0.92},
        "weight_support": {"score_penalty": 1.8, "ranking_bonus": -0.9, "position_multiplier": 0.84, "soft_buy_allowed": True, "soft_max_strength": 0.52, "hard_max_strength": 0.74},
        "weight_support_active": {"score_penalty": 0.8, "candidate_penalty_weight": 0.24, "ranking_bonus": 0.1, "position_multiplier": 0.92, "soft_buy_allowed": True, "soft_max_strength": 0.80, "hard_max_strength": 0.88},
        "high_flyer_retreat": {"score_penalty": 3.4, "ranking_bonus": -2.0, "position_multiplier": 0.66, "soft_buy_allowed": False, "hard_buy_allowed": False, "hard_max_strength": 0.0},
    },
    "ma_support": {
        "broad_rally": {"ranking_bonus": 0.8, "position_multiplier": 1.05},
        "repair": {"ranking_bonus": 0.8, "position_multiplier": 1.0, "hard_max_strength": 0.94},
        "weight_support": {"score_penalty": 1.4, "ranking_bonus": -0.6, "position_multiplier": 0.88, "soft_buy_allowed": True, "soft_max_strength": 0.62, "hard_max_strength": 0.82},
        "weight_support_active": {"score_penalty": 0.6, "candidate_penalty_weight": 0.20, "ranking_bonus": 0.4, "position_multiplier": 0.96, "soft_buy_allowed": True, "soft_max_strength": 0.84, "hard_max_strength": 0.92},
        "high_flyer_retreat": {"score_penalty": 3.2, "ranking_bonus": -1.8, "position_multiplier": 0.68, "soft_buy_allowed": False, "hard_buy_allowed": False, "hard_max_strength": 0.0},
    },
    "first_board": {
        "repair": {"score_penalty": 1.5, "ranking_bonus": 0.2, "position_multiplier": 0.88, "hard_max_strength": 0.72},
        "low_volume_wait": {"score_penalty": 2.8, "ranking_bonus": -1.4, "position_multiplier": 0.72, "hard_buy_allowed": False},
        "fast_rotation": {"score_penalty": 3.0, "ranking_bonus": -2.2, "position_multiplier": 0.62, "hard_buy_allowed": False},
        "weight_support": {"score_penalty": 3.2, "ranking_bonus": -2.4, "position_multiplier": 0.58, "hard_buy_allowed": False},
        "weight_support_active": {"score_penalty": 2.2, "candidate_penalty_weight": 0.44, "ranking_bonus": -1.2, "position_multiplier": 0.70, "soft_buy_allowed": False, "hard_max_strength": 0.46},
        "high_flyer_retreat": {"score_penalty": 4.0, "ranking_bonus": -2.8, "position_multiplier": 0.48, "execution_blocked": True},
    },
    "volume_shrink": {
        "repair": {"position_multiplier": 0.98, "hard_max_strength": 0.82},
        "low_volume_wait": {"score_penalty": 2.0, "ranking_bonus": -0.9, "position_multiplier": 0.80, "soft_buy_allowed": True, "soft_max_strength": 0.52, "hard_max_strength": 0.58},
        "fast_rotation": {"score_penalty": 2.6, "ranking_bonus": -1.6, "position_multiplier": 0.70, "soft_buy_allowed": False, "hard_max_strength": 0.42},
        "weight_support": {"score_penalty": 2.8, "ranking_bonus": -1.8, "position_multiplier": 0.68, "soft_buy_allowed": False, "hard_max_strength": 0.46},
        "weight_support_active": {"score_penalty": 1.5, "candidate_penalty_weight": 0.32, "ranking_bonus": -0.4, "position_multiplier": 0.82, "soft_buy_allowed": True, "soft_max_strength": 0.58, "hard_max_strength": 0.64},
    },
    "late_session_strong_support": {
        "broad_rally": {"ranking_bonus": 0.8, "position_multiplier": 0.96},
        "repair": {"score_penalty": 1.2, "ranking_bonus": 0.1, "position_multiplier": 0.86, "hard_max_strength": 0.68},
        "low_volume_wait": {"score_penalty": 2.4, "ranking_bonus": -1.2, "position_multiplier": 0.70, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "fast_rotation": {"score_penalty": 2.8, "ranking_bonus": -1.8, "position_multiplier": 0.62, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support": {"score_penalty": 3.0, "ranking_bonus": -2.0, "position_multiplier": 0.58, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support_active": {"score_penalty": 1.9, "candidate_penalty_weight": 0.38, "ranking_bonus": -0.7, "position_multiplier": 0.76, "soft_buy_allowed": True, "soft_max_strength": 0.52, "hard_max_strength": 0.56},
        "high_flyer_retreat": {"score_penalty": 3.8, "ranking_bonus": -2.6, "position_multiplier": 0.46, "execution_blocked": True},
        "risk_release": {"execution_blocked": True},
    },
    "core_midcap_vwap_ma5_retrace": {
        "broad_rally": {"ranking_bonus": 0.9, "position_multiplier": 1.02},
        "repair": {"score_penalty": 0.8, "ranking_bonus": 0.4, "position_multiplier": 0.94, "hard_max_strength": 0.80},
        "low_volume_wait": {"score_penalty": 1.8, "ranking_bonus": -0.8, "position_multiplier": 0.80, "soft_buy_allowed": True, "soft_max_strength": 0.56, "hard_max_strength": 0.58},
        "fast_rotation": {"score_penalty": 2.6, "ranking_bonus": -1.6, "position_multiplier": 0.68, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support": {"score_penalty": 1.5, "ranking_bonus": -0.5, "position_multiplier": 0.88, "soft_buy_allowed": True, "soft_max_strength": 0.60, "hard_max_strength": 0.72},
        "weight_support_active": {"score_penalty": 0.7, "candidate_penalty_weight": 0.22, "ranking_bonus": 0.3, "position_multiplier": 0.96, "soft_buy_allowed": True, "soft_max_strength": 0.80, "hard_max_strength": 0.84},
        "high_flyer_retreat": {"score_penalty": 3.4, "ranking_bonus": -2.2, "position_multiplier": 0.56, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "risk_release": {"execution_blocked": True},
    },
    "sector_mainline_first_divergence_low_buy": {
        "broad_rally": {"ranking_bonus": 1.0, "position_multiplier": 0.98},
        "repair": {"score_penalty": 1.0, "ranking_bonus": 0.2, "position_multiplier": 0.88, "hard_max_strength": 0.70},
        "low_volume_wait": {"score_penalty": 2.2, "ranking_bonus": -1.1, "position_multiplier": 0.72, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "fast_rotation": {"score_penalty": 2.4, "ranking_bonus": -1.4, "position_multiplier": 0.66, "soft_buy_allowed": False, "hard_max_strength": 0.44},
        "weight_support": {"score_penalty": 3.1, "ranking_bonus": -2.0, "position_multiplier": 0.58, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support_active": {"score_penalty": 1.6, "candidate_penalty_weight": 0.34, "ranking_bonus": -0.4, "position_multiplier": 0.78, "soft_buy_allowed": True, "soft_max_strength": 0.56, "hard_max_strength": 0.58},
        "high_flyer_retreat": {"score_penalty": 3.8, "ranking_bonus": -2.6, "position_multiplier": 0.48, "execution_blocked": True},
        "risk_release": {"execution_blocked": True},
    },
    "mainline_limitup_shrink_retrace_reclaim": {
        "broad_rally": {"ranking_bonus": 1.0, "position_multiplier": 1.00},
        "repair": {"score_penalty": 0.8, "ranking_bonus": 0.3, "position_multiplier": 0.92, "hard_max_strength": 0.74},
        "low_volume_wait": {"score_penalty": 1.8, "ranking_bonus": -0.8, "position_multiplier": 0.78, "soft_buy_allowed": True, "soft_max_strength": 0.54, "hard_max_strength": 0.58},
        "fast_rotation": {"score_penalty": 2.4, "ranking_bonus": -1.5, "position_multiplier": 0.66, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support": {"score_penalty": 2.8, "ranking_bonus": -1.8, "position_multiplier": 0.60, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support_active": {"score_penalty": 1.4, "candidate_penalty_weight": 0.32, "ranking_bonus": -0.3, "position_multiplier": 0.80, "soft_buy_allowed": True, "soft_max_strength": 0.58, "hard_max_strength": 0.62},
        "high_flyer_retreat": {"score_penalty": 3.8, "ranking_bonus": -2.6, "position_multiplier": 0.46, "execution_blocked": True},
        "risk_release": {"execution_blocked": True},
    },
    "breakout_support": {
        "repair": {"position_multiplier": 0.98, "hard_max_strength": 0.88},
        "weight_support": {"score_penalty": 1.6, "ranking_bonus": -0.8, "position_multiplier": 0.84, "soft_buy_allowed": True, "soft_max_strength": 0.56, "hard_max_strength": 0.76},
        "weight_support_active": {"score_penalty": 0.7, "candidate_penalty_weight": 0.22, "ranking_bonus": 0.3, "position_multiplier": 0.94, "soft_buy_allowed": True, "soft_max_strength": 0.82, "hard_max_strength": 0.90},
        "high_flyer_retreat": {"score_penalty": 3.6, "ranking_bonus": -2.2, "position_multiplier": 0.62, "soft_buy_allowed": False, "hard_buy_allowed": False, "hard_max_strength": 0.0},
    },
    "limit_up_breakout_retrace": {
        "broad_rally": {"ranking_bonus": 0.9, "position_multiplier": 0.98},
        "repair": {"score_penalty": 1.8, "ranking_bonus": -0.4, "position_multiplier": 0.82, "soft_buy_allowed": True, "soft_max_strength": 0.44, "hard_max_strength": 0.58},
        "low_volume_wait": {"score_penalty": 2.8, "ranking_bonus": -1.4, "position_multiplier": 0.66, "soft_buy_allowed": False, "hard_max_strength": 0.30},
        "fast_rotation": {"score_penalty": 3.2, "ranking_bonus": -2.0, "position_multiplier": 0.58, "execution_blocked": True},
        "weight_support": {"score_penalty": 3.4, "ranking_bonus": -2.2, "position_multiplier": 0.54, "execution_blocked": True},
        "weight_support_active": {"score_penalty": 2.4, "candidate_penalty_weight": 0.46, "ranking_bonus": -1.2, "position_multiplier": 0.66, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "high_flyer_retreat": {"score_penalty": 4.0, "ranking_bonus": -2.8, "position_multiplier": 0.48, "execution_blocked": True},
        "risk_release": {"execution_blocked": True},
    },
    "divergence_consensus": {
        "broad_rally": {"ranking_bonus": 1.0, "position_multiplier": 0.96},
        "repair": {"score_penalty": 1.4, "ranking_bonus": 0.0, "position_multiplier": 0.80, "soft_buy_allowed": True, "soft_max_strength": 0.38, "hard_max_strength": 0.52},
        "low_volume_wait": {"score_penalty": 3.0, "ranking_bonus": -1.6, "position_multiplier": 0.60, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "fast_rotation": {"score_penalty": 3.5, "ranking_bonus": -2.4, "position_multiplier": 0.52, "execution_blocked": True},
        "weight_support": {"score_penalty": 3.6, "ranking_bonus": -2.5, "position_multiplier": 0.50, "execution_blocked": True},
        "weight_support_active": {"score_penalty": 2.6, "candidate_penalty_weight": 0.48, "ranking_bonus": -1.3, "position_multiplier": 0.62, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "high_flyer_retreat": {"score_penalty": 4.2, "ranking_bonus": -3.0, "position_multiplier": 0.44, "execution_blocked": True},
        "risk_release": {"execution_blocked": True},
    },
    "deep_pullback": {
        "repair": {"score_penalty": 1.6, "position_multiplier": 0.82, "soft_buy_allowed": False, "hard_max_strength": 0.62},
        "low_volume_wait": {"score_penalty": 2.6, "position_multiplier": 0.66, "execution_blocked": True},
        "fast_rotation": {"score_penalty": 3.0, "position_multiplier": 0.58, "execution_blocked": True},
        "weight_support": {"score_penalty": 3.2, "position_multiplier": 0.56, "execution_blocked": True},
        "weight_support_active": {"score_penalty": 2.2, "candidate_penalty_weight": 0.42, "position_multiplier": 0.64, "execution_blocked": True},
        "high_flyer_retreat": {"score_penalty": 4.2, "position_multiplier": 0.44, "execution_blocked": True},
    },
    "trend_rebound": {
        "repair": {"ranking_bonus": 0.3, "position_multiplier": 0.94, "hard_max_strength": 0.76},
        "low_volume_wait": {"score_penalty": 2.2, "ranking_bonus": -1.0, "position_multiplier": 0.76, "soft_buy_allowed": False, "hard_max_strength": 0.46},
        "fast_rotation": {"score_penalty": 2.9, "ranking_bonus": -1.8, "position_multiplier": 0.64, "soft_buy_allowed": False, "hard_max_strength": 0.38},
        "weight_support": {"score_penalty": 3.2, "ranking_bonus": -2.2, "position_multiplier": 0.60, "soft_buy_allowed": False, "hard_buy_allowed": False},
        "weight_support_active": {"score_penalty": 1.8, "candidate_penalty_weight": 0.34, "ranking_bonus": -0.8, "position_multiplier": 0.76, "soft_buy_allowed": False, "hard_buy_allowed": True, "hard_max_strength": 0.52},
        "high_flyer_retreat": {"score_penalty": 4.0, "ranking_bonus": -2.6, "position_multiplier": 0.48, "execution_blocked": True},
    },
}

_SEVERITY_PENALTY_SCALE = {
    "broad_rally": 0.4,
    "repair": 0.8,
    "low_volume_wait": 1.2,
    "fast_rotation": 1.4,
    "weight_support": 1.8,
    "weight_support_active": 1.1,
    "high_flyer_retreat": 2.0,
    "risk_release": 2.6,
}


def build_low_buy_market_adjustment(
    strategy: str,
    market_state: str,
    market_state_text: str,
    market_state_strength: float = 0.0,
) -> LowBuyMarketAdjustment:
    profile = resolve_strategy_market_profile(
        strategy=strategy,
        market_state=market_state,
        market_state_strength=market_state_strength,
    )
    risks = [*profile.notes]
    if market_state_text:
        risks.insert(0, f"当前市场状态：{market_state_text}。")
    return LowBuyMarketAdjustment(
        score_penalty=profile.score_penalty,
        candidate_penalty_weight=profile.candidate_penalty_weight,
        position_multiplier=profile.position_multiplier,
        execution_blocked=profile.execution_blocked,
        market_state_strength=profile.market_state_strength,
        extra_risks=risks,
        extra_tags=[market_state_text] if market_state_text else [],
    )


def resolve_strategy_market_profile(
    strategy: str,
    market_state: str,
    market_state_strength: float = 0.0,
) -> StrategyMarketProfile:
    state = market_state or "low_volume_wait"
    strength = _clamp(market_state_strength)
    base = dict(_DEFAULT_STATE_RULES.get(state, _DEFAULT_STATE_RULES["low_volume_wait"]))
    base.update(_STRATEGY_OVERRIDES.get(strategy, {}).get(state, {}))
    penalty_scale = _SEVERITY_PENALTY_SCALE.get(state, 1.0)
    score_penalty = float(base["score_penalty"]) + penalty_scale * strength
    ranking_bonus = _scaled_ranking_bonus(float(base["ranking_bonus"]), strength)
    position_multiplier = _scaled_position_multiplier(float(base["position_multiplier"]), strength)
    candidate_penalty_weight = float(base.get("candidate_penalty_weight", 0.45))
    soft_allowed = bool(base["soft_buy_allowed"]) and strength <= float(base.get("soft_max_strength", 1.0))
    hard_allowed = bool(base["hard_buy_allowed"]) and strength <= float(base.get("hard_max_strength", 1.0))
    execution_blocked = bool(base.get("execution_blocked", False))
    notes = list(base.get("notes", []))
    if state in _NEGATIVE_STATES and strength >= 0.7:
        notes.append("当前环境强度偏高，执行信号需要进一步收紧。")
    elif state in _POSITIVE_STATES and strength >= 0.6:
        notes.append("当前环境偏正向，但仍要优先做确认充分的结构。")
    return StrategyMarketProfile(
        score_penalty=round(score_penalty, 2),
        candidate_penalty_weight=round(candidate_penalty_weight, 3),
        ranking_bonus=round(ranking_bonus, 2),
        position_multiplier=round(position_multiplier, 4),
        soft_buy_allowed=soft_allowed and not execution_blocked,
        hard_buy_allowed=hard_allowed and not execution_blocked,
        execution_blocked=execution_blocked,
        market_state_strength=strength,
        notes=notes,
    )


def soft_buy_allowed(strategy: str, market_state: str, market_state_strength: float = 0.0) -> bool:
    return resolve_strategy_market_profile(strategy, market_state, market_state_strength).soft_buy_allowed


def hard_buy_allowed(strategy: str, market_state: str, market_state_strength: float = 0.0) -> bool:
    return resolve_strategy_market_profile(strategy, market_state, market_state_strength).hard_buy_allowed


def strategy_market_bonus(strategy: str, market_state: str, market_state_strength: float = 0.0) -> float:
    return resolve_strategy_market_profile(strategy, market_state, market_state_strength).ranking_bonus


def strategy_position_multiplier(strategy: str, market_state: str, market_state_strength: float = 0.0) -> float:
    return resolve_strategy_market_profile(strategy, market_state, market_state_strength).position_multiplier


def compute_directional_bias(
    market_state: str,
    regime_scores: dict | None = None,
    emotion_data: dict | None = None,
    mainline_strength: dict | None = None,
) -> str:
    state = market_state or "low_volume_wait"
    scores = regime_scores or {}
    emotion = emotion_data or {}
    mainline = mainline_strength or {}
    broken_ratio = float(emotion.get("broken_board_ratio") or 0.0)
    limit_down_count = int(emotion.get("limit_down_count") or 0)
    limit_up_count = int(emotion.get("limit_up_count") or 0)
    mainline_score = float(mainline.get("score") or mainline.get("strength") or 0.0)
    style_divergence = float(scores.get("style_divergence") or 0.0)

    if state in {"risk_release", "high_flyer_retreat"} or limit_down_count >= 20:
        return "neutral"
    if broken_ratio >= 0.45 and limit_up_count < 25:
        return "negative_t"
    if state in {"broad_rally", "repair"}:
        return "positive_t"
    if state == "fast_rotation" and mainline_score >= 0.7:
        return "positive_t"
    if state in {"weight_support", "weight_support_active"} and style_divergence >= 0.35:
        return "negative_t"
    return "neutral"


def directional_bias_text(bias: str) -> str:
    return {
        "positive_t": "正T优先",
        "negative_t": "反T优先",
        "neutral": "观望",
    }.get(bias, "观望")


def _scaled_ranking_bonus(bonus: float, strength: float) -> float:
    magnitude = 0.45 + strength * 0.55
    return bonus * magnitude


def _scaled_position_multiplier(multiplier: float, strength: float) -> float:
    if multiplier >= 1.0:
        return 1.0 + (multiplier - 1.0) * strength
    return 1.0 - (1.0 - multiplier) * max(strength, 0.45)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
