from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median

import pandas as pd
from sqlalchemy import and_, or_, select

from app.models.entities import DailyBarSnapshot, Instrument, LowBuyPoolSnapshot
from app.repositories.low_buy import DailyHistoryRepository
from app.services.low_buy.shared import BoardCandidate
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.market.emotion import MarketEmotionSnapshot
from app.services.market.regime_scoring import classify_market_regime
from app.services.market.regime_types import MarketBreadthSnapshot


def fetch_daily_rows_for_backtest(
    *,
    db,
    symbols: list[str],
    start_date_iso: str,
    latest_trade_date: str,
    chunk_size: int = 320,
) -> dict[str, list]:
    repository = DailyHistoryRepository(db)
    rows_by_symbol: dict[str, list] = {}
    for chunk in _chunked(symbols, chunk_size):
        rows_by_symbol.update(
            repository.fetch_rows_for_symbols(
                symbols=chunk,
                start_date_iso=start_date_iso,
                latest_trade_date=latest_trade_date,
            )
        )
    return rows_by_symbol


def load_symbol_metadata(db) -> dict[str, tuple[str, str]]:
    metadata: dict[str, tuple[str, str]] = {}
    instrument_rows = db.execute(
        select(Instrument.symbol, Instrument.name).where(Instrument.instrument_type == "stock")
    ).all()
    for symbol, name in instrument_rows:
        cleaned_symbol = str(symbol)
        metadata[cleaned_symbol] = (str(name or cleaned_symbol), "")

    pool_rows = db.execute(
        select(LowBuyPoolSnapshot.symbol, LowBuyPoolSnapshot.name, LowBuyPoolSnapshot.industry)
        .where(LowBuyPoolSnapshot.industry != "")
    ).all()
    for symbol, name, industry in pool_rows:
        cleaned_symbol = str(symbol)
        current_name, current_industry = metadata.get(cleaned_symbol, (str(name or cleaned_symbol), ""))
        metadata[cleaned_symbol] = (
            current_name if current_name != cleaned_symbol else str(name or cleaned_symbol),
            str(industry or current_industry or ""),
        )

    return metadata


