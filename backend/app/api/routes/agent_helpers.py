from __future__ import annotations

import json
import time
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import AgentAuditLog
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentAuditLogOut,
    AgentBacktestRequest,
    AgentBacktestResponse,
    AgentCompareStrategiesResponse,
    AgentMarketSentimentResponse,
    AgentPaperOrderRequest,
    AgentPaperOrderResponse,
    AgentPositionTSignalRequest,
    AgentPositionTSignalResponse,
    AgentSectorFundFlowResponse,
    AgentSectorHeatmapResponse,
    SectorFundFlowItem,
)
from app.services.agent_context_service import AgentContextService
from app.services.market_data import MarketDataService
from app.services.market.regime_quality import market_regime_quality_text
from app.services.paper import PaperAccountService, PaperOrderService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker

_SECTOR_HEATMAP_CACHE: dict[tuple[int], tuple[float, AgentSectorHeatmapResponse]] = {}
_SECTOR_HEATMAP_TTL_SECONDS = 180.0

_SECTOR_FUND_FLOW_CACHE: dict[tuple[str, str, int], tuple[float, AgentSectorFundFlowResponse]] = {}
_SECTOR_FUND_FLOW_TTL_SECONDS = 120.0


def agent_backtest_strategy(
    service: AgentContextService,
    db: Session,
    payload: AgentBacktestRequest,
) -> AgentBacktestResponse:
    custom = getattr(service, "backtest_strategy", None)
    if callable(custom):
        return custom(db, payload)
    try:
        result = service.low_buy_screener.execution_backtest(
            db,
            strategy=payload.strategy_key,
            lookback_days=payload.lookback_days,
        )
    except Exception as exc:
        return AgentBacktestResponse(
            strategy_key=payload.strategy_key,
            lookback_days=payload.lookback_days,
            data_quality="limited",
            data_quality_text="回测服务暂不可用",
            notes=[str(exc)[:160]],
            summary="回测未完成，已返回结构化降级摘要。",
        )
    return AgentBacktestResponse(
        strategy_key=result.strategy_key,
        lookback_days=result.lookback_days,
        evaluated_signals=result.evaluated_signals,
        filled_signals=result.filled_signals,
        win_rate=result.win_rate,
        net_win_rate=result.net_win_rate,
        avg_net_return_pct=result.avg_net_return_pct,
        profit_factor=result.profit_factor,
        max_adverse_pct=result.max_adverse_pct,
        data_quality=result.data_quality,
        data_quality_text=result.data_quality_text,
        notes=result.notes[:4],
        summary=(
            f"{result.strategy_key} 近 {result.lookback_days} 日："
            f"样本 {result.evaluated_signals}，成交 {result.filled_signals}，"
            f"胜率 {result.win_rate:.2f}%，平均收益 {result.avg_net_return_pct:.2f}%。"
        ),
    )


def agent_compare_strategies(
    service: AgentContextService,
    db: Session,
    *,
    strategy_keys: list[str],
    lookback_days: int,
) -> AgentCompareStrategiesResponse:
    custom = getattr(service, "compare_strategies", None)
    if callable(custom):
        return custom(db, strategy_keys, lookback_days=lookback_days)
    unique_keys = list(dict.fromkeys([key.strip() for key in strategy_keys if key.strip()]))
    items: list[dict] = []
    for strategy_key in unique_keys:
        result = agent_backtest_strategy(
            service,
            db,
            AgentBacktestRequest(strategy_key=strategy_key, lookback_days=lookback_days),
        )
        items.append(
            {
                "strategy_key": result.strategy_key,
                "evaluated_signals": result.evaluated_signals,
                "filled_signals": result.filled_signals,
                "win_rate": result.win_rate,
                "avg_net_return_pct": result.avg_net_return_pct,
                "profit_factor": result.profit_factor,
                "data_quality": result.data_quality,
            }
        )
    items.sort(key=lambda item: (item.get("avg_net_return_pct", 0.0), item.get("win_rate", 0.0)), reverse=True)
    best = str(items[0]["strategy_key"]) if items else ""
    return AgentCompareStrategiesResponse(
        strategy_keys=unique_keys,
        lookback_days=lookback_days,
        strategy_count=len(unique_keys),
        items=items,
        best_strategy_key=best,
        summary=f"已对比 {len(unique_keys)} 个策略，当前排序第一：{best or '无'}。",
    )


