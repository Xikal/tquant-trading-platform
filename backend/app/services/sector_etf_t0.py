from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import SectorEtfT0Opportunity, SectorEtfT0Response
from app.services.low_buy.service import LowBuyScreenerService
from app.services.market_data import MarketDataService


@dataclass(frozen=True)
class SectorEtfProxy:
    symbol: str
    name: str
    aliases: tuple[str, ...]


SECTOR_ETF_PROXIES: tuple[SectorEtfProxy, ...] = (
    SectorEtfProxy("510300", "沪深300ETF", ("宽基", "沪深300", "大盘", "权重")),
    SectorEtfProxy("159915", "创业板ETF", ("创业板", "成长", "新能源", "医药", "消费电子")),
    SectorEtfProxy("588000", "科创50ETF", ("科创", "半导体", "芯片", "人工智能", "算力", "软件")),
    SectorEtfProxy("512760", "芯片ETF", ("半导体", "芯片", "电子元件")),
    SectorEtfProxy("512660", "军工ETF", ("军工", "国防军工", "航天航空", "船舶")),
    SectorEtfProxy("512880", "证券ETF", ("证券", "券商", "金融")),
    SectorEtfProxy("512480", "半导体ETF", ("半导体", "芯片")),
    SectorEtfProxy("515790", "光伏ETF", ("光伏", "新能源", "电力设备")),
    SectorEtfProxy("512170", "医疗ETF", ("医疗", "医药", "医疗器械")),
)


class SectorEtfT0Service:
    """Build sector ETF T+0 ideas from stock low-buy signals.

    The service intentionally produces advisory ETF plans only. It does not
    place orders and it does not convert stock signals into guaranteed trades.
    """

    def __init__(
        self,
        *,
        market_data: MarketDataService | None = None,
        low_buy: LowBuyScreenerService | None = None,
    ) -> None:
        self.market_data = market_data or MarketDataService()
        self.low_buy = low_buy or LowBuyScreenerService()

    def build(self, db: Session, *, limit: int = 8) -> SectorEtfT0Response:
        board = self.low_buy.priority_board(db=db, limit=max(12, limit * 3))
        return self.build_from_priority_board(board, limit=limit)

    def build_from_priority_board(self, board: Any, *, limit: int = 8) -> SectorEtfT0Response:
        """Derive ETF T+0 ideas from an already materialized priority board.

        Monitor pages already load the all-strategy board. Reusing that payload
        keeps ETF suggestions on the same read path and avoids a second priority
        board calculation during every dashboard refresh.
        """

        regime = self.market_data.get_market_regime_fast()
        items = []
        used_etfs: set[str] = set()
        for candidate in _field(board, "items", []) or []:
            sector_name = _string_value(
                _field(candidate, "sector_name")
                or _field(candidate, "industry_tier_text")
                or ""
            )
            proxy = _proxy_for_sector(sector_name)
            if proxy is None or proxy.symbol in used_etfs:
                continue
            buy_signal_state = _string_value(_field(candidate, "buy_signal_state"))
            simple_bucket = _string_value(_field(candidate, "simple_bucket"))
            if buy_signal_state not in {"buy_now", "soft_buy_now"} and simple_bucket != "wait_price":
                continue
            try:
                quote = self.market_data.get_quote(proxy.symbol)
            except Exception:
                continue
            if quote.last_price <= 0:
                continue
            confidence = _confidence(_float_value(_field(candidate, "priority_score")), regime.state, quote.change_pct)
            entry_low = round(quote.last_price * 0.996, 3)
            entry_high = round(quote.last_price * 1.002, 3)
            sell_low = round(quote.last_price * 1.008, 3)
            sell_high = round(quote.last_price * 1.014, 3)
            expected_edge = round((sell_low / max(entry_high, 0.01) - 1.0) * 100, 2)
            items.append(
                SectorEtfT0Opportunity(
                    sector_name=sector_name or "行业代理",
                    etf_symbol=proxy.symbol,
                    etf_name=proxy.name,
                    source_signal_symbol=_string_value(_field(candidate, "symbol")),
                    source_signal_name=_string_value(_field(candidate, "name")),
                    source_strategy=_string_value(_field(candidate, "strategy_title")),
                    source_signal_text=_string_value(_field(candidate, "buy_signal_text")),
                    last_price=quote.last_price,
                    change_pct=quote.change_pct,
                    bias="positive_t" if confidence >= 60 else "hold",
                    bias_text="ETF 正T候选" if confidence >= 60 else "只观察",
                    confidence=confidence,
                    entry_zone=f"{entry_low:.3f}-{entry_high:.3f}",
                    sell_zone=f"{sell_low:.3f}-{sell_high:.3f}",
                    stop_loss=round(quote.last_price * 0.992, 3),
                    expected_edge_pct=expected_edge,
                    reason=f"{_string_value(_field(candidate, 'name'))} 属于该方向强信号，优先用 ETF 降低个股波动和 T+1 风险。",
                    risk="ETF 仍受板块回落影响；价差低于 0.8% 时不做，避免手续费和滑点吞噬收益。",
                    data_quality_text=getattr(quote, "data_quality_message", "") or getattr(quote, "source_quality", "") or "行情正常",
                )
            )
            used_etfs.add(proxy.symbol)
            if len(items) >= limit:
                break
        notes = [
            "行业 ETF 做T只作为替代执行方案，不等同于个股买入建议。",
            "只在板块方向明确、ETF 价差覆盖手续费和滑点时执行。",
        ]
        return SectorEtfT0Response(
            updated_at=beijing_now_string(),
            market_state=regime.state,
            market_state_text=regime.label,
            total=len(items),
            opportunities=items,
            notes=notes,
        )


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _string_value(value: Any) -> str:
    return str(value or "")


def _float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _proxy_for_sector(sector_name: str) -> SectorEtfProxy | None:
    text = str(sector_name or "")
    if not text:
        return None
    for proxy in SECTOR_ETF_PROXIES:
        if any(alias in text for alias in proxy.aliases):
            return proxy
    return None


def _confidence(priority_score: float, market_state: str, change_pct: float) -> float:
    score = 45.0 + max(float(priority_score or 0.0) - 75.0, 0.0) * 0.8
    if market_state in {"broad_rally", "repair", "weight_support_active"}:
        score += 8.0
    if market_state in {"risk_release", "high_flyer_retreat"}:
        score -= 20.0
    if change_pct > 2.5:
        score -= 8.0
    if change_pct < -2.0:
        score -= 6.0
    return round(max(0.0, min(score, 95.0)), 1)
