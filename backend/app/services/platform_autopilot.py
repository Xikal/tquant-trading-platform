from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import beijing_now, beijing_now_string
from app.models.entities import BacktestOptimization, BacktestValidation, RuntimeTask
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.models.schema_defs.agent_platform import (
    AgentPlatformAutopilotAction,
    AgentPlatformAutopilotIssue,
    AgentPlatformAutopilotResponse,
)
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_workflow_job_service import AgentWorkflowJobService
from app.services.latest_data_close_refresh import enqueue_latest_data_close_refresh
from app.services.latest_data_status import latest_data_status
from app.services.market_quote_cache_refresh import quote_cache_refresh_bucket, quote_cache_refresh_due
from app.services.operation_audit import record_operation_audit
from app.services.tasks import RuntimeTaskQueue


logger = logging.getLogger(__name__)
RESEARCH_STUCK_MINUTES = 10
RUNTIME_BACKLOG_WARNING = 20


class PlatformAutopilotService:
    """Controlled platform monitor and low-risk self-healing runbook.

    This service intentionally does not execute shell commands, deployments,
    schema changes, strategy promotion, or trading-state resets.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def run(
        self,
        *,
        auto_repair: bool = True,
        notify: bool = True,
        audit: bool = True,
        trigger: str = "scheduled",
    ) -> AgentPlatformAutopilotResponse:
        issues: list[AgentPlatformAutopilotIssue] = []
        actions: list[AgentPlatformAutopilotAction] = []
        self._check_latest_data(auto_repair=auto_repair, issues=issues, actions=actions)
        self._check_runtime_tasks(auto_repair=auto_repair, issues=issues, actions=actions)
        self._check_backtest_research_queue(issues=issues, actions=actions)
        self._check_hermes_workflow(issues=issues, actions=actions)
        self._check_quote_cache(auto_repair=auto_repair, actions=actions)
        self._check_notification_channel(issues=issues)

        status = _overall_status(issues)
        response = AgentPlatformAutopilotResponse(
            ok=status != "failed",
            status=status,
            updated_at=beijing_now_string(),
            trigger=trigger,
            auto_repair=auto_repair,
            issues=issues,
            actions=actions,
            summary=_summary(status, issues, actions),
        )
        if audit:
            self._audit(response)
        if notify and (issues or any(action.status in {"queued", "executed", "failed"} for action in actions)):
            self._notify(response)
        return response

    def _check_latest_data(
        self,
        *,
        auto_repair: bool,
        issues: list[AgentPlatformAutopilotIssue],
        actions: list[AgentPlatformAutopilotAction],
    ) -> None:
        try:
            status = latest_data_status(self.db)
        except Exception as exc:
            self.db.rollback()
            issues.append(_issue("latest_data_check_failed", "error", "最新数据状态检查失败", {"error": str(exc)}))
            return
        if status.get("status") == "success":
            return
        issues.append(
            _issue(
                "latest_data_pending",
                "warning",
                "最新交易日数据尚未完整发布",
                {
                    "expected_trade_date": status.get("expected_trade_date"),
                    "daily_bar_count": status.get("daily_bar_count"),
                    "missing_strategies": status.get("missing_strategies") or [],
                },
            )
        )
        if not auto_repair:
            actions.append(_action("latest_data_refresh", "skipped", "未启用自动修复，跳过最新数据补全。"))
            return
        try:
            result = enqueue_latest_data_close_refresh(self.db)
            actions.append(
                _action(
                    "latest_data_refresh",
                    "queued" if result.get("task_id") else "executed",
                    "已触发最新数据补全检查。",
                    task_id=result.get("task_id"),
                    detail=result,
                )
            )
        except Exception as exc:
            logger.exception("platform autopilot latest data repair failed")
            actions.append(_action("latest_data_refresh", "failed", "最新数据补全触发失败。", detail={"error": str(exc)}))

    def _check_runtime_tasks(
        self,
        *,
        auto_repair: bool,
        issues: list[AgentPlatformAutopilotIssue],
        actions: list[AgentPlatformAutopilotAction],
    ) -> None:
        try:
            queue = RuntimeTaskQueue(self.db)
            if auto_repair:
                queue.recover_stale_running_tasks()
            queued = _runtime_count(self.db, "queued")
            running = _runtime_count(self.db, "running")
            failed_since = datetime.utcnow() - timedelta(hours=max(get_settings().platform_autopilot_failed_task_window_hours, 1))
            failed = _runtime_count(self.db, "failed", since=failed_since)
        except Exception as exc:
            self.db.rollback()
            issues.append(_issue("runtime_queue_check_failed", "error", "后台任务队列检查失败", {"error": str(exc)}))
            return
        if queued >= RUNTIME_BACKLOG_WARNING:
            issues.append(_issue("runtime_queue_backlog", "warning", "后台任务队列积压较多", {"queued": queued}))
        if failed:
            issues.append(_issue("runtime_tasks_failed", "warning", "存在失败的后台任务", {"failed": failed}))
            actions.append(
                _action(
                    "runtime_queue_check",
                    "executed",
                    "已检查后台任务队列。",
                    detail={"queued": queued, "running": running, "failed_recent": failed},
                )
            )

    def _check_backtest_research_queue(
        self,
        *,
        issues: list[AgentPlatformAutopilotIssue],
        actions: list[AgentPlatformAutopilotAction],
    ) -> None:
        try:
            stale_cutoff = datetime.utcnow() - timedelta(minutes=RESEARCH_STUCK_MINUTES)
            opt_count = _research_stuck_count(self.db, BacktestOptimization, stale_cutoff)
            val_count = _research_stuck_count(self.db, BacktestValidation, stale_cutoff)
        except Exception as exc:
            self.db.rollback()
            issues.append(
                _issue("backtest_research_queue_check_failed", "error", "回测研究队列检查失败", {"error": str(exc)})
            )
            return
        if opt_count or val_count:
            issues.append(
                _issue(
                    "backtest_research_queue_stuck",
                    "warning",
                    "参数优化或样本外验证任务长时间未被消费",
                    {"optimizations": opt_count, "validations": val_count},
                )
            )
        actions.append(
            _action(
                "backtest_research_queue_check",
                "executed",
                "已检查参数优化/样本外验证队列。",
                detail={"stuck_optimizations": opt_count, "stuck_validations": val_count},
            )
        )

    def _check_hermes_workflow(
        self,
        *,
        issues: list[AgentPlatformAutopilotIssue],
        actions: list[AgentPlatformAutopilotAction],
    ) -> None:
        try:
            job = AgentWorkflowJobService().latest_daily_research(self.db)
        except Exception as exc:
            self.db.rollback()
            issues.append(_issue("hermes_workflow_check_failed", "warning", "Hermes 工作流状态检查失败", {"error": str(exc)}))
            return
        if job.status == "failed" and "超时" in job.message:
            issues.append(_issue("hermes_workflow_stale_released", "warning", "Hermes 研究工作流超时任务已释放"))
            actions.append(_action("hermes_workflow_release", "executed", job.message))

    def _check_quote_cache(self, *, auto_repair: bool, actions: list[AgentPlatformAutopilotAction]) -> None:
        if not quote_cache_refresh_due():
            return
        if not auto_repair:
            actions.append(_action("quote_cache_refresh", "skipped", "交易时段行情缓存刷新未自动触发。"))
            return
        try:
            task = RuntimeTaskQueue(self.db).enqueue(
                RuntimeTaskCreate(
                    task_type="market_quote_cache_refresh",
                    payload={"limit": 200, "reason": "platform_autopilot"},
                    priority=25,
                    idempotency_key=f"market_quote_cache_refresh:{quote_cache_refresh_bucket()}",
                    max_attempts=2,
                )
            )
            actions.append(_action("quote_cache_refresh", "queued", "已触发交易时段行情缓存刷新。", task_id=task.id))
        except Exception as exc:
            self.db.rollback()
            actions.append(_action("quote_cache_refresh", "failed", "行情缓存刷新触发失败。", detail={"error": str(exc)}))

    def _check_notification_channel(self, *, issues: list[AgentPlatformAutopilotIssue]) -> None:
        if not AgentNotificationService().supports_channel("feishu"):
            issues.append(_issue("notification_not_configured", "warning", "飞书/Hermes 通知通道未配置"))

    def _audit(self, response: AgentPlatformAutopilotResponse) -> None:
        try:
            record_operation_audit(
                self.db,
                operation="platform_autopilot_run",
                resource_type="agent",
                resource_id="platform_autopilot",
                status=response.status,
                detail=response.model_dump(mode="json"),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.warning("platform autopilot audit write failed", exc_info=True)

    def _notify(self, response: AgentPlatformAutopilotResponse) -> None:
        message = _notification_message(response)
        result = AgentNotificationService().send_test(AgentNotificationTestRequest(channel="feishu", message=message))
        if not result.ok:
            logger.warning("platform autopilot notification failed: %s", result.message)


def _runtime_count(db: Session, status: str, *, since: datetime | None = None) -> int:
    statement = select(func.count(RuntimeTask.id)).where(RuntimeTask.status == status)
    if since is not None:
        statement = statement.where(
            or_(
                and_(RuntimeTask.finished_at.is_not(None), RuntimeTask.finished_at >= since),
                and_(RuntimeTask.finished_at.is_(None), RuntimeTask.updated_at >= since),
            )
        )
    return int(db.execute(statement).scalar() or 0)


def _research_stuck_count(db: Session, model: Any, cutoff: datetime) -> int:
    return int(
        db.execute(
            select(func.count(model.id))
            .where(model.status.in_(("queued", "running")))
            .where(model.deleted_at.is_(None))
            .where(
                or_(
                    and_(model.status == "queued", model.created_at <= cutoff),
                    and_(
                        model.status == "running",
                        or_(
                            and_(model.started_at.is_not(None), model.started_at <= cutoff),
                            and_(model.started_at.is_(None), model.updated_at <= cutoff),
                        ),
                    ),
                )
            )
        ).scalar()
        or 0
    )


def _issue(code: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> AgentPlatformAutopilotIssue:
    return AgentPlatformAutopilotIssue(code=code, severity=severity, message=message, detail=detail or {})


def _action(
    action_key: str,
    status: str,
    message: str,
    *,
    task_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> AgentPlatformAutopilotAction:
    return AgentPlatformAutopilotAction(
        action_key=action_key,
        status=status,
        message=message,
        task_id=task_id,
        detail=detail or {},
    )


def _overall_status(issues: list[AgentPlatformAutopilotIssue]) -> str:
    if any(issue.severity == "error" for issue in issues):
        return "failed"
    if any(issue.severity == "warning" for issue in issues):
        return "degraded"
    return "ok"


def _summary(status: str, issues: list[AgentPlatformAutopilotIssue], actions: list[AgentPlatformAutopilotAction]) -> str:
    if status == "ok":
        return f"平台巡检正常，执行 {len(actions)} 个检查/动作。"
    return f"平台巡检发现 {len(issues)} 个问题，执行 {len(actions)} 个检查/动作。"


def _notification_message(response: AgentPlatformAutopilotResponse) -> str:
    lines = [f"【TQuant 自动巡检】{response.status}", response.summary]
    for issue in response.issues[:6]:
        lines.append(f"- {issue.severity}: {issue.message}")
    for action in response.actions[:6]:
        if action.status in {"queued", "executed", "failed"}:
            lines.append(f"- 动作 {action.action_key}: {action.status} {action.message}")
    return "\n".join(lines)