def fetch_historical_pool_signals(
    *,
    db,
    start_date_iso: str,
    latest_trade_date: str,
    trade_dates: list[str],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    rows = db.execute(
        select(
            DailyBarSnapshot.symbol,
            DailyBarSnapshot.trade_date,
            DailyBarSnapshot.open_price,
            DailyBarSnapshot.close_price,
            DailyBarSnapshot.high_price,
            DailyBarSnapshot.amount,
            DailyBarSnapshot.pct_chg,
        )
        .where(
            DailyBarSnapshot.trade_date >= start_date_iso,
            DailyBarSnapshot.trade_date <= latest_trade_date,
            or_(
                DailyBarSnapshot.pct_chg >= 9.2,
                and_(
                    DailyBarSnapshot.pct_chg >= 8.2,
                    DailyBarSnapshot.close_price >= DailyBarSnapshot.open_price * 1.06,
                    DailyBarSnapshot.close_price >= DailyBarSnapshot.high_price * 0.985,
                    DailyBarSnapshot.amount >= 80_000_000,
                ),
            ),
        )
        .order_by(DailyBarSnapshot.symbol.asc(), DailyBarSnapshot.trade_date.asc())
    ).all()
    trade_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    last_limit_index_by_symbol: dict[str, int] = {}
    board_count_by_symbol: dict[str, int] = {}
    signal_by_date: dict[str, list[BoardCandidate]] = {}
    for symbol, trade_date, open_price, close_price, high_price, amount, pct_chg in rows:
        symbol = str(symbol)
        name, industry = symbol_meta.get(symbol, (symbol, ""))
        if is_backtest_excluded_symbol(symbol, name):
            continue
        open_value = float(open_price or 0.0)
        close_value = float(close_price or 0.0)
        high_value = float(high_price or 0.0)
        amount_value = float(amount or 0.0)
        pct_value = float(pct_chg or 0.0)
        limit_like = pct_value >= 9.2
        strong_like = (
            pct_value >= 8.2
            and open_value > 0
            and high_value > 0
            and close_value >= open_value * 1.06
            and close_value >= high_value * 0.985
            and amount_value >= 80_000_000
        )
        if not limit_like and not strong_like:
            continue
        current_index = trade_index.get(str(trade_date), -10_000)
        previous_limit_index = last_limit_index_by_symbol.get(symbol)
        if limit_like and previous_limit_index == current_index - 1:
            board_count_by_symbol[symbol] = board_count_by_symbol.get(symbol, 1) + 1
        elif limit_like:
            board_count_by_symbol[symbol] = 1
        signal_by_date.setdefault(str(trade_date), []).append(
            BoardCandidate(
                symbol=symbol,
                name=name or symbol,
                board_date=str(trade_date),
                board_count=max(board_count_by_symbol.get(symbol, 1), 1),
                amount=amount_value,
                industry=industry,
            )
        )
        if limit_like:
            last_limit_index_by_symbol[symbol] = current_index
    return signal_by_date


def build_ranked_pools_from_signals(
    *,
    signal_by_date: dict[str, list[BoardCandidate]],
    trade_dates: list[str],
    evaluation_dates: list[str],
) -> dict[str, list[BoardCandidate]]:
    trade_date_index = {trade_date: index for index, trade_date in enumerate(trade_dates)}
    pools: dict[str, list[BoardCandidate]] = {}
    for trade_date in evaluation_dates:
        latest_index = trade_date_index.get(trade_date)
        if latest_index is None:
            pools[trade_date] = []
            continue
        board_window = trade_dates[max(0, latest_index - 13) : latest_index + 1]
        pooled: dict[str, BoardCandidate] = {}
        for board_date in board_window:
            if board_date >= trade_date:
                continue
            for item in signal_by_date.get(board_date, []):
                current = pooled.get(item.symbol)
                if current is None or current.board_date < item.board_date:
                    pooled[item.symbol] = item
        pools[trade_date] = sorted(
            pooled.values(),
            key=lambda item: (item.board_date, item.board_count == 1, item.amount),
            reverse=True,
        )
    return pools


def build_ranked_pools_from_daily_rows(
    *,
    rows_by_symbol: dict[str, list],
    trade_dates: list[str],
    evaluation_dates: list[str],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    signal_by_date = _collect_historical_pool_signals(
        rows_by_symbol=rows_by_symbol,
        symbol_meta=symbol_meta,
    )
    return build_ranked_pools_from_signals(
        signal_by_date=signal_by_date,
        trade_dates=trade_dates,
        evaluation_dates=evaluation_dates,
    )


def build_local_hot_context_by_date(
    *,
    rows_by_symbol: dict[str, list],
    trade_dates: list[str],
    evaluation_dates: list[str],
    ranked_pool_by_date: dict[str, list],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, tuple[list[str], object]]:
    rows_by_date = _index_daily_rows_by_date(rows_by_symbol)
    signal_by_date = _collect_historical_pool_signals(
        rows_by_symbol=rows_by_symbol,
        symbol_meta=symbol_meta,
    )
    contexts: dict[str, tuple[list[str], object]] = {}
    previous_hot_industries: list[str] = []
    previous_limit_up_count = 0
    previous_board_height = 0
    for trade_date in trade_dates:
        if trade_date not in evaluation_dates:
            previous_hot_industries = _top_hot_industries(ranked_pool_by_date.get(trade_date, [])) or previous_hot_industries
            previous_limit_up_count, previous_board_height = _emotion_counts(signal_by_date.get(trade_date, []))
            continue

        hot_industries = _top_hot_industries(ranked_pool_by_date.get(trade_date, []))
        hot_overlap = _hot_overlap_ratio(hot_industries, previous_hot_industries)
        hot_turnover = round(max(0.0, 1.0 - hot_overlap), 4)
        board_frame = _build_local_board_frame(
            rows=rows_by_date.get(trade_date, []),
            symbol_meta=symbol_meta,
        )
        breadth = _build_local_breadth_snapshot(
            rows_by_date.get(trade_date, []),
            hot_turnover=hot_turnover,
            hot_overlap_ratio=hot_overlap,
        )
        current_signals = signal_by_date.get(trade_date, [])
        limit_up_count, board_height = _emotion_counts(current_signals)
        emotion = _build_local_emotion_snapshot(
            limit_up_count=limit_up_count,
            previous_limit_up_count=previous_limit_up_count,
            board_height=board_height,
            previous_board_height=previous_board_height,
            hot_turnover=hot_turnover,
        )
        regime = classify_market_regime(
            board_frame,
            limit_down_count=_limit_down_count(rows_by_date.get(trade_date, [])),
            hot_industries=hot_industries,
            hot_industry_source="local_daily_history",
            hot_industry_source_text="本地日线历史推导",
            breadth_snapshot=breadth,
            emotion_snapshot=emotion,
        )
        contexts[trade_date] = (hot_industries, regime)
        previous_hot_industries = hot_industries or previous_hot_industries
        previous_limit_up_count = limit_up_count
        previous_board_height = board_height
    return contexts


def is_stock_symbol(symbol: str) -> bool:
    return len(symbol) == 6 and symbol.isdigit() and not symbol.startswith(("1", "4", "5", "8", "68"))


def is_backtest_excluded_symbol(symbol: str, name: str) -> bool:
    return not is_stock_symbol(symbol) or "ST" in name.upper()


def _collect_historical_pool_signals(
    *,
    rows_by_symbol: dict[str, list],
    symbol_meta: dict[str, tuple[str, str]],
) -> dict[str, list[BoardCandidate]]:
    signal_by_date: dict[str, list[BoardCandidate]] = {}
    for symbol, rows in rows_by_symbol.items():
        name, industry = symbol_meta.get(symbol, (symbol, ""))
        if is_backtest_excluded_symbol(symbol, name):
            continue
        consecutive_boards = 0
        previous_close = 0.0
        for row in rows:
            limit_like = _is_limit_like_bar(row=row, previous_close=previous_close)
            strong_like = _is_strong_launch_bar(row=row)
            if limit_like:
                consecutive_boards += 1
            else:
                consecutive_boards = 0
            if limit_like or strong_like:
                signal_by_date.setdefault(row.trade_date, []).append(
                    BoardCandidate(
                        symbol=symbol,
                        name=name or symbol,
                        board_date=row.trade_date,
                        board_count=max(consecutive_boards, 1),
                        amount=float(row.amount or 0.0),
                        industry=industry,
                    )
                )
            previous_close = float(row.close_price or previous_close or 0.0)
    return signal_by_date


def _is_limit_like_bar(*, row, previous_close: float) -> bool:
    close_price = float(row.close_price or 0.0)
    high_price = float(row.high_price or 0.0)
    pct_chg = float(row.pct_chg or 0.0)
    if pct_chg >= 9.2:
        return True
    if previous_close <= 0:
        return False
    return high_price >= previous_close * 1.095 and close_price >= previous_close * 1.085


def _is_strong_launch_bar(row) -> bool:
    open_price = float(row.open_price or 0.0)
    close_price = float(row.close_price or 0.0)
    high_price = float(row.high_price or 0.0)
    amount = float(row.amount or 0.0)
    pct_chg = float(row.pct_chg or 0.0)
    if min(open_price, close_price, high_price) <= 0:
        return False
    return (
        pct_chg >= 8.2
        and close_price >= open_price * 1.06
        and close_price >= high_price * 0.985
        and amount >= 80_000_000
    )


def _chunked(items: list[str], chunk_size: int):
    for index in range(0, len(items), max(chunk_size, 1)):
        yield items[index : index + chunk_size]


def _index_daily_rows_by_date(rows_by_symbol: dict[str, list]) -> dict[str, list]:
    rows_by_date: dict[str, list] = defaultdict(list)
    for symbol, rows in rows_by_symbol.items():
        for row in rows:
            rows_by_date[row.trade_date].append((symbol, row))
    return rows_by_date


def _top_hot_industries(ranked_pool: list, limit: int = 5) -> list[str]:
    scores: Counter[str] = Counter()
    for item in ranked_pool:
        industry = str(getattr(item, "industry", "") or "").strip()
        if not industry:
            continue
        scores[industry] += max(float(getattr(item, "amount", 0.0) or 0.0), 1.0)
    return [industry for industry, _ in scores.most_common(limit)]


def _build_local_board_frame(*, rows: list, symbol_meta: dict[str, tuple[str, str]]) -> pd.DataFrame | None:
    industry_changes: dict[str, list[float]] = defaultdict(list)
    for symbol, row in rows:
        _, industry = symbol_meta.get(str(symbol), ("", ""))
        if not industry:
            continue
        industry_changes[industry].append(float(row.pct_chg or 0.0))
    if not industry_changes:
        return None
    frame = pd.DataFrame(
        [
            {"industry": industry, "change_pct": mean(changes)}
            for industry, changes in industry_changes.items()
            if changes
        ]
    )
    if frame.empty:
        return None
    return frame.sort_values("change_pct", ascending=False).reset_index(drop=True)


def _build_local_breadth_snapshot(rows: list, *, hot_turnover: float, hot_overlap_ratio: float) -> MarketBreadthSnapshot:
    if not rows:
        return MarketBreadthSnapshot(
            breadth_ready=False,
            stock_up_ratio=0.0,
            stock_median_change=0.0,
            largecap_change=0.0,
            smallcap_change=0.0,
            style_divergence=0.0,
            hot_turnover=hot_turnover,
            hot_overlap_ratio=hot_overlap_ratio,
        )
    changes = [float(row.pct_chg or 0.0) for _, row in rows]
    ordered_by_amount = sorted((row for _, row in rows), key=lambda item: float(item.amount or 0.0), reverse=True)
    bucket_size = max(1, len(ordered_by_amount) // 5)
    largecap_change = mean(float(row.pct_chg or 0.0) for row in ordered_by_amount[:bucket_size])
    smallcap_change = mean(float(row.pct_chg or 0.0) for row in ordered_by_amount[-bucket_size:])
    return MarketBreadthSnapshot(
        breadth_ready=True,
        stock_up_ratio=round(sum(1 for value in changes if value > 0) / len(changes), 4),
        stock_median_change=round(median(changes), 4),
        largecap_change=round(largecap_change, 4),
        smallcap_change=round(smallcap_change, 4),
        style_divergence=round(largecap_change - smallcap_change, 4),
        hot_turnover=hot_turnover,
        hot_overlap_ratio=hot_overlap_ratio,
    )


def _build_local_emotion_snapshot(
    *,
    limit_up_count: int,
    previous_limit_up_count: int,
    board_height: int,
    previous_board_height: int,
    hot_turnover: float,
) -> MarketEmotionSnapshot:
    promotion_ratio = 0.0
    if previous_limit_up_count > 0:
        promotion_ratio = min(1.0, limit_up_count / previous_limit_up_count)
    broken_board_ratio = max(0.0, min(1.0, 1.0 - promotion_ratio)) if previous_limit_up_count > 0 else 0.0
    promotion_break_gap = max(0.0, float(previous_board_height - board_height))
    promotion_break_pressure = max(0.0, min(1.0, broken_board_ratio + hot_turnover * 0.35))
    high_flyer_gap_speed = max(0.0, min(1.0, promotion_break_gap / 3.0))
    high_flyer_retreat_ratio = max(0.0, min(1.0, broken_board_ratio * 0.7 + high_flyer_gap_speed * 0.3))
    return MarketEmotionSnapshot(
        emotion_ready=True,
        limit_up_count=limit_up_count,
        previous_limit_up_count=previous_limit_up_count,
        board_height=board_height,
        previous_board_height=previous_board_height,
        promotion_ratio=round(promotion_ratio, 4),
        broken_board_ratio=round(broken_board_ratio, 4),
        promotion_break_gap=round(promotion_break_gap, 4),
        promotion_break_pressure=round(promotion_break_pressure, 4),
        high_flyer_retreat_ratio=round(high_flyer_retreat_ratio, 4),
        high_flyer_gap_speed=round(high_flyer_gap_speed, 4),
        emotion_distribution_pressure=round(promotion_break_pressure, 4),
    )


def _emotion_counts(signals: list[BoardCandidate]) -> tuple[int, int]:
    if not signals:
        return 0, 0
    return len(signals), max(int(item.board_count or 1) for item in signals)


def _hot_overlap_ratio(current: list[str], previous: list[str]) -> float:
    if not current or not previous:
        return 0.0
    current_set = set(current)
    previous_set = set(previous)
    return round(len(current_set & previous_set) / max(1, len(current_set | previous_set)), 4)


def _limit_down_count(rows: list) -> int:
    return sum(1 for _, row in rows if float(row.pct_chg or 0.0) <= -9.2)
