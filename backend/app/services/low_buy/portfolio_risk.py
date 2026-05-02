from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json

from app.models.schemas import LowBuyCandidateOut, LowBuyPortfolioRiskOut


@dataclass(frozen=True)
class PortfolioHolding:
    symbol: str
    name: str
    industry: str
    position_pct: float


def build_portfolio_risk(
    candidates: list[LowBuyCandidateOut],
    *,
    market_state: str,
    active_holdings: list[PortfolioHolding] | None = None,
) -> LowBuyPortfolioRiskOut:
    holdings = active_holdings or []
    actionable = [
        item
        for item in candidates
        if item.buy_signal_state in {"buy_now", "soft_buy_now", "near_entry"}
        and item.suggested_position_pct > 0
    ]
    if not actionable and not holdings:
        return LowBuyPortfolioRiskOut(
            recommended_total_cap_pct=_market_cap(market_state),
            notes=["当前没有可执行仓位，组合层保持等待。"],
        )

    industry_positions = _industry_position_map(actionable)
    holding_industry_positions = _holding_industry_position_map(holdings)
    combined_industry_positions = _merge_industry_positions(
        industry_positions,
        holding_industry_positions,
    )
    total_position = round(sum(item.suggested_position_pct for item in actionable), 2)
    holding_position = round(sum(item.position_pct for item in holdings), 2)
    max_candidate_position = max((item.suggested_position_pct for item in actionable), default=0.0)
    max_holding_position = max((item.position_pct for item in holdings), default=0.0)
    max_single = round(max(max_candidate_position, max_holding_position), 2)
    top_industry, top_industry_position = _top_industry(combined_industry_positions)
    cap = _market_cap(market_state)
    notes = _risk_notes(
        total_position=total_position + holding_position,
        max_single=max_single,
        top_industry=top_industry,
        top_industry_position=top_industry_position,
        cap=cap,
        holding_position=holding_position,
    )
    return LowBuyPortfolioRiskOut(
        total_planned_position_pct=total_position,
        holding_position_pct=holding_position,
        max_single_position_pct=max_single,
        active_signal_count=len(actionable),
        holding_signal_count=len(holdings),
        industry_concentration_pct=round(top_industry_position, 2),
        top_industry=top_industry,
        recommended_total_cap_pct=cap,
        risk_level=_risk_level(total_position + holding_position, top_industry_position, cap),
        notes=notes,
    )


def build_lifecycle_holdings(rows) -> list[PortfolioHolding]:
    holdings: list[PortfolioHolding] = []
    for row in rows:
        payload = _load_lifecycle_payload(row.payload_json)
        position_pct = _coerce_float(payload.get("suggested_position_pct"), default=0.0)
        if position_pct <= 0:
            position_pct = _estimate_position_from_plan(row)
        holdings.append(
            PortfolioHolding(
                symbol=row.symbol,
                name=row.name,
                industry=str(payload.get("sector_name") or "未归类"),
                position_pct=position_pct,
            )
        )
    return holdings


def _industry_position_map(candidates: list[LowBuyCandidateOut]) -> dict[str, float]:
    buckets: dict[str, float] = defaultdict(float)
    for item in candidates:
        buckets[item.sector_name or "未归类"] += item.suggested_position_pct
    return dict(buckets)


def _holding_industry_position_map(holdings: list[PortfolioHolding]) -> dict[str, float]:
    buckets: dict[str, float] = defaultdict(float)
    for item in holdings:
        buckets[item.industry or "未归类"] += item.position_pct
    return dict(buckets)


def _merge_industry_positions(*maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = defaultdict(float)
    for item in maps:
        for industry, position in item.items():
            merged[industry] += position
    return dict(merged)


def _top_industry(industry_positions: dict[str, float]) -> tuple[str, float]:
    if not industry_positions:
        return "", 0.0
    return max(industry_positions.items(), key=lambda item: item[1])


def _market_cap(market_state: str) -> float:
    caps = {
        "broad_rally": 65.0,
        "repair": 50.0,
        "weight_support_active": 42.0,
        "low_volume_wait": 35.0,
        "fast_rotation": 30.0,
        "weight_support": 28.0,
        "high_flyer_retreat": 22.0,
        "risk_release": 15.0,
    }
    return caps.get(market_state, 35.0)


def _risk_level(total_position: float, top_industry_position: float, cap: float) -> str:
    if total_position > cap * 1.2 or top_industry_position > 35:
        return "block"
    if total_position > cap or top_industry_position > 25:
        return "degrade"
    if total_position > cap * 0.75 or top_industry_position > 18:
        return "note"
    return "clear"


def _risk_notes(
    *,
    total_position: float,
    max_single: float,
    top_industry: str,
    top_industry_position: float,
    cap: float,
    holding_position: float,
) -> list[str]:
    notes = [f"当前市场建议低吸总仓不超过 {cap:.0f}%。"]
    if holding_position > 0:
        notes.append(f"已记录持仓约 {holding_position:.1f}%，新信号需扣除已占用仓位。")
    if total_position > cap:
        notes.append("候选信号合计仓位超过市场上限，需要只保留最高优先级。")
    if max_single > 30:
        notes.append("单票建议仓位偏高，建议拆分确认。")
    if top_industry_position > 25:
        notes.append(f"{top_industry} 行业信号过于集中，避免同题材连续开仓。")
    return notes


def _load_lifecycle_payload(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _coerce_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _estimate_position_from_plan(row) -> float:
    if row.entry_price and row.entry_plan_low and row.entry_plan_high:
        return 10.0
    return 5.0
