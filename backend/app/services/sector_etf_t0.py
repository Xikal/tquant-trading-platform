from __future__ import annotations

from dataclasses import dataclass
from math import comb
from typing import Any

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import (
    MarketModelValidationMetric,
    MarketModelValidationResponse,
    SectorEtfT0Opportunity,
    SectorEtfT0Response,
)
from app.services.etf.universe import etf_profile_for
from app.services.etf.t0_signal import evaluate_etf_t0_signal
from app.services.low_buy.service import LowBuyScreenerService
from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS
from app.services.market_data import MarketDataService
from app.services.market_model_observation_service import MarketModelObservationService


@dataclass(frozen=True)
class SectorEtfProxy:
    symbol: str
    name: str
    aliases: tuple[str, ...]


SECTOR_ETF_PROXIES: tuple[SectorEtfProxy, ...] = (
    SectorEtfProxy("510300", "沪深300ETF", ("宽基", "沪深300", "大盘", "权重")),
    SectorEtfProxy("159915", "创业板ETF", ("创业板", "成长")),
    SectorEtfProxy("588000", "科创50ETF", ("科创", "科创50")),
    SectorEtfProxy("515000", "科技ETF", ("人工智能", "算力", "软件")),
    SectorEtfProxy("512760", "芯片ETF", ("芯片", "电子元件")),
    SectorEtfProxy("512660", "军工ETF", ("军工", "国防军工", "航天航空", "船舶")),
    SectorEtfProxy("512880", "证券ETF", ("证券", "券商", "金融")),
    SectorEtfProxy("512480", "半导体ETF", ("半导体",)),
    SectorEtfProxy("515790", "光伏ETF", ("光伏", "新能源", "电力设备")),
    SectorEtfProxy("512170", "医疗ETF", ("医疗", "医药", "医疗器械")),
    SectorEtfProxy("510310", "消费ETF", ("消费", "食品饮料", "商贸零售", "家电")),
    SectorEtfProxy("512690", "酒ETF", ("白酒",)),
    SectorEtfProxy("512400", "有色金属ETF", ("有色", "有色金属", "小金属")),
    SectorEtfProxy("516780", "稀土ETF", ("稀土",)),
    SectorEtfProxy("512200", "房地产ETF", ("房地产", "地产", "房屋建设")),
    SectorEtfProxy("159930", "能源ETF", ("能源", "石油石化")),
    SectorEtfProxy("515220", "煤炭ETF", ("煤炭",)),
    SectorEtfProxy("512800", "银行ETF", ("银行",)),
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
        observation_service: MarketModelObservationService | None = None,
    ) -> None:
        self.market_data = market_data or MarketDataService()
        self._low_buy = low_buy
        self.observations = observation_service or MarketModelObservationService()

    @property
    def low_buy(self) -> LowBuyScreenerService:
        if self._low_buy is None:
            self._low_buy = LowBuyScreenerService()
        return self._low_buy

    def build(self, db: Session, *, limit: int = 8, record_observations: bool = True) -> SectorEtfT0Response:
        params = _params()
        board_limit = max(
            _int_param(params, "priority_min_limit"),
            limit * _int_param(params, "priority_limit_multiplier"),
        )
        board = self.low_buy.priority_board(db=db, limit=board_limit)
        response = self.build_from_priority_board(board, limit=limit)
        if record_observations:
            self._record_observations(db, response)
            db.commit()
        return response

    def build_from_priority_board(self, board: Any, *, limit: int = 8) -> SectorEtfT0Response:
        """Derive ETF T+0 ideas from an already materialized priority board.

        Monitor pages already load the all-strategy board. Reusing that payload
        keeps ETF suggestions on the same read path and avoids a second priority
        board calculation during every dashboard refresh.
        """

        regime = self.market_data.get_market_regime_fast()
        params = _params()
        items = []
        used_etfs: set[str] = set()
        for candidate in _field(board, "items", []) or []:
            sector_name = _string_value(
                _field(candidate, "sector_name")
                or _field(candidate, "industry_tier_text")
                or ""
            )
            proxy = _proxy_for_sector(sector_name, params=params)
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
            profile = etf_profile_for(proxy.symbol, name=proxy.name, instrument_type="fund")
            t0_eligible = bool(profile and profile.same_day_sell_allowed)
            intraday_signal = None
            if t0_eligible:
                intraday_signal = self._intraday_signal(proxy, quote, params=params)
            confidence = _confidence(
                _float_value(_field(candidate, "priority_score")),
                regime.state,
                quote.change_pct,
                params,
            )
            entry_low = round(quote.last_price * _float_param(params, "entry_low_multiplier"), 3)
            entry_high = round(quote.last_price * _float_param(params, "entry_high_multiplier"), 3)
            sell_low = round(quote.last_price * _float_param(params, "sell_low_multiplier"), 3)
            sell_high = round(quote.last_price * _float_param(params, "sell_high_multiplier"), 3)
            expected_edge = round((sell_low / max(entry_high, 0.01) - 1.0) * 100, 2)
            positive_confidence_min = _float_param(params, "positive_confidence_min")
            positive_t_candidate = t0_eligible and confidence >= positive_confidence_min
            if t0_eligible:
                eligibility_text = "ETF universe 已放行 T+0，执行前仍需检查流动性、价差和数据 freshness。"
            else:
                eligibility_text = "ETF universe 未放行 T+0，只展示替代观察，不进入自动做T执行。"
            items.append(
                SectorEtfT0Opportunity(
                    sector_name=sector_name or "行业代理",
                    etf_symbol=proxy.symbol,
                    etf_name=proxy.name,
                    etf_category=profile.category.value if profile is not None else "unknown",
                    t0_eligible=t0_eligible,
                    settlement_rule=profile.settlement_rule if profile is not None else "t1",
                    tracking_index=profile.tracking_index if profile is not None else "",
                    min_amount=profile.min_amount if profile is not None else 0.0,
                    max_spread_bps=profile.max_spread_bps if profile is not None else 0.0,
                    slippage_bps=profile.slippage_bps if profile is not None else 0.0,
                    premium_discount_available=profile.premium_discount_available if profile is not None else False,
                    t0_eligibility_text=eligibility_text,
                    source_signal_symbol=_string_value(_field(candidate, "symbol")),
                    source_signal_name=_string_value(_field(candidate, "name")),
                    source_signal_state=buy_signal_state,
                    source_strategy=_string_value(_field(candidate, "strategy_title")),
                    source_signal_text=_string_value(_field(candidate, "buy_signal_text")),
                    last_price=quote.last_price,
                    change_pct=quote.change_pct,
                    bias="positive_t" if positive_t_candidate else "hold",
                    bias_text="ETF 正T候选" if positive_t_candidate else "T+0未放行" if not t0_eligible else "只观察",
                    confidence=confidence,
                    entry_zone=f"{entry_low:.3f}-{entry_high:.3f}",
                    sell_zone=f"{sell_low:.3f}-{sell_high:.3f}",
                    stop_loss=round(quote.last_price * _float_param(params, "stop_loss_multiplier"), 3),
                    expected_edge_pct=expected_edge,
                    intraday_signal_action=_field(intraday_signal, "action", "unavailable"),
                    intraday_signal_text=_field(intraday_signal, "action_text", "分钟信号待刷新"),
                    intraday_signal_confidence=_float_value(_field(intraday_signal, "confidence", 0.0)),
                    intraday_signal_snapshot=_field(intraday_signal, "to_dict", lambda: {})(),
                    intraday_risk_flags=list(_field(intraday_signal, "risk_flags", []) or []),
                    reason=f"{_string_value(_field(candidate, 'name'))} 属于该方向强信号，优先用 ETF 降低个股波动和 T+1 风险。",
                    risk=f"{eligibility_text} ETF 仍受板块回落影响；价差低于 {_float_param(params, 'fee_edge_buffer_pct'):.1f}% 时不做，避免手续费和滑点吞噬收益。",
                    data_quality_text=getattr(quote, "data_quality_message", "") or getattr(quote, "source_quality", "") or "行情正常",
                )
            )
            used_etfs.add(proxy.symbol)
            if len(items) >= min(limit, _int_param(params, "max_opportunities")):
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

    def _intraday_signal(self, proxy: SectorEtfProxy, quote: Any, *, params: dict[str, Any]):
        try:
            bars = self.market_data.get_intraday_bars(
                proxy.symbol,
                period="1m",
                limit=_int_param(params, "signal_bar_limit"),
                allow_slow_fallback=False,
            )
        except TypeError:
            try:
                bars = self.market_data.get_intraday_bars(proxy.symbol, period="1m", limit=_int_param(params, "signal_bar_limit"))
            except Exception:
                return None
        except Exception:
            return None
        if not bars:
            return None
        spread_bps = _quote_spread_bps(quote)
        return evaluate_etf_t0_signal(
            symbol=proxy.symbol,
            name=proxy.name,
            bars=bars,
            spread_bps=spread_bps,
            data_quality=getattr(quote, "data_quality", "fresh") or "fresh",
            params=params,
        )

    def validation_report(self, db: Session, *, limit: int = 8) -> MarketModelValidationResponse:
        """Return an automatic acceptance report for the ETF T+0 model.

        This is a production guardrail, not a promise of profit.  The report
        checks whether the model currently has enough high-quality opportunities
        and whether the estimated ETF edge clears a fee/slippage buffer.
        """

        payload = self.build(db, limit=limit, record_observations=False)
        params = _params()
        opportunities = payload.opportunities
        historical = self.observations.summarize(db, model_key="sector_etf_t0", lookback_days=60)
        actionable = [item for item in opportunities if item.bias == "positive_t"]
        edge_pass = [
            item for item in actionable
            if item.expected_edge_pct >= _float_param(params, "fee_edge_buffer_pct")
            and item.confidence >= _float_param(params, "positive_confidence_min")
        ]
        sample_count = len(opportunities)
        pass_rate = len(edge_pass) / max(len(actionable), 1) * 100.0 if actionable else 0.0
        avg_edge = sum(item.expected_edge_pct for item in actionable) / max(len(actionable), 1) if actionable else 0.0
        current_ready = len(edge_pass) >= _int_param(params, "production_min_edge_pass") and pass_rate >= _float_param(params, "production_pass_rate_min_pct")
        historical_gate = self.historical_acceptance(db, params=params, historical=historical)
        settled_count = historical_gate["settled_count"]
        historical_success_rate = historical_gate["success_rate_pct"]
        p_value = historical_gate["p_value"]
        historical_ready = historical_gate["production_ready"]
        production_ready = current_ready and historical_ready
        return MarketModelValidationResponse(
            model_key="sector_etf_t0",
            generated_at=beijing_now_string(),
            production_ready=production_ready,
            acceptance_status="passed" if production_ready else "watch",
            metrics=[
                MarketModelValidationMetric(
                    name="ETF 价差覆盖检查",
                    status="passed" if current_ready else "watch",
                    sample_count=sample_count,
                    pass_rate_pct=round(pass_rate, 2),
                    avg_edge_pct=round(avg_edge, 2),
                    notes="按当前机会池检查 ETF 预期价差是否覆盖手续费和滑点。",
                ),
                MarketModelValidationMetric(
                    name="影子跟踪历史绩效",
                    status="passed" if historical_ready else "watch",
                    sample_count=int(historical["sample_count"]),
                    settled_count=settled_count,
                    pending_count=int(historical["pending_count"]),
                    pass_rate_pct=round(historical_success_rate, 2),
                    avg_edge_pct=round(float(historical["avg_return_1d_pct"] or 0.0), 2),
                    avg_return_1d_pct=round(float(historical["avg_return_1d_pct"] or 0.0), 2),
                    avg_return_3d_pct=round(float(historical["avg_return_3d_pct"] or 0.0), 2),
                    avg_max_adverse_5d_pct=round(float(historical["avg_max_adverse_5d_pct"] or 0.0), 2),
                    p_value=round(p_value, 6),
                    notes=(
                        "按观察样本后续日线结算胜率、1日/3日收益和最大不利波动；"
                        f"需满足已结算≥{_int_param(params, 'production_min_settled_samples')}、"
                        f"胜率≥{_float_param(params, 'production_min_success_rate_pct'):.1f}%、"
                        f"p≤{_float_param(params, 'production_max_p_value'):.3f}。"
                    ),
                )
            ],
            notes=[
                f"行业 ETF 做T已接入影子跟踪和日线结算；待结算样本 {int(historical['pending_count'])} 个。",
                "未达到统计显著性验收时只展示观察，不作为自动交易指令。",
            ],
        )

    def historical_acceptance(
        self,
        db: Session,
        *,
        params: dict[str, Any] | None = None,
        historical: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Statistical gate used before ETF T+0 reaches automatic execution."""

        resolved = params or _params()
        summary = historical or self.observations.summarize(db, model_key="sector_etf_t0", lookback_days=60)
        settled_count = int(summary.get("settled_count") or 0)
        success_count = int(summary.get("success_count") or 0)
        success_rate = float(summary.get("success_rate_pct") or 0.0)
        p_value = _binomial_one_sided_p_value(success_count, settled_count, baseline=0.5)
        production_ready = (
            settled_count >= _int_param(resolved, "production_min_settled_samples")
            and success_rate >= _float_param(resolved, "production_min_success_rate_pct")
            and p_value <= _float_param(resolved, "production_max_p_value")
        )
        return {
            "production_ready": production_ready,
            "settled_count": settled_count,
            "success_count": success_count,
            "success_rate_pct": success_rate,
            "p_value": p_value,
        }

    def _record_observations(self, db: Session, response: SectorEtfT0Response) -> None:
        for item in response.opportunities:
            self.observations.record(
                db,
                model_key="sector_etf_t0",
                symbol=item.etf_symbol,
                name=item.etf_name,
                signal_state=item.bias,
                confidence=item.confidence,
                expected_edge_pct=item.expected_edge_pct,
                payload=item.model_dump(),
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


def _proxy_for_sector(sector_name: str, params: dict[str, Any] | None = None) -> SectorEtfProxy | None:
    text = str(sector_name or "")
    if not text:
        return None
    mapped = _proxy_from_config(text, params or {})
    if mapped is not None:
        return mapped
    for proxy in SECTOR_ETF_PROXIES:
        if any(alias in text for alias in proxy.aliases):
            return proxy
    return None


def resolve_sector_etf_proxy(sector_name: str, params: dict[str, Any] | None = None) -> SectorEtfProxy | None:
    return _proxy_for_sector(sector_name, params=params)


def _proxy_from_config(sector_name: str, params: dict[str, Any]) -> SectorEtfProxy | None:
    mapping = params.get("sector_proxy_map")
    if not isinstance(mapping, dict):
        return None
    normalized = sector_name.strip()
    exact = mapping.get(normalized)
    if exact is None:
        for key, value in mapping.items():
            if str(key or "") and str(key) in normalized:
                exact = value
                break
    if not isinstance(exact, dict):
        return None
    symbol = str(exact.get("symbol") or "").strip()
    name = str(exact.get("name") or "").strip()
    if not symbol or not name:
        return None
    return SectorEtfProxy(symbol=symbol, name=name, aliases=(normalized,))


def _confidence(priority_score: float, market_state: str, change_pct: float, params: dict[str, Any]) -> float:
    score = _float_param(params, "confidence_base") + max(
        float(priority_score or 0.0) - _float_param(params, "confidence_priority_floor"),
        0.0,
    ) * _float_param(params, "confidence_priority_weight")
    if market_state in {"broad_rally", "repair", "weight_support_active"}:
        score += _float_param(params, "confidence_positive_market_bonus")
    if market_state in {"risk_release", "high_flyer_retreat"}:
        score -= _float_param(params, "confidence_negative_market_penalty")
    if change_pct > _float_param(params, "confidence_hot_change_threshold"):
        score -= _float_param(params, "confidence_hot_change_penalty")
    if change_pct < _float_param(params, "confidence_weak_change_threshold"):
        score -= _float_param(params, "confidence_weak_change_penalty")
    return round(max(0.0, min(score, _float_param(params, "confidence_cap"))), 1)


def _params() -> dict[str, Any]:
    from app.services.quant.runtime_parameters import get_market_sector_etf_t0

    values = get_market_sector_etf_t0()
    return {**MARKET_SECTOR_ETF_T0_DEFAULTS, **values} if isinstance(values, dict) else dict(MARKET_SECTOR_ETF_T0_DEFAULTS)


def _float_param(params: dict[str, Any], key: str) -> float:
    try:
        return float(params.get(key, MARKET_SECTOR_ETF_T0_DEFAULTS[key]))
    except (KeyError, TypeError, ValueError):
        return float(MARKET_SECTOR_ETF_T0_DEFAULTS[key])


def _int_param(params: dict[str, Any], key: str) -> int:
    return int(round(_float_param(params, key)))


def _quote_spread_bps(quote: Any) -> float:
    raw = _field(quote, "spread_bps")
    if raw is not None:
        return _float_value(raw)
    price = _float_value(_field(quote, "last_price"))
    bid = _float_value(_field(quote, "best_bid"))
    ask = _float_value(_field(quote, "best_ask"))
    if price > 0 and ask > bid > 0:
        return round((ask - bid) / price * 10000, 4)
    return 0.0


def _binomial_one_sided_p_value(success_count: int, sample_count: int, *, baseline: float) -> float:
    if sample_count <= 0 or success_count <= 0:
        return 1.0
    success_count = max(0, min(success_count, sample_count))
    probability = 0.0
    for k in range(success_count, sample_count + 1):
        probability += comb(sample_count, k) * (baseline ** k) * ((1 - baseline) ** (sample_count - k))
    return max(0.0, min(probability, 1.0))
