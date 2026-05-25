from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schemas import QuoteSnapshot
from app.services.bff.remote_client import RemoteBffError, remote_bff_get

logger = logging.getLogger(__name__)


def load_go_market_read_quotes(symbols: list[str]) -> dict[str, QuoteSnapshot]:
    settings = get_settings()
    base_url = settings.tquant_market_read_service_url.strip()
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
        result[quote.symbol] = quote.model_copy(
            update={
                "data_source": quote.data_source or "go_market_read_service",
                "source_quality": quote.source_quality or item.get("data_quality") or quote.data_quality,
                "data_quality": item.get("data_quality") or quote.data_quality,
            }
        )
    return result
