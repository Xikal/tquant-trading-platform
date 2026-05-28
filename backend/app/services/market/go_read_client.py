from __future__ import annotations

import logging

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import (
    EtfMinuteSnapshotBatchResponse,
    IntradayKeyLevelResponse,
    SectorRelativeStrengthItem,
    SectorRelativeStrengthResponse,
)
from app.models.schemas import QuoteSnapshot
from app.services.bff.remote_client import RemoteBffError, remote_bff_get, remote_bff_post

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return get_settings().tquant_market_read_service_url.strip()


def load_go_market_read_quotes(symbols: list[str]) -> dict[str, QuoteSnapshot]:
    base_url = _base_url()
    cleaned_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
    if not base_url or not cleaned_symbols:
        return {}
    try:
        payload = remote_bff_get(
            base_url,
            "/api/market-read/v1/quote-batch",
            params={"symbols": ",".join(cleaned_symbols)},
        )
    except RemoteBffError:
        return {}

    result: dict[str, QuoteSnapshot] = {}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        quote_payload = item.get("quote")
        if not isinstance(quote_payload, dict):
            continue
        try:
            quote = QuoteSnapshot.model_validate(quote_payload)
        except ValidationError:
            logger.warning("go market read quote schema mismatch", exc_info=True)
            continue
        quality = _quote_quality(item, quote)
        result[quote.symbol] = quote.model_copy(
            update={
                "data_source": quote.data_source or "go_market_read_service",
                "source_quality": quality,
                "data_quality": quality,
                "is_stale": _quote_is_stale(quality, quote),
            }
        )
    return result


def load_go_intraday_latest(symbols: list[str]) -> dict[str, QuoteSnapshot]:
    base_url = _base_url()
    cleaned_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
    if not base_url or not cleaned_symbols:
        return {}
    try:
        payload = remote_bff_get(
            base_url,
            "/api/market-read/v1/intraday-latest-batch",
            params={"symbols": ",".join(cleaned_symbols)},
        )
    except RemoteBffError:
        return {}
    result: dict[str, QuoteSnapshot] = {}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        quote_payload = item.get("latest")
        if not isinstance(quote_payload, dict):
            continue
        try:
            quote = QuoteSnapshot.model_validate(quote_payload)
        except ValidationError:
            logger.warning("go intraday latest schema mismatch", exc_info=True)
            continue
        quality = _quote_quality(item, quote)
        result[quote.symbol] = quote.model_copy(
            update={
                "data_source": quote.data_source or "go_market_read_service",
                "source_quality": quality,
                "data_quality": quality,
                "is_stale": _quote_is_stale(quality, quote),
            }
        )
    return result


def load_go_etf_minute_snapshots(symbols: list[str], *, period: str = "1m", limit: int = 30) -> EtfMinuteSnapshotBatchResponse | None:
    base_url = _base_url()
    cleaned_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
    if not base_url or not cleaned_symbols:
        return None
    try:
        payload = remote_bff_get(
            base_url,
            "/api/market-read/v1/etf-minute-snapshot-batch",
            params={"symbols": ",".join(cleaned_symbols), "period": period, "limit": max(1, min(limit, 240))},
        )
    except RemoteBffError:
        return None
    try:
        response = EtfMinuteSnapshotBatchResponse.model_validate(payload)
    except ValidationError:
        logger.warning("go etf minute snapshot schema mismatch", exc_info=True)
        return None
    notes = list(response.notes or [])
    notes.append("Go market-read-service 只返回 ETF 分钟快照和数据质量，不生成做T信号。")
    return response.model_copy(update={"notes": notes})