def agent_create_paper_order(
    service: AgentContextService,
    db: Session,
    payload: AgentPaperOrderRequest,
    *,
    user_id: int | None,
) -> AgentPaperOrderResponse:
    custom = getattr(service, "create_paper_order", None)
    if callable(custom):
        return custom(db, payload, user_id=user_id)
    account = _resolve_agent_paper_account(db, payload.account_id, user_id=user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="无可用模拟账户。")
    try:
        order = PaperOrderService(db).create_order(
            account_id=account.id,
            symbol=payload.symbol.strip(),
            name=payload.name or payload.symbol.strip(),
            side=payload.side,
            order_type="limit",
            quantity=payload.quantity,
            price=Decimal(str(payload.price)),
            source="agent",
            strategy_key=payload.strategy_key,
            reason=payload.reason,
            signal_snapshot={"agent_tool": "create_paper_order"},
            current_price=Decimal(str(payload.price)),
            quote_time=datetime.now(),
            is_suspended=False,
        )
        PaperRiskCircuitBreaker(db).evaluate_account(account.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentPaperOrderResponse(
        ok=True,
        account_id=account.id,
        order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=float(order.price or payload.price),
        status=order.status,
        summary="模拟盘订单已创建并按模拟撮合规则处理。",
    )


def agent_market_sentiment(
    service: AgentContextService,
    market_data: MarketDataService,
) -> AgentMarketSentimentResponse:
    custom = getattr(service, "market_sentiment", None)
    if callable(custom):
        return custom()
    regime = market_data.get_market_regime_fast()
    return AgentMarketSentimentResponse(
        updated_at=_now_string(),
        state=regime.state,
        state_text=regime.label,
        breadth_ready=regime.breadth_ready,
        emotion_ready=regime.emotion_ready,
        stock_up_ratio=round(regime.stock_up_ratio, 4),
        stock_median_change=round(regime.stock_median_change, 4),
        limit_up_count=int(regime.limit_up_count or 0),
        limit_down_count=regime.limit_down_count,
        broken_board_ratio=round(regime.broken_board_ratio, 4),
        promotion_ratio=round(regime.promotion_ratio, 4),
        board_height=int(regime.board_height or 0),
        hot_industries=regime.hot_industries[:8],
        hot_turnover=round(regime.hot_turnover, 4),
        data_quality_text=market_regime_quality_text(regime),
    )


def agent_sector_heatmap(
    service: AgentContextService,
    market_data: MarketDataService,
    *,
    limit: int,
) -> AgentSectorHeatmapResponse:
    custom = getattr(service, "sector_heatmap", None)
    if callable(custom):
        return custom(limit=limit)
    cache_key = (int(limit),)
    now = time.monotonic()
    cached = _SECTOR_HEATMAP_CACHE.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    # Hermes/Feishu 的日报与问答需要快速响应。优先使用市场状态快照
    # 已经沉淀出的热点行业，避免在请求线程同步等待板块宽度外部源。
    sentiment = agent_market_sentiment(service, market_data)
    sectors: list[dict] = [
        {"sector_name": name, "change_pct": 0.0, "rank": index + 1}
        for index, name in enumerate(sentiment.hot_industries[:limit])
    ]
    if sectors:
        response = AgentSectorHeatmapResponse(
            updated_at=_now_string(),
            limit=limit,
            sectors=sectors,
            data_quality_text="快速热点快照，涨跌幅等待后台板块数据刷新",
        )
        _SECTOR_HEATMAP_CACHE[cache_key] = (now + _SECTOR_HEATMAP_TTL_SECONDS, response)
        return response

    try:
        snapshots = market_data.get_sector_heatmap(limit=limit)
    except Exception:
        snapshots = []
    if snapshots:
        for item in snapshots[:limit]:
            sectors.append(
                {
                    "sector_name": item.sector_name,
                    "change_pct": round((item.sector_strength - 50.0) / 8.0, 4),
                    "rank": len(sectors) + 1,
                }
            )
    response = AgentSectorHeatmapResponse(
        updated_at=_now_string(),
        limit=limit,
        sectors=sectors,
        data_quality_text="实时板块榜" if sectors else "板块热度暂无可用数据",
    )
    _SECTOR_HEATMAP_CACHE[cache_key] = (now + _SECTOR_HEATMAP_TTL_SECONDS, response)
    return response


def agent_sector_fund_flow(
    market_data: MarketDataService,
    *,
    period: str,
    sector_type: str,
    limit: int,
) -> AgentSectorFundFlowResponse:
    """Fetch sector capital flow from EastMoney datacenter API."""
    cache_key = (period, sector_type, limit)
    now = time.monotonic()
    cached = _SECTOR_FUND_FLOW_CACHE.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    try:
        result = market_data.provider_router.fetch_sector_fund_flow(
            period=period, sector_type=sector_type, limit=limit,
        )
    except Exception:
        result = None

    if result and result.usable and result.data is not None:
        flow_data = result.data
        items = _sector_fund_flow_items(flow_data, limit=limit)
        response = AgentSectorFundFlowResponse(
            updated_at=_now_string(),
            period=period,
            sector_type=sector_type,
            total=_sector_fund_flow_total(flow_data, fallback=len(items)),
            items=items,
            data_quality_text=_sector_fund_flow_quality_text(result.source, sector_type, period, bool(items)),
        )
    else:
        response = AgentSectorFundFlowResponse(
            updated_at=_now_string(),
            period=period,
            sector_type=sector_type,
            total=0,
            items=[],
            data_quality_text="板块资金流数据暂不可用",
        )

    _SECTOR_FUND_FLOW_CACHE[cache_key] = (now + _SECTOR_FUND_FLOW_TTL_SECONDS, response)
    return response


def _sector_fund_flow_items(flow_data, *, limit: int) -> list[SectorFundFlowItem]:
    """Normalize typed EastMoney results and legacy DataFrame fallbacks."""
    raw_items = getattr(flow_data, "items", None)
    if isinstance(raw_items, list):
        return [
            SectorFundFlowItem(
                board_code=str(getattr(item, "board_code", "")),
                sector_name=str(getattr(item, "sector_name", "")),
                net_flow_yi=round(_float(getattr(item, "net_flow", 0.0)) / 1e8, 2),
                net_flow_rank=idx + 1,
            )
            for idx, item in enumerate(raw_items[:limit])
        ]
    if hasattr(flow_data, "iterrows"):
        return _sector_fund_flow_items_from_frame(flow_data, limit=limit)
    return []


def _sector_fund_flow_items_from_frame(frame, *, limit: int) -> list[SectorFundFlowItem]:
    if frame is None or getattr(frame, "empty", True):
        return []
    name_column = _find_frame_column(frame, ("名称", "板块名称", "行业名称", "行业", "sector_name"))
    flow_column = _find_frame_column(frame, ("主力净流入-净额", "主力净流入", "净流入-净额", "净流入", "净额", "amount"))
    code_column = _find_frame_column(frame, ("代码", "板块代码", "board_code"))
    if not name_column or not flow_column:
        return []
    try:
        sorted_frame = frame.assign(_fund_flow_value=frame[flow_column].map(_float)).sort_values(
            "_fund_flow_value",
            ascending=False,
        )
    except Exception:
        sorted_frame = frame
    items: list[SectorFundFlowItem] = []
    for _, row in sorted_frame.head(limit).iterrows():
        sector_name = str(row.get(name_column, ""))
        if not sector_name:
            continue
        items.append(
            SectorFundFlowItem(
                board_code=str(row.get(code_column, "")) if code_column else "",
                sector_name=sector_name,
                net_flow_yi=round(_float(row.get(flow_column, 0.0)) / 1e8, 2),
                net_flow_rank=len(items) + 1,
            )
        )
    return items


def _sector_fund_flow_total(flow_data, *, fallback: int) -> int:
    try:
        total = getattr(flow_data, "total", None)
        if total is None:
            raise TypeError("missing total")
        return int(total)
    except (TypeError, ValueError):
        if hasattr(flow_data, "__len__"):
            try:
                return int(len(flow_data))
            except Exception:
                pass
        return fallback


def _sector_fund_flow_quality_text(source: str, sector_type: str, period: str, has_items: bool) -> str:
    if not has_items:
        return "板块资金流数据暂不可用"
    source_name = {
        "eastmoney": "东方财富数据中心",
        "akshare": "AkShare",
        "local": "本地快照估算",
    }.get(source or "", source or "市场数据源")
    return f"{source_name} {sector_type}板块 {period}主力净流入"


def _find_frame_column(frame, candidates: tuple[str, ...]) -> str | None:
    columns = list(getattr(frame, "columns", []))
    for candidate in candidates:
        if candidate in columns:
            return candidate
    for column in columns:
        text = str(column)
        if any(candidate in text for candidate in candidates):
            return str(column)
    return None


def agent_position_t_signal(
    service: AgentContextService,
    db: Session,
    payload: AgentPositionTSignalRequest,
) -> AgentPositionTSignalResponse:
    custom = getattr(service, "position_t_signal", None)
    if callable(custom):
        return custom(db, payload)
    analysis = service.analysis(
        db,
        AgentAnalysisRequest(
            symbol=payload.symbol,
            base_position=max(payload.shares, 0),
            available_position=max(payload.shares, 0),
            cost_basis=payload.cost_basis or None,
            include_ai=False,
        ),
    )
    return AgentPositionTSignalResponse(
        symbol=analysis.symbol,
        name=analysis.name,
        action=analysis.action,
        action_text=analysis.action_text,
        signal_score=analysis.signal_score,
        tradability_score=analysis.tradability_score,
        risk_level=analysis.risk_level,
        entry_price=analysis.entry_price,
        exit_price=analysis.exit_price,
        stop_loss=analysis.stop_loss,
        position_pct=analysis.position_pct,
        summary=analysis.summary,
        reasons=analysis.reasons,
        blocking_rules=analysis.blocking_rules,
    )


def audit_log_out(row: AgentAuditLog) -> AgentAuditLogOut:
    result = _json_dict(row.result_summary)
    return AgentAuditLogOut(
        trace_id=row.trace_id,
        agent_id=str(result.get("agent_id") or ""),
        provider=row.provider_name,
        tool_name=row.tool_name,
        outcome=str(result.get("outcome") or ("success" if row.ok else "error")),
        latency_ms=int(row.duration_ms or 0),
        ip_address=str(result.get("ip_address") or ""),
        params_snapshot=_json_dict(row.input_arguments),
        result_summary=str(result.get("summary") or row.result_summary or "")[:200],
        created_at=row.created_at,
    )


def _resolve_agent_paper_account(db: Session, account_id: int | None, *, user_id: int | None):
    service = PaperAccountService(db)
    if account_id is not None:
        account = service.get_account(account_id)
        if user_id is not None and account.user_id != user_id:
            return None
        return account
    return service.get_or_create_default(user_id)


def _json_dict(raw_value: str) -> dict:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _now_string() -> str:
    from app.core.timezone import beijing_now_string

    return beijing_now_string()
