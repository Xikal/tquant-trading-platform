from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.services.trading_experience import repository
from app.services.trading_experience.config import ENGINE_VERSION
from app.services.trading_experience.key_level_context import key_level_missing_evidence, load_stock_key_level_context
from app.services.trading_experience.schemas import VolumePositionTag


def build_tags(db: Session, symbol: str, *, trade_date: date | None = None) -> list[VolumePositionTag]:
    end_date = trade_date or repository.latest_trade_date(db)
    history = repository.symbol_history(db, symbol, end_date=end_date, days=20)
    as_of = datetime.now()
    if len(history) < 5:
        return [
            VolumePositionTag(
                symbol=symbol,
                trade_date=end_date.isoformat() if end_date else "",
                tag_code="insufficient_history",
                level="info",
                evidence=["信号日前历史样本不足"],
                explanation="数据不足，保持观察态。",
                data_quality="insufficient",
                as_of=as_of,
                engine_version=ENGINE_VERSION,
            )
        ]
    current = history[-1]
    key_level = load_stock_key_level_context(db, symbol, trade_date=current.trade_date, latest_price=float(current.close_price or 0.0))
    if key_level is None:
        return [
            VolumePositionTag(
                symbol=symbol,
                trade_date=current.trade_date.isoformat(),
                tag_code="insufficient_key_level",
                level="info",
                evidence=key_level_missing_evidence(symbol, current.trade_date),
                explanation="关键位缓存缺失，无法判断量价-位置标签。",
                data_quality="insufficient",
                as_of=as_of,
                engine_version=ENGINE_VERSION,
            )
        ]
    prior = history[:-1]
    volume_window = prior[-5:]
    avg_volume = sum(float(row.volume or 0) for row in volume_window) / len(volume_window)
    vol_ratio = (float(current.volume or 0) / avg_volume) if avg_volume > 0 else 0.0
    close_position = _close_position(current)
    pct = float(current.pct_chg or 0.0)
    prev_pct = float(prior[-1].pct_chg or 0.0)
    position = key_level.position_percentile
    tags: list[VolumePositionTag] = []
    base = [*key_level.evidence, f"量比 {vol_ratio:.2f}", f"收盘位置 {close_position:.2f}", f"关键位位置分位 {position:.2f}" if position is not None else "关键位位置分位不足"]
    if vol_ratio >= 2.2 and close_position < 0.45 and (key_level.near_resistance or key_level.support_broken):
        tags.append(_tag(symbol, current.trade_date, "high_vol_distribution_risk", "warn", base, "高量但收盘位置偏弱，且处在关键位压力或破位状态。", as_of, key_level.result.data_quality))
    if vol_ratio <= 0.65 and pct < -1.5 and key_level.support_broken:
        tags.append(_tag(symbol, current.trade_date, "low_vol_grind_down_risk", "warn", base, "缩量下行且跌破关键支撑，留意结构走弱。", as_of, key_level.result.data_quality))
    if -3.0 <= pct <= 0.5 and vol_ratio <= 1.2 and key_level.near_support and not key_level.support_broken:
        tags.append(_tag(symbol, current.trade_date, "healthy_pullback_observe", "info", base, "回落靠近 AKeyLevel 支撑且量能未明显放大，仅作观察。", as_of, key_level.result.data_quality))
    if prev_pct > 1.0 and pct < -1.0 and vol_ratio >= 1.3 and position is not None and position >= 0.55:
        tags.append(_tag(symbol, current.trade_date, "up_shrink_down_expand_risk", "warn", base, "上行后放量回落，且仍处在较高关键位分位。", as_of, key_level.result.data_quality))
    if pct >= 8.0 and vol_ratio >= 2.5 and close_position >= 0.9 and key_level.near_resistance:
        tags.append(_tag(symbol, current.trade_date, "blowoff_overheat_risk", "warn", base, "涨幅和量能同步过热，并接近 AKeyLevel 压力区。", as_of, key_level.result.data_quality))
    if pct > 1.0 and close_position < 0.35 and position is not None and position >= 0.5:
        tags.append(_tag(symbol, current.trade_date, "price_volume_divergence_risk", "warn", base, "上涨但收盘位置偏低，关键位分位未回到低位。", as_of, key_level.result.data_quality))
    return tags or [_tag(symbol, current.trade_date, "neutral_observe", "info", [*key_level.evidence, "未触发首批风险标签"], "未触发首批量价-位置风险标签。", as_of, key_level.result.data_quality)]


def _tag(symbol: str, trade_date: date, code: str, level: str, evidence: list[str], explanation: str, as_of: datetime, data_quality: str = "ok") -> VolumePositionTag:
    return VolumePositionTag(
        symbol=symbol,
        trade_date=trade_date.isoformat(),
        tag_code=code,
        level=level,  # type: ignore[arg-type]
        evidence=evidence,
        explanation=explanation,
        data_quality=data_quality,  # type: ignore[arg-type]
        as_of=as_of,
        engine_version=ENGINE_VERSION,
    )


def _close_position(row: object) -> float:
    high = float(getattr(row, "high_price", 0.0) or 0.0)
    low = float(getattr(row, "low_price", 0.0) or 0.0)
    close = float(getattr(row, "close_price", 0.0) or 0.0)
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (close - low) / (high - low)))
