from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import PairedHedgeIdeaOut, PairedHedgeLegOut, PairedHedgeResearchResponse
from app.services.low_buy.service import LowBuyScreenerService
from app.services.market_data import MarketDataService
from app.services.sector_etf_t0 import resolve_sector_etf_proxy


class PairedHedgeResearchService:
    """Research-only stock + ETF hedge ideas.

    A-share accounts cannot short most ETFs in the same way as futures/options.
    Therefore this endpoint only standardizes research legs and exposure
    estimates; it is not consumed by paper auto-trading.
    """

    def __init__(
        self,
        *,
        low_buy: LowBuyScreenerService | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self.low_buy = low_buy or LowBuyScreenerService()
        self.market_data = market_data or MarketDataService()

    def build(self, db: Session, *, limit: int = 8) -> PairedHedgeResearchResponse:
        board = self.low_buy.priority_board(db=db, limit=max(limit * 2, 12))
        ideas = self.build_from_priority_board(board, limit=limit)
        return PairedHedgeResearchResponse(
            updated_at=beijing_now_string(),
            total=len(ideas),
            disclaimer="配对/对冲研究仅用于复盘和假设分析，不自动下单，不构成真实对冲或收益承诺。",
            ideas=ideas,
            notes=[
                "多腿组合仅用于研究，不自动下单，也不代表可直接做空 ETF。",
                "对冲比例按信号强度、行业代理 ETF 和当前价差估算，需用回测验证后再进入生产。",
            ],
        )

    def build_from_priority_board(self, board: Any, *, limit: int = 8) -> list[PairedHedgeIdeaOut]:
        ideas: list[PairedHedgeIdeaOut] = []
        for candidate in _field(board, "items", []) or []:
            if len(ideas) >= limit:
                break
            sector = str(_field(candidate, "sector_name") or "")
            proxy = resolve_sector_etf_proxy(sector)
            if proxy is None:
                continue
            stock_symbol = str(_field(candidate, "symbol") or "")
            if not stock_symbol:
                continue
            try:
                quotes = self.market_data.get_quotes_batch([stock_symbol, proxy.symbol])
            except Exception:
                continue
            stock_quote = quotes.get(stock_symbol)
            etf_quote = quotes.get(proxy.symbol)
            if stock_quote is None or etf_quote is None or stock_quote.last_price <= 0 or etf_quote.last_price <= 0:
                continue
            priority_score = _float(_field(candidate, "priority_score"))
            hedge_ratio = _hedge_ratio(priority_score, _float(_field(candidate, "change_pct")), etf_quote.change_pct)
            tracking_error = abs(float(stock_quote.change_pct or 0.0) - float(etf_quote.change_pct or 0.0))
            ideas.append(
                PairedHedgeIdeaOut(
                    source_signal_symbol=stock_symbol,
                    source_signal_name=str(_field(candidate, "name") or ""),
                    source_strategy=str(_field(candidate, "strategy_title") or ""),
                    sector_name=sector or "未分类",
                    confidence=round(min(max(priority_score, 0.0), 100.0), 1),
                    hedge_ratio=hedge_ratio,
                    gross_exposure_pct=round(100.0 + hedge_ratio * 100.0, 1),
                    net_exposure_pct=round(100.0 - hedge_ratio * 100.0, 1),
                    estimated_beta=round(max(0.0, 1.0 - hedge_ratio * 0.7), 3),
                    hedge_cost_pct=round(0.08 + hedge_ratio * 0.12, 3),
                    tracking_error_pct=round(tracking_error, 2),
                    legs=[
                        PairedHedgeLegOut(
                            role="alpha_stock",
                            symbol=stock_symbol,
                            name=str(_field(candidate, "name") or ""),
                            side="long",
                            notional_ratio=1.0,
                            latest_price=float(stock_quote.last_price or 0.0),
                            change_pct=float(stock_quote.change_pct or 0.0),
                            reason="低吸优先榜 alpha 信号腿",
                        ),
                        PairedHedgeLegOut(
                            role="sector_etf_hedge",
                            symbol=proxy.symbol,
                            name=proxy.name,
                            side="hedge_research",
                            notional_ratio=hedge_ratio,
                            latest_price=float(etf_quote.last_price or 0.0),
                            change_pct=float(etf_quote.change_pct or 0.0),
                            reason="行业 ETF 代理对冲腿，仅研究展示",
                        ),
                    ],
                    risk_notes=[
                        "A 股普通账户不能把该组合视为真实做空执行方案。",
                        "ETF 与个股跟踪误差较大时，对冲保护会失效。",
                    ],
                )
            )
        return ideas


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _hedge_ratio(priority_score: float, stock_change_pct: float, etf_change_pct: float) -> float:
    base = 0.25 if priority_score >= 90 else 0.35 if priority_score >= 82 else 0.45
    if stock_change_pct > 4.0:
        base += 0.08
    if etf_change_pct < -1.0:
        base += 0.06
    return round(min(max(base, 0.15), 0.6), 2)
