from __future__ import annotations

from app.services.low_buy.shared import pd


def build_divergence_consensus_metrics(
    history: pd.DataFrame,
    board_index: int,
    latest_index: int,
    board_row: pd.Series,
    latest: pd.Series,
) -> dict[str, float | int | bool]:
    board_high = float(board_row["high"])
    board_volume = max(float(board_row["volume"]), 1.0)
    pre_latest = history.iloc[board_index + 1 : latest_index]
    if pre_latest.empty:
        return empty_divergence_consensus_metrics(board_high, board_volume, latest)

    divergence_window = history.iloc[board_index + 1 : min(latest_index, board_index + 6)]
    if divergence_window.empty:
        divergence_window = pre_latest
    divergence_label, divergence_day_stall = select_divergence_day(
        divergence_window=divergence_window,
        board_row=board_row,
        board_volume=board_volume,
    )
    divergence_index = int(history.index.get_loc(divergence_label))
    divergence_row = history.iloc[divergence_index]
    divergence_high = max(board_high, float(divergence_row["high"]))
    divergence_volume = max(float(divergence_row["volume"]), 1.0)
    consolidation = history.iloc[divergence_index + 1 : latest_index]
    consolidation_volume = float(consolidation["volume"].mean()) if not consolidation.empty else divergence_volume
    recent_volume_window = history.iloc[max(board_index + 1, latest_index - 5) : latest_index]
    recent_volume_avg = float(recent_volume_window["volume"].mean()) if not recent_volume_window.empty else consolidation_volume
    consensus_volume_ratio = float(latest["volume"]) / max(recent_volume_avg, 1.0)
    close_strength = candle_close_strength(latest)
    latest_close = float(latest["close"])
    latest_open = float(latest["open"])
    latest_change_pct = float(latest["pct_chg"])
    return {
        "divergence_high": divergence_high,
        "divergence_volume_ratio": divergence_volume / board_volume,
        "divergence_day_stall": divergence_day_stall,
        "consolidation_days": len(consolidation),
        "consolidation_low": float(consolidation["low"].min()) if not consolidation.empty else float(latest["low"]),
        "consolidation_high": float(consolidation["high"].max()) if not consolidation.empty else divergence_high,
        "consolidation_volume_ratio": consolidation_volume / max(divergence_volume, 1.0),
        "consensus_breakout": (
            latest_close >= divergence_high * 1.002
            and latest_close >= latest_open
            and latest_change_pct >= 1.2
            and consensus_volume_ratio >= 1.45
            and close_strength >= 0.55
        ),
        "consensus_volume_ratio": consensus_volume_ratio,
        "consensus_close_strength": close_strength,
    }


def empty_divergence_consensus_metrics(board_high: float, board_volume: float, latest: pd.Series) -> dict[str, float | int | bool]:
    return {
        "divergence_high": board_high,
        "divergence_volume_ratio": 0.0,
        "divergence_day_stall": False,
        "consolidation_days": 0,
        "consolidation_low": float(latest["low"]),
        "consolidation_high": board_high,
        "consolidation_volume_ratio": 1.0,
        "consensus_breakout": False,
        "consensus_volume_ratio": float(latest["volume"]) / max(board_volume, 1.0),
        "consensus_close_strength": candle_close_strength(latest),
    }


def select_divergence_day(
    divergence_window: pd.DataFrame,
    board_row: pd.Series,
    board_volume: float,
) -> tuple[object, bool]:
    stalled_rows: list[tuple[float, object]] = []
    for label, row in divergence_window.iterrows():
        if is_divergence_stall_day(row=row, board_row=board_row, board_volume=board_volume):
            stalled_rows.append((float(row["volume"]), label))
    if stalled_rows:
        _, label = max(stalled_rows, key=lambda item: item[0])
        return label, True
    fallback_label = divergence_window["volume"].idxmax()
    fallback_row = divergence_window.loc[fallback_label]
    return fallback_label, is_divergence_stall_day(
        row=fallback_row,
        board_row=board_row,
        board_volume=board_volume,
    )


def is_divergence_stall_day(row: pd.Series, board_row: pd.Series, board_volume: float) -> bool:
    high_price = float(row["high"])
    low_price = float(row["low"])
    open_price = float(row["open"])
    close_price = float(row["close"])
    pct_chg = float(row["pct_chg"])
    volume = float(row["volume"])
    intraday_range = max(high_price - low_price, 0.01)
    upper_shadow_ratio = max(high_price - max(open_price, close_price), 0.0) / intraday_range
    close_strength = candle_close_strength(row)
    second_limit_up = pct_chg >= 9.2 or close_price >= open_price * 1.085
    stall_like = (
        pct_chg <= 5.5
        or upper_shadow_ratio >= 0.28
        or close_strength <= 0.55
        or close_price <= float(board_row["close"]) * 1.035
    )
    return volume >= board_volume * 0.55 and stall_like and not second_limit_up


def candle_close_strength(row: pd.Series) -> float:
    low_price = float(row["low"])
    high_price = float(row["high"])
    close_price = float(row["close"])
    return (close_price - low_price) / max(high_price - low_price, 0.01)
