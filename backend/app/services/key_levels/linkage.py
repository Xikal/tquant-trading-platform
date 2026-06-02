from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Instrument
from app.models.schema_defs.key_levels import KeyLevelResult
from app.services.key_levels.materialization import read_cached_key_level
from app.services.key_levels.score import clamp_score


def apply_three_layer_linkage(db: Session, result: KeyLevelResult, *, trade_date: str | None = None) -> KeyLevelResult:
    if result.scope != "stock" or result.data_quality not in {"ok", "research_only"}:
        return result
    factor = 1.0
    warnings = list(result.warnings)
    market = read_cached_key_level(db, scope="market", key="market", trade_date=trade_date or result.trade_date)
    if market is None or market.data_quality in {"insufficient", "stale", "blocked"}:
        factor *= 0.7
        warnings.append("大盘关键位缺失或不可用，个股支撑可信度降级。")
    elif _support_broken(market):
        factor *= 0.7
        warnings.append("大盘跌破关键支撑，大盘/板块/个股观察统一降级。")
    sector_key = _sector_for_symbol(db, result.symbol)
    if sector_key:
        sector = read_cached_key_level(db, scope="sector", key=sector_key, trade_date=trade_date or result.trade_date)
        if sector is None or sector.data_quality in {"insufficient", "stale", "blocked"}:
            factor *= 0.8
            warnings.append("板块关键位缺失或不可用，个股支撑可信度降级。")
        elif _support_broken(sector):
            factor *= 0.8
            warnings.append("板块跌破关键支撑，板块内个股支撑可信度降级。")
        elif sector.data_quality == "research_only":
            warnings.append("板块关键位为代理序列，仅作研究观察。")
    if factor >= 0.999 and warnings == result.warnings:
        return result
    support_strength = clamp_score(int(round(result.support_strength * factor))) if result.support_strength else 0
    data_quality = result.data_quality
    if factor < 0.999 and data_quality == "ok":
        data_quality = "research_only"
    candidates = [
        candidate.model_copy(update={"strength_score": clamp_score(int(round(candidate.strength_score * factor)))})
        if candidate.direction == "support"
        else candidate
        for candidate in result.key_level_candidates
    ]
    return result.model_copy(
        update={
            "support_strength": support_strength,
            "data_quality": data_quality,
            "key_level_candidates": candidates,
            "warnings": list(dict.fromkeys(warnings)),
        }
    )


def _sector_for_symbol(db: Session, symbol: str) -> str:
    value = db.execute(select(Instrument.sector_name).where(Instrument.symbol == symbol).limit(1)).scalar_one_or_none()
    return str(value or "").strip()


def _support_broken(result: KeyLevelResult) -> bool:
    return bool(result.support_zone_low and result.latest_price < result.support_zone_low)
