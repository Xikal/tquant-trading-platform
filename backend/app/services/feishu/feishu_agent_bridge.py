from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import UserFeishuBinding
from app.services.agent_context_service import AgentContextService
from app.services.agent_report_service import AgentReportService
from app.services.agent_workflow_job_service import AgentWorkflowJobService, WorkflowJobView
from app.services.feishu.feishu_card_builder import daily_report_card, help_card, interactive_card, signal_card, text_card


class FeishuAgentBridge:
    """Translate simple Feishu bot commands into existing Agent safe contexts."""

    def __init__(self, *, workflow_jobs: AgentWorkflowJobService | None = None) -> None:
        self.context = AgentContextService()
        self.reports = AgentReportService()
        self.workflow_jobs = workflow_jobs or AgentWorkflowJobService()

    def handle_text(self, db: Session, *, open_id: str, text: str) -> dict:
        command = _normalize_command(text)
        user_id = _resolve_user_id(db, open_id)
        if command in {"帮助", "help", ""}:
            return help_card()
        if user_id is None and command in {"持仓", "成交", "绩效", "风控"}:
            return text_card("需要绑定账户", ["当前飞书用户尚未绑定平台账号，请先在系统配置中完成绑定。"])
        if command == "持仓":
            return _paper_feature_removed_card()
        if command == "成交":
            return _paper_feature_removed_card()
        if command == "绩效":
            return _paper_feature_removed_card()
        if command == "策略":
            board = self.context.priority_board(db, limit=5)
            top_signal = board.items[0] if board.items else None
            if top_signal:
                return signal_card(
                    title="生产优先榜",
                    signal_title=f"{top_signal.rank}. {top_signal.name} {top_signal.symbol}",
                    summary=top_signal.summary or top_signal.buy_signal_text,
                    fields=[
                        ("市场状态", board.market_state_text),
                        ("信号", top_signal.buy_signal_text),
                        ("策略", "、".join(top_signal.strategy_titles[:3])),
                        ("候选数", str(board.total_candidates)),
                    ],
                )
            return interactive_card("生产优先榜", [("市场状态", board.market_state_text), ("候选数", "0")])
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
            return text_card(
                "风控摘要",
                [
                    "模拟盘功能已下线，飞书侧不再读取模拟账户。",
                    "请使用 Web 端实时行动、生产优先榜和自选监控查看当前风险状态。",
                ],
            )
        if command == "日报":
            report = self.reports.daily_report(db)
            return daily_report_card(
                headline=report.headline,
                summaries=[
                    f"自选：{report.watchlist_summary.get('total', 0)} 只，可执行 {report.watchlist_summary.get('actionable_count', 0)} 只",
                    f"优先榜：{report.priority_board_summary.get('total_candidates', 0)} 只，确定 {report.priority_board_summary.get('immediate_count', 0)} 只",
                ],
                risk_notes=report.risk_notes,
                next_actions=report.next_actions,
            )
        if _is_research_start_command(command):
            symbols = _extract_research_symbols(command)
            job = self.workflow_jobs.start_daily_research(db, open_id=open_id, symbols=symbols, channel="feishu")
            return _workflow_job_card("Hermes 研究工作流", job)
        if command in {"研究状态", "研报状态", "workflow状态", "workflow status"}:
            job = self.workflow_jobs.latest_daily_research(db, open_id=open_id, channel="feishu")
            return _workflow_job_card("Hermes 研究状态", job)
        if command in {"研究报告", "研报报告", "workflow报告", "workflow report"}:
            job = self.workflow_jobs.latest_daily_research(db, open_id=open_id, channel="feishu")
            if job.markdown:
                return text_card("Hermes 研究报告", [_compact_markdown(job.markdown)])
            return _workflow_job_card("Hermes 研究报告", job)
        return text_card("无法识别指令", ["发送“帮助”查看可用指令。"])


def _normalize_command(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("@"):
        parts = cleaned.split(maxsplit=1)
        cleaned = parts[1] if len(parts) > 1 else ""
    return cleaned.strip().lower() if cleaned.strip().lower() == "help" else cleaned.strip()


def _is_research_start_command(command: str) -> bool:
    if command in {"研究", "研报", "今日研报", "今日研究", "研究日报", "workflow", "workflow run"}:
        return True
    return command.startswith("研究 ") or command.startswith("研报 ") or command.startswith("workflow ")


def _extract_research_symbols(command: str) -> list[str]:
    for prefix in ("研究", "研报", "workflow"):
        if command == prefix:
            return []
        if command.startswith(prefix + " "):
            raw = command[len(prefix) :].strip()
            return [
                "".join(ch for ch in item.strip() if ch.isalnum())
                for item in raw.replace("，", ",").replace("、", ",").split(",")
                if "".join(ch for ch in item.strip() if ch.isalnum())
            ][:10]
    return []


def _workflow_job_card(title: str, job: WorkflowJobView) -> dict:
    fields = [
        ("工作流", job.workflow_name),
        ("状态", _workflow_status_text(job.status)),
        ("任务", job.job_id or "--"),
        ("标的", "、".join(job.symbols) if job.symbols else "生产优先榜 TOP 10"),
    ]
    if job.notification_sent:
        fields.append(("推送", "已推送飞书"))
    return interactive_card(title, fields + [("说明", job.message or "--")])


def _workflow_status_text(status: str) -> str:
    return {
        "queued": "排队中",
        "running": "执行中",
        "succeeded": "已完成",
        "failed": "失败",
        "timeout": "超时",
        "not_configured": "未配置",
        "not_found": "暂无记录",
    }.get(status or "", status or "--")


def _compact_markdown(markdown: str) -> str:
    content = (markdown or "").strip()
    if len(content) <= 1800:
        return content
    return content[:1800].rstrip() + "\n\n...报告较长，完整内容已通过飞书推送通道发送或保存在任务记录中。"


def _resolve_user_id(db: Session, open_id: str) -> int | None:
    if not open_id:
        return None
    row = (
        db.query(UserFeishuBinding)
        .filter(UserFeishuBinding.open_id == open_id, UserFeishuBinding.status == "active")
        .first()
    )
    return row.user_id if row else None


def _paper_feature_removed_card() -> dict:
    return text_card("模拟盘已下线", ["当前入口不再提供模拟盘账户、成交和绩效数据。"])
