from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, PaperTrade, UserFeishuBinding
from app.services.agent_context_service import AgentContextService
from app.services.agent_report_service import AgentReportService
from app.services.feishu.feishu_card_builder import help_card, interactive_card, text_card


class FeishuAgentBridge:
    """Translate simple Feishu bot commands into existing Agent safe contexts."""

    def __init__(self) -> None:
        self.context = AgentContextService()
        self.reports = AgentReportService()

    def handle_text(self, db: Session, *, open_id: str, text: str) -> dict:
        command = _normalize_command(text)
        user_id = _resolve_user_id(db, open_id)
        if command in {"帮助", "help", ""}:
            return help_card()
        if user_id is None and command in {"持仓", "成交", "绩效", "风控"}:
            return text_card("需要绑定账户", ["当前飞书用户尚未绑定平台账号，请先在系统配置中完成绑定。"])
        if command == "持仓":
            portfolio = self.context.paper_portfolio(db, user_id=user_id)
            fields = [
                ("总资产", f"{portfolio.total_assets:.2f}"),
                ("可用资金", f"{portfolio.cash_available:.2f}"),
                ("持仓数", str(len(portfolio.positions))),
            ]
            fields.extend((item.symbol, f"{item.name or item.symbol} · {item.quantity}股") for item in portfolio.positions[:5])
            return interactive_card("模拟盘持仓", fields)
        if command == "成交":
            return _latest_trade_card(db, user_id)
        if command == "绩效":
            portfolio = self.context.paper_portfolio(db, user_id=user_id)
            return interactive_card(
                "模拟盘绩效",
                [
                    ("总收益率", f"{portfolio.total_return_pct:.2f}%"),
                    ("胜率", f"{portfolio.win_rate_pct:.2f}%"),
                    ("净胜率", f"{portfolio.net_win_rate_pct:.2f}%"),
                ],
            )
        if command == "策略":
            board = self.context.priority_board(db, limit=5)
            fields = [
                ("市场状态", board.market_state_text),
                ("候选数", str(board.total_candidates)),
            ]
            fields.extend((f"{item.rank}. {item.symbol}", f"{item.name} · {item.buy_signal_text}") for item in board.items[:5])
            return interactive_card("全策略优先榜", fields)
        if command == "自选":
            watchlist = self.context.watchlist_context(db)
            return text_card(
                "自选监控",
                [
                    f"自选数：{watchlist.total}",
                    f"可执行：{watchlist.actionable_count}",
                    f"高风险：{watchlist.high_risk_count}",
                ],
            )
        if command == "风控":
            portfolio = self.context.paper_portfolio(db, user_id=user_id)
            return text_card(
                "风控摘要",
                [
                    f"持仓市值：{portfolio.market_value:.2f}",
                    f"收益因子：{portfolio.profit_factor if portfolio.profit_factor is not None else '--'}",
                    "详细熔断状态请在 Web 模拟盘查看。",
                ],
            )
        if command == "日报":
            report = self.reports.daily_report(db)
            return text_card(report.headline, report.next_actions[:5] or report.risk_notes[:5])
        return text_card("无法识别指令", ["发送“帮助”查看可用指令。"])


def _normalize_command(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("@"):
        parts = cleaned.split(maxsplit=1)
        cleaned = parts[1] if len(parts) > 1 else ""
    return cleaned.strip().lower() if cleaned.strip().lower() == "help" else cleaned.strip()


def _resolve_user_id(db: Session, open_id: str) -> int | None:
    if not open_id:
        return None
    row = (
        db.query(UserFeishuBinding)
        .filter(UserFeishuBinding.open_id == open_id, UserFeishuBinding.status == "active")
        .first()
    )
    return row.user_id if row else None


def _latest_trade_card(db: Session, user_id: int | None) -> dict:
    account = (
        db.execute(select(PaperAccount).where(PaperAccount.user_id == user_id).order_by(PaperAccount.id.asc()))
        .scalars()
        .first()
    )
    if account is None:
        return text_card("模拟成交", ["暂无模拟账户。"])
    rows = (
        db.execute(
            select(PaperTrade)
            .where(PaperTrade.account_id == account.id)
            .order_by(PaperTrade.trade_time.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )
    if not rows:
        return text_card("模拟成交", ["暂无成交记录。"])
    lines = [
        f"{row.symbol} {'买入' if row.side == 'buy' else '卖出'} {row.quantity}股 @ {float(row.price or 0):.3f}"
        for row in rows
    ]
    return text_card("最近模拟成交", lines)
