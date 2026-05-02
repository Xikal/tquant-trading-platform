from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.schema_defs.agent import AgentDailyReportResponse
from app.services.agent_context_service import AgentContextService


class AgentReportService:
    def __init__(self) -> None:
        self.context = AgentContextService()

    def daily_report(self, db: Session) -> AgentDailyReportResponse:
        watchlist = self.context.watchlist_context(db)
        board = self.context.priority_board(db, limit=12)
        headline = (
            f"今日可执行信号 {watchlist.actionable_count} 个，"
            f"全策略优先候选 {board.immediate_count} 个。"
        )
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
            actions.append("全策略榜只看生产层和确定买入，观察层不提前买。")
        return actions
