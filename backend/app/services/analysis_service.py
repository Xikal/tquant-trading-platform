from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    InstrumentOut,
    MarketEventOut,
    QuoteSnapshot,
    SettingsPayload,
)
from app.repositories.low_buy.hot_industries import LowBuyHotIndustryRepository
from app.services.ai_service import AiService
from app.services.market_data import MarketDataService
from app.services.market_rules import MarketRuleService
from app.services.quant_engine import QuantEngine
from app.services.research_service import ResearchService, quote_from_bars
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self) -> None:
        self.market_data = MarketDataService()
        self.market_rules = MarketRuleService()
        self.quant_engine = QuantEngine()
        self.ai_service = AiService()
        self.research_service = ResearchService()

    def analyze(
        self,
        db: Session,
        request: AnalysisRequest,
        persist: bool = True,
        runtime_settings: SettingsPayload | None = None,
        lightweight: bool = False,
        preloaded_quote: QuoteSnapshot | None = None,
    ) -> AnalysisResponse:
        runtime_settings = runtime_settings or SettingsService(db).get_payload()
        effective_lightweight = lightweight or _request_allows_lightweight_path(request)
        instrument = self.market_data.get_instrument(db, request.symbol)
        quote = preloaded_quote or self.market_data.get_quote(request.symbol)
        bars = self.market_data.get_intraday_bars_for_analysis(
            db,
            quote,
            period="5m",
            limit=160 if effective_lightweight else 240,
            persist_snapshots=not lightweight,
        )
        rules = self.market_rules.get_or_create_rule(db, instrument)
        sector = self.market_data.get_sector_snapshot(
            instrument,
            bars,
            use_board_lookup=not effective_lightweight,
        )
        events = (
            self.market_data.get_market_events(db, request.symbol, quote)
            if runtime_settings.event_risk_enabled and request.include_events
            else []
        )
        microstructure = self.market_data.get_microstructure(
            quote,
            bars,
            enabled=bool(runtime_settings.microstructure_enabled and request.include_microstructure),
        )
        market_regime = self._load_market_regime(db)

        metrics, suggestion, compliance_notes, assumptions = self.quant_engine.evaluate(
            quote=quote,
            bars=bars,
            rules=rules,
            sector=sector,
            events=events,
            microstructure=microstructure,
            request=request,
            risk_config=runtime_settings.model_dump(),
            market_regime=market_regime,
        )
        compliance_notes.extend(
            self.market_rules.build_runtime_notes(
                rule=rules,
                base_position=request.base_position,
                available_position=request.available_position,
            )
        )
        compliance_notes = self._dedupe_keep_order(compliance_notes)
        ai = self.ai_service.build_insight(
            settings=runtime_settings.model_dump(),
            payload=self._build_ai_payload(
                instrument=InstrumentOut(
                    symbol=instrument.symbol,
                    name=instrument.name,
                    market=instrument.market,
                    instrument_type=instrument.instrument_type,
                    sector_name=instrument.sector_name,
                ).model_dump(),
                quote=quote.model_dump(),
                rules=rules.model_dump(),
                sector=sector.model_dump(),
                events=[event.model_dump() for event in events],
                metrics=metrics,
                suggestion=suggestion.model_dump(),
                assumptions=assumptions,
            ),
            include_ai=request.include_ai,
        )

        response = AnalysisResponse(
            symbol=request.symbol,
            instrument=InstrumentOut(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                instrument_type=instrument.instrument_type,
                sector_name=instrument.sector_name,
            ),
            quote=quote,
            rules=rules,
            sector=sector,
            events=events,
            microstructure=microstructure,
            bars=bars[-120:],
            metrics=metrics,
            suggestion=suggestion,
            ai=ai,
            compliance_notes=compliance_notes,
            assumptions=assumptions,
            analysis_log_id=None,
        )
        if persist:
            analysis_log_id = self.research_service.persist_analysis(db, response)
            response.analysis_log_id = analysis_log_id
        return response

    def analyze_batch(self, db: Session, requests: list[AnalysisRequest], max_workers: int = 4) -> list[AnalysisResponse]:
        if len(requests) <= 1:
            return [self.analyze(db, item, persist=False) for item in requests]

        results: list[AnalysisResponse | None] = [None] * len(requests)

        def analyze_one(index: int, request: AnalysisRequest) -> None:
            with SessionLocal() as item_db:
                results[index] = AnalysisService().analyze(item_db, request, persist=False)

        workers = min(max_workers, len(requests))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="analysis-batch") as pool:
            futures = [pool.submit(analyze_one, index, request) for index, request in enumerate(requests)]
            for future in as_completed(futures):
                try:
                    future.result(timeout=30)
                except Exception:
                    logger.warning("batch analysis item failed", exc_info=True)
        return [item for item in results if item is not None]

    def run_backtest(self, db: Session, request, instrument) -> Any:
        bars = self.market_data.get_intraday_bars(
            request.symbol,
            period=request.bar_period,
            limit=max(180, request.lookback_bars),
        )
        rules = self.market_rules.get_or_create_rule(db, instrument)
        runtime_settings = SettingsService(db).get_payload()

        def quote_factory(subset):
            return quote_from_bars(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                instrument_type=instrument.instrument_type,
                bars=subset,
            )

        def runtime_context_factory(subset, quote):
            events: list[MarketEventOut] = []
            sector = self.market_data.get_sector_snapshot(
                instrument,
                subset,
                use_board_lookup=False,
            )
            micro = self.market_data.get_microstructure(
                quote,
                subset,
                enabled=bool(runtime_settings.microstructure_enabled),
            )
            analyze_request = AnalysisRequest(
                symbol=instrument.symbol,
                prefer_strategy="auto",
                base_position=request.initial_position,
                available_position=request.initial_position,
                include_ai=False,
                include_microstructure=runtime_settings.microstructure_enabled,
            )
            return {
                "rules": rules,
                "sector": sector,
                "events": events,
                "microstructure": micro,
                "request": analyze_request,
                "market_regime": self._load_market_regime(db),
            }

        return self.research_service.run_backtest(
            db=db,
            request=request,
            bars=bars,
            quote_factory=quote_factory,
            runtime_context_factory=runtime_context_factory,
            risk_config=runtime_settings.model_dump(),
        )

    @staticmethod
    def _build_ai_payload(**kwargs: Any) -> dict[str, Any]:
        instrument = kwargs.get("instrument") or {}
        quote = kwargs.get("quote") or {}
        rules = kwargs.get("rules") or {}
        sector = kwargs.get("sector") or {}
        metrics = kwargs.get("metrics") or {}
        suggestion = kwargs.get("suggestion") or {}
        assumptions = kwargs.get("assumptions") or []
        events = kwargs.get("events") or []

        return {
            "instrument": {
                "symbol": instrument.get("symbol"),
                "name": instrument.get("name"),
                "market": instrument.get("market"),
                "instrument_type": instrument.get("instrument_type"),
                "sector_name": instrument.get("sector_name"),
            },
            "quote": {
                "last_price": quote.get("last_price"),
                "change_pct": quote.get("change_pct"),
                "amount": quote.get("amount"),
                "volume": quote.get("volume"),
                "timestamp": quote.get("timestamp"),
            },
            "rules": {
                "turnaround_mode": rules.get("turnaround_mode"),
                "requires_base_position": rules.get("requires_base_position"),
                "supports_positive_t": rules.get("supports_positive_t"),
                "supports_negative_t": rules.get("supports_negative_t"),
            },
            "sector": {
                "sector_name": sector.get("sector_name"),
                "alignment_score": sector.get("alignment_score"),
                "market_strength": sector.get("market_strength"),
            },
            "metrics": {
                "rsi14": metrics.get("rsi14"),
                "macd_hist": metrics.get("macd_hist"),
                "vwap": metrics.get("vwap"),
                "atr14": metrics.get("atr14"),
                "amplitude_pct": metrics.get("amplitude_pct"),
                "positive_score": metrics.get("positive_score"),
                "negative_score": metrics.get("negative_score"),
                "risk_score": metrics.get("risk_score"),
                "expected_profit_pct": metrics.get("expected_profit_pct"),
                "min_profit_pct": metrics.get("min_profit_pct"),
                "scenario": metrics.get("scenario"),
                "market_state": metrics.get("market_state"),
                "market_state_text": metrics.get("market_state_text"),
            },
            "suggestion": {
                "action": suggestion.get("action"),
                "risk_level": suggestion.get("risk_level"),
                "signal_score": suggestion.get("signal_score"),
                "tradability_score": suggestion.get("tradability_score"),
                "confidence": suggestion.get("confidence"),
                "expected_profit_pct": suggestion.get("expected_profit_pct"),
                "strategy_notes": suggestion.get("strategy_notes"),
                "reasons": list(suggestion.get("reasons") or [])[:4],
                "blocking_rules": list(suggestion.get("blocking_rules") or [])[:4],
            },
            "events": [
                {
                    "title": item.get("title"),
                    "risk_level": item.get("risk_level"),
                }
                for item in events[:3]
                if isinstance(item, dict)
            ],
            "assumptions": list(assumptions)[:3],
        }

    def _load_market_regime(self, db: Session):
        latest_trade_date = self.market_data._resolve_regime_trade_date(None)
        if not latest_trade_date:
            return self.market_data.get_market_regime()
        repo = LowBuyHotIndustryRepository(db)
        recent_rows = repo.fetch_recent_valids(latest_trade_date=latest_trade_date, limit=3)
        recent_hot_sequences: list[list[str]] = []
        for row in recent_rows:
            try:
                industries = json.loads(row.industries_json or "[]")
            except Exception:
                industries = []
            if isinstance(industries, list) and industries:
                recent_hot_sequences.append([str(item) for item in industries if str(item).strip()])
        latest_row = repo.fetch_latest_valid(latest_trade_date=latest_trade_date)
        hot_industries: list[str] = []
        hot_industry_source = ""
        hot_industry_source_text = ""
        if latest_row is not None:
            try:
                cached = json.loads(latest_row.industries_json or "[]")
            except Exception:
                cached = []
            if isinstance(cached, list):
                hot_industries = [str(item) for item in cached if str(item).strip()]
            hot_industry_source = latest_row.source or ""
            if hot_industries:
                hot_industry_source_text = {
                    "board_strength": "热点来源：板块涨幅实时榜",
                    "pool_inference": "热点来源：涨停池推断",
                    "historical_cache": "热点来源：历史缓存回退",
                    "historical_cache_stale": "热点来源：历史缓存弱回退",
                }.get(hot_industry_source, "热点来源：历史缓存回退")
        return self.market_data.get_market_regime(
            latest_trade_date=latest_trade_date,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=recent_hot_sequences,
        )

    @staticmethod
    def _dedupe_keep_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result


def _request_allows_lightweight_path(request: AnalysisRequest) -> bool:
    return not request.include_ai and not request.include_events and not request.include_microstructure
