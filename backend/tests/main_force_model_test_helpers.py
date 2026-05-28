from __future__ import annotations

from app.models.schemas import LowBuyCandidateOut
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION


def main_force_candidate(**overrides) -> LowBuyCandidateOut:
    data = {
        "strategy_key": "volume_shrink",
        "strategy_title": "缩量回踩",
        "payload_version": LOW_BUY_RESULT_VERSION,
        "symbol": "300001",
        "name": "测试科技",
        "market": "SZ",
        "instrument_type": "stock",
        "sector_name": "人工智能",
        "latest_price": 11.72,
        "change_pct": 3.2,
        "quote_timestamp": "2026-04-24",
        "data_quality": "ok",
        "board_date": "2026-04-20",
        "board_count": 1,
        "retracement_days": 3,
        "score": 88.0,
        "entry_zone_low": 11.2,
        "entry_zone_high": 11.9,
        "stop_loss": 10.6,
        "take_profit": 12.8,
        "ma5": 11.4,
        "ma10": 11.2,
        "ma20": 10.9,
        "volume_burst_ratio": 2.0,
        "volume_shrink_ratio": 0.62,
        "support_distance_pct": 1.2,
        "execution_ready": True,
        "execution_note": "测试",
        "risk_tier": "note",
        "suggested_position_pct": 6.0,
        "suggested_position_text": "小仓 6%",
        "final_position_cap_pct": 6.0,
        "summary_reason": "测试",
        "buy_signal_state": "buy_now",
        "buy_signal_text": "确定买入",
        "buy_signal_hint": "测试",
        "market_state": "repair",
        "market_state_text": "修复中",
        "market_state_strength": 0.7,
        "market_position_multiplier": 1.0,
        "reasons": ["测试"],
        "risks": ["测试"],
        "tags": ["测试"],
    }
    data.update(overrides)
    return LowBuyCandidateOut(**data)


def washout_history(days: int = 45) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for idx in range(days):
        day = idx + 1
        trade_date = f"2026-03-{day:02d}" if day <= 31 else f"2026-04-{day - 31:02d}"
        if idx < 25:
            close = 10.0 + idx * 0.04
            volume = 1_200_000 + idx * 12_000
        elif idx < 34:
            close = 11.0 + (idx - 25) * 0.18
            volume = 2_200_000 + (idx - 25) * 110_000
        elif idx < 42:
            close = 12.3 - (idx - 34) * 0.13
            volume = 1_600_000 - (idx - 34) * 55_000
        else:
            close = 11.25 + (idx - 42) * 0.16
            volume = 1_550_000 + (idx - 42) * 90_000
        rows.append(_bar(trade_date, close, volume))
    rows[-1].update({
        "trade_date": "2026-04-24",
        "close_price": 11.72,
        "high_price": 11.86,
        "low_price": 11.18,
        "open_price": 11.28,
        "amount": 210_000_000,
        "pct_chg": 3.2,
    })
    return rows


def _bar(trade_date: str, close: float, volume: float) -> dict[str, float | str]:
    return {
        "trade_date": trade_date,
        "open_price": close * 0.99,
        "close_price": close,
        "high_price": close * 1.025,
        "low_price": close * 0.975,
        "volume": volume,
        "amount": volume * close * 10,
        "pct_chg": 0.0,
    }
