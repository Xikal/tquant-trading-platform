from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.schema_defs.agent import AgentDailyReportResponse
from app.services.agent_context_service import AgentContextService
from app.services.agent_research_service import AgentResearchService


class AgentReportService:
    def __init__(self) -> None:
        self.context = AgentContextService()
        self.research = AgentResearchService(context_service=self.context)

    def daily_report(self, db: Session) -> AgentDailyReportResponse:
        watchlist = self.context.watchlist_context(db)
        board = self.context.priority_board(db, limit=12)
        market = self.research.market_state_analysis(db)
        sector = self.research.sector_mainline_analysis(db)
        stock_top = self._stock_top(board)
        risk = self.research.risk_check(
            db,
            [
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "sector": item.get("sector", ""),
                    "position_pct": item.get("suggested_position_pct", 0),
                }
                for item in stock_top[:10]
            ],
        )
        headline = (
            f"今日可执行信号 {watchlist.actionable_count} 个，"
            f"生产优先候选 {board.immediate_count} 个。"
        )
        holding_t_signals = self._holding_t_signals(watchlist)
        operation_checklist = [
            "市场状态是否允许开仓？",
            "目标标的是否在主线板块？",
            "三方分析师结论是否一致？",
            "价格是否已进入买点区？",
            "单票仓位是否 <= 20%？",
            "止损位是否已设定？",
            "是否为 T+1 买入日（卖出需检查可用股数）？",
        ]
        return AgentDailyReportResponse(
            trade_date=beijing_now().strftime("%Y-%m-%d"),
            generated_at=beijing_now_string(),
            headline=headline,
            watchlist_summary={
                "total": watchlist.total,
                "actionable_count": watchlist.actionable_count,
                "high_risk_count": watchlist.high_risk_count,
            },
            priority_board_summary={
                "total_candidates": board.total_candidates,
                "immediate_count": board.immediate_count,
                "focus_count": board.focus_count,
                "track_count": board.track_count,
            },
            top_opportunities=[
                f"{item.name} {item.symbol}: {item.buy_signal_text}，{item.summary}"
                for item in board.items[:5]
            ],
            risk_notes=self._risk_notes(watchlist, board),
            next_actions=self._next_actions(watchlist.actionable_count, board.immediate_count),
            market_overview=market,
            sector_mainline=sector,
            holding_t_signals=holding_t_signals,
            stock_top=stock_top[:10],
            risk_check=risk,
            operation_checklist=operation_checklist,
            markdown=self._markdown_report(
                market=market,
                sector=sector,
                holding_t_signals=holding_t_signals,
                stock_top=stock_top[:10],
                risk=risk,
                operation_checklist=operation_checklist,
            ),
        )

    @staticmethod
    def _risk_notes(watchlist, board) -> list[str]:
        notes: list[str] = []
        if watchlist.high_risk_count:
            notes.append(f"持仓监控中有 {watchlist.high_risk_count} 个高风险信号，先处理风险再看新机会。")
        if board.market_state_text:
            notes.append(f"当前市场状态：{board.market_state_text}。")
        if not notes:
            notes.append("当前未发现需要单独升级的系统风险。")
        return notes[:4]

    @staticmethod
    def _next_actions(actionable_count: int, immediate_count: int) -> list[str]:
        actions = ["所有结论只作为辅助解释，买点、止损和仓位仍以系统硬规则为准。"]
        if actionable_count:
            actions.append("先复核持仓做T信号，确认可卖数量和价差是否满足。")
        if immediate_count:
            actions.append("生产优先榜只看生产层和确定买入，观察层不提前买。")
        return actions

    @staticmethod
    def _holding_t_signals(watchlist) -> list[dict]:
        rows: list[dict] = []
        for item in watchlist.items:
            if item.action not in {"positive_t", "negative_t"}:
                continue
            rows.append(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "base_position": item.base_position,
                    "available_position": item.available_position,
                    "cost_basis": item.cost_basis,
                    "last_price": item.last_price,
                    "unrealized_pnl_pct": _pnl_pct(item.last_price, item.cost_basis),
                    "t_signal": item.action_text,
                    "suggestion": item.summary,
                    "risk_level": item.risk_level,
                }
            )
        return rows[:20]

    @staticmethod
    def _stock_top(board) -> list[dict]:
        rows: list[dict] = []
        for item in board.items[:20]:
            strategy_titles = item.strategy_titles or []
            suggested_position_pct = _position_pct_from_text(item.suggested_position_text)
            rows.append(
                {
                    "rank": item.rank,
                    "symbol": item.symbol,
                    "name": item.name,
                    "strategy": " / ".join(strategy_titles[:2]),
                    "score": item.priority_score,
                    "entry_zone": item.entry_zone,
                    "stop_loss": item.stop_loss,
                    "signal": item.buy_signal_text,
                    "three_way_consensus": item.buy_signal_text in {"确定买入", "立即买入", "生产买入"},
                    "suggested_position_text": item.suggested_position_text,
                    "suggested_position_pct": suggested_position_pct,
                    "sector": getattr(item, "sector_name", "") or "",
                    "summary": item.summary,
                }
            )
        return rows

    def _markdown_report(
        self,
        *,
        market: dict,
        sector: dict,
        holding_t_signals: list[dict],
        stock_top: list[dict],
        risk: dict,
        operation_checklist: list[str],
    ) -> str:
        market_state = market.get("market_state", {})
        emotion = market.get("emotion", {})
        position = market.get("risk", {}).get("recommended_position_range", {})
        lines = [
            "# TQuant 每日决策报告",
            f"## {beijing_now().strftime('%Y-%m-%d')}",
            "",
            "### 市场概览（市场状态分析师）",
            f"- 市场状态：{market_state.get('label', '上下文降级')}（置信度 {market_state.get('confidence_pct', 0)}%）",
            f"- 涨停 {emotion.get('limit_up_count', 0)} 家 | 跌停 {emotion.get('limit_down_count', 0)} 家 | 炸板率 {emotion.get('broken_board_pct', 0)}%",
            f"- 建议仓位：{position.get('min_pct', 0)}% - {position.get('max_pct', 15)}%",
            f"- 风险等级：{market.get('risk', {}).get('risk_level', 'high')}",
            "",
            "### 板块主线（板块热点分析师）",
        ]
        for item in sector.get("mainlines", [])[:5]:
            core = "、".join(stock.get("symbol", "") for stock in item.get("core_symbols", [])[:3])
            lines.append(f"- {item.get('rank')}. {item.get('sector')} | 持续性 {item.get('continuity_score')} | 核心标的 {core or '待确认'}")
        lines.extend(["", "### 持仓做T信号"])
        lines.extend(
            [
                f"- {item['symbol']} {item['name']} | {item['t_signal']} | {item['suggestion']}"
                for item in holding_t_signals[:10]
            ]
            or ["- 暂无持仓做T信号。"]
        )
        lines.extend(["", "### 选股宝典 TOP 10"])
        lines.extend(
            [
                f"- {item['rank']}. {item['symbol']} {item['strategy']} | {item['score']} | {item['signal']} | 三方一致 {item['three_way_consensus']}"
                for item in stock_top
            ]
            or ["- 暂无优先候选。"]
        )
        lines.extend(["", "### 风控检查（策略验证员）"])
        lines.append(f"- 风险等级：{risk.get('risk_level', 'clear')}，总计划仓位 {risk.get('summary', {}).get('total_position_pct', 0)}%。")
        for violation in risk.get("violations", [])[:5]:
            lines.append(f"- 超限：{violation}")
        lines.extend(["", "### 操作检查清单（组合经理）"])
        lines.extend([f"- [ ] {item}" for item in operation_checklist])
        return "\n".join(lines)


def _pnl_pct(last_price: float, cost_basis: float | None) -> float:
    if not cost_basis:
        return 0.0
    return round((float(last_price or 0) - float(cost_basis)) / float(cost_basis) * 100, 2)


def _position_pct_from_text(text: str) -> float:
    import re

    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text or "")
    return float(match.group(1)) if match else 0.0