def load_go_intraday_key_levels(
    symbol: str,
    *,
    entry_zone_low: float | None = None,
    entry_zone_high: float | None = None,
    threshold_pct: float = 0.3,
) -> IntradayKeyLevelResponse | None:
    base_url = _base_url()
    symbol = symbol.strip()
    if not base_url or not symbol:
        return None
    params: dict[str, object] = {"symbol": symbol, "threshold_pct": threshold_pct}
    if entry_zone_low is not None:
        params["entry_zone_low"] = entry_zone_low
    if entry_zone_high is not None:
        params["entry_zone_high"] = entry_zone_high
    try:
        payload = remote_bff_get(
            base_url,
            "/api/market-read/v1/intraday-key-levels",
            params=params,
        )
    except RemoteBffError:
        return None
    try:
        response = IntradayKeyLevelResponse.model_validate(payload)
    except ValidationError:
        logger.warning("go intraday key levels schema mismatch", exc_info=True)
        return None
    text = response.data_quality_text or "Go market-read-service 基于本地行情缓存计算分时关键位。"
    return response.model_copy(update={"data_quality_text": text})


def load_go_sector_relative_strength(
    db: Session,
    *,
    hot_sectors: list[str] | None = None,
    sector_limit: int = 8,
    per_sector_limit: int = 10,
    trade_date: str = "",
) -> SectorRelativeStrengthResponse | None:
    base_url = _base_url()
    if not base_url:
        return None

    from app.services.market.sector_relative_strength import (
        _latest_complete_trade_date,
        _load_current_rows,
        _select_sectors,
    )

    target_date = trade_date or _latest_complete_trade_date(db)
    if not target_date:
        return None
    rows = _load_current_rows(db, target_date)
    if not rows:
        return None
    sectors = _select_sectors(rows, hot_sectors or [], max(1, min(sector_limit, 20)))
    groups = [
        {
            "sector": sector_name,
            "symbols": [str(row["symbol"]) for row in rows if row["sector_name"] == sector_name],
        }
        for sector_name in sectors
    ]
    groups = [group for group in groups if group["symbols"]]
    if not groups:
        return None
    try:
        payload = remote_bff_post(
            base_url,
            "/api/market-read/v1/sector-relative-strength",
            json_body={"sectors": groups, "limit": max(1, min(per_sector_limit, 30))},
        )
    except RemoteBffError:
        return None

    items: list[SectorRelativeStrengthItem] = []
    for sector in payload.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        sector_name = str(sector.get("sector") or "")
        for rank, raw_item in enumerate(sector.get("leaders") or [], start=1):
            if not isinstance(raw_item, dict):
                continue
            try:
                items.append(
                    SectorRelativeStrengthItem(
                        sector_name=sector_name,
                        symbol=str(raw_item.get("symbol") or ""),
                        name=str(raw_item.get("name") or raw_item.get("symbol") or ""),
                        latest_price=_float(raw_item.get("last_price")),
                        change_pct=_float(raw_item.get("change_pct")),
                        sector_median_change_pct=_float(raw_item.get("sector_median_change")),
                        relative_strength_ratio=_relative_ratio(raw_item),
                        volume_ratio=_float(raw_item.get("volume_ratio")),
                        turnover_proxy=_float(raw_item.get("turnover_rate")),
                        leader_score=_float(raw_item.get("leader_score")),
                        rank=rank,
                        data_quality_text=f"Go market-read-service，本地缓存质量：{raw_item.get('data_quality') or payload.get('data_quality') or 'unknown'}",
                    )
                )
            except ValidationError:
                logger.warning("go sector strength item schema mismatch", exc_info=True)
                continue
    if not items:
        return None
    return SectorRelativeStrengthResponse(
        updated_at=beijing_now_string(),
        trade_date=target_date,
        sector_count=len(groups),
        items=items,
        notes=[
            "Go market-read-service 已优先命中板块相对强度主读路径；失败时回退 Python 计算。",
            f"data_quality={payload.get('data_quality') or 'unknown'}",
        ],
    )


def _float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _relative_ratio(raw_item: dict[str, object]) -> float | None:
    median = _float(raw_item.get("sector_median_change"))
    change = _float(raw_item.get("change_pct"))
    if abs(median) < 0.1:
        return None
    return round(change / median, 4)


def _quote_quality(item: dict[str, object], quote: QuoteSnapshot) -> str:
    return str(item.get("data_quality") or quote.source_quality or quote.data_quality or "fresh").strip() or "fresh"


def _quote_is_stale(quality: str, quote: QuoteSnapshot) -> bool:
    return bool(quote.is_stale) or "stale" in quality.lower()
