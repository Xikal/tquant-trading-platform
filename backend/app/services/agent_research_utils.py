from __future__ import annotations

from typing import Any


OPERATION_CHECKLIST = [
    "市场状态是否允许开仓？",
    "目标标的是否在主线板块？",
    "三方分析师结论是否一致？",
    "价格是否已进入买点区？",
    "单票仓位是否 <= 20%？",
    "止损位是否已设定？",
    "是否为 T+1 买入日（卖出需检查可用股数）？",
]


def metadata(context: str) -> dict[str, Any]:
    return {"context": context, "read_only": True, "llm_used": False, "strategy_params_modified": False}


def get_value(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def first_attr(obj: Any, name: str, default: Any = None) -> Any:
    value = get_value(obj, name, None)
    return default if value is None else value


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def ratio(value: Any) -> float:
    value_float = to_float(value)
    if value_float > 1:
        value_float /= 100
    return round(max(0.0, min(value_float, 1.0)), 4)


def to_pct(value: Any) -> int:
    return int(round(ratio(value) * 100))


def position_range(state: str, multiplier: float) -> dict[str, int]:
    max_pct = int(round(55 * max(0.25, min(multiplier, 1.2))))
    if state == "risk_release":
        max_pct = min(max_pct, 25)
    elif state == "high_flyer_retreat":
        max_pct = min(max_pct, 35)
    return {"min_pct": 15 if max_pct >= 25 else 0, "max_pct": max(15, min(max_pct, 65))}


def market_risk_level(state: str, broken_ratio: float, limit_down_count: int) -> str:
    if state in {"risk_release", "high_flyer_retreat"} or limit_down_count >= 20 or broken_ratio >= 0.35:
        return "high"
    if state in {"fast_rotation", "low_volume_wait"} or limit_down_count >= 8 or broken_ratio >= 0.22:
        return "medium"
    return "low"


def market_risk_notes(state: str, risk_level: str, range_pct: dict[str, int], errors: list[str]) -> list[str]:
    notes = [f"市场风险等级 {risk_level}，建议总仓位 {range_pct['min_pct']}%-{range_pct['max_pct']}%。"]
    if state in {"low_volume_wait", "fast_rotation"}:
        notes.append("缩量或快速轮动环境下，只处理强确认标的。")
    if errors:
        notes.append("部分行情源降级，所有结论需要人工复核。")
    return notes[:3]


def match_hot_industry(item: Any, hot_industries: list[str]) -> str:
    text = " ".join(
        str(value)
        for value in [
            get_value(item, "summary", ""),
            get_value(item, "strategy_titles", []),
            get_value(item, "buy_signal_text", ""),
        ]
    )
    return next((industry for industry in hot_industries if industry and industry in text), hot_industries[0] if hot_industries else "")


def mainline_score(rank: int, items: list[Any], is_hot: bool) -> int:
    base = 82 if is_hot else 58
    score = base - (rank - 1) * 7 + min(len(items), 5) * 3
    return max(0, min(100, score))


def stock_brief(item: Any) -> dict[str, Any]:
    return {
        "symbol": get_value(item, "symbol", ""),
        "name": get_value(item, "name", ""),
        "signal": get_value(item, "buy_signal_text", ""),
        "score": to_float(get_value(item, "priority_score", 0.0)),
    }


def sector_evidence(sector: str, items: list[Any], is_hot: bool) -> list[str]:
    evidence = [f"{sector} 位于热点主线列表。" if is_hot else f"{sector} 来自候选池归因。"]
    if items:
        evidence.append(f"候选池覆盖 {len(items)} 只标的，最高分 {max(to_float(get_value(item, 'priority_score', 0.0)) for item in items):.1f}。")
    else:
        evidence.append("暂无候选标的，需等待工程数据补齐或人工确认。")
    return evidence


def rotation_risks(board: Any, mainlines: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if not mainlines:
        risks.append("未识别到可用主线，按无主线环境处理。")
    if get_value(board, "directional_bias", "") in {"defensive", "risk_off"}:
        risks.append("方向偏防守，主线延续性需要打折。")
    if get_value(board, "data_quality", "ok") != "ok":
        risks.append(get_value(board, "data_quality_text", "板块数据质量降级。"))
    return risks or ["板块轮动风险未触发系统升级。"]


def clean_symbols(symbols: list[str]) -> list[str]:
    result: list[str] = []
    for symbol in symbols:
        cleaned = str(symbol or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result[:30]


def validation_item(symbol: str, analysis: Any, board_item: Any, hot_industries: set[str]) -> dict[str, Any]:
    blockers = list(get_value(analysis, "blocking_rules", []) or [])
    score = to_float(get_value(analysis, "signal_score", 0.0))
    board_score = to_float(get_value(board_item, "priority_score", 0.0))
    action = get_value(analysis, "action", "hold")
    sector = get_value(board_item, "sector_name", "") or ""
    in_mainline = bool(sector and sector in hot_industries) or board_item is not None
    positive_action = action in {"positive_t", "negative_t", "buy", "buy_now", "soft_buy_now"}
    if positive_action and score >= 75 and not blockers and (board_item is not None or in_mainline):
        consensus = "high"
    elif blockers or (positive_action and board_item is None) or score < 60:
        consensus = "conflict"
    else:
        consensus = "watch"
    return {
        "symbol": symbol,
        "name": get_value(analysis, "name", get_value(board_item, "name", symbol)),
        "sector": sector,
        "consensus": consensus,
        "technical_signal": {"action": action, "text": get_value(analysis, "action_text", "观望"), "score": score},
        "strategy_signal": {
            "on_priority_board": board_item is not None,
            "score": board_score,
            "signal": get_value(board_item, "buy_signal_text", ""),
        },
        "mainline_signal": {"in_mainline": in_mainline},
        "conflict_reasons": blockers or ([] if consensus != "conflict" else ["技术面、主线或策略榜未形成一致确认。"]),
        "entry": {
            "entry_price": get_value(analysis, "entry_price", None),
            "stop_loss": get_value(analysis, "stop_loss", get_value(board_item, "stop_loss", None)),
            "take_profit": get_value(analysis, "take_profit", None),
            "entry_zone": get_value(board_item, "entry_zone", ""),
        },
        "summary": get_value(analysis, "summary", get_value(board_item, "summary", "")),
    }


def normalize_proposal(item: dict[str, Any]) -> dict[str, Any]:
    pct = to_float(item.get("position_pct", item.get("position", item.get("weight", 0.0))))
    if pct <= 1:
        pct *= 100
    return {
        "symbol": str(item.get("symbol") or ""),
        "name": str(item.get("name") or item.get("symbol") or ""),
        "sector": str(item.get("sector") or item.get("sector_name") or "未归因"),
        "position_pct": round(max(0.0, pct), 2),
    }


def risk_check_notes(risk_level: str, violations: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[str]:
    if risk_level == "clear":
        return ["仓位、行业集中度和单票暴露均未触发系统阈值。"]
    notes = []
    if violations:
        notes.append("存在硬性风控超限，组合经理不得直接执行。")
    if warnings:
        notes.append("存在接近上限的仓位项，需要人工确认。")
    return notes


def decision_summary(market: dict[str, Any], validation: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    risk_level = risk.get("risk_level", "clear")
    high_count = int(validation.get("summary", {}).get("high_confidence_count", 0))
    allow_new = bool(market.get("ok")) and risk_level in {"clear", "degrade"} and high_count > 0
    return {
        "allow_new_positions": allow_new,
        "mode": "production_review" if allow_new else "research_only",
        "summary": "存在高一致性候选，可进入人工复核。" if allow_new else "未满足生产开仓条件，保持研究或观察。",
    }
