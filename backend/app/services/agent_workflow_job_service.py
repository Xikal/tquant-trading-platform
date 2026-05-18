from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timezone import beijing_now
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService
from app.services.hermes_workflow_runner import HermesWorkflowRunner, HermesWorkflowRunResult, WORKFLOW_NAME


WORKFLOW_EVENT_TYPE = "hermes_workflow"
WORKFLOW_SYMBOL = WORKFLOW_NAME
RUNNING_STATES = {"queued", "running"}
STALE_WORKFLOW_MINUTES = 45


@dataclass(frozen=True)
class WorkflowJobView:
    job_id: str
    workflow_name: str
    status: str
    message: str
    symbols: list[str]
    markdown: str = ""
    notification_sent: bool = False


class AgentWorkflowJobService:
    """Track Feishu-triggered Hermes workflow jobs using the notification ledger."""

    def __init__(
        self,
        *,
        runner: HermesWorkflowRunner | None = None,
        notification_service: AgentNotificationService | None = None,
        run_async: bool = True,
    ) -> None:
        self.runner = runner or HermesWorkflowRunner()
        self.notifications = notification_service or AgentNotificationService()
        self.run_async = run_async

    def start_daily_research(
        self,
        db: Session,
        *,
        open_id: str = "",
        symbols: list[str] | None = None,
        channel: str = "feishu",
    ) -> WorkflowJobView:
        scope_key = _scope_key(open_id)
        symbols = _normalize_symbols(symbols)
        if not self.runner.is_configured():
            return WorkflowJobView(
                job_id="",
                workflow_name=WORKFLOW_NAME,
                status="not_configured",
                message="Hermes 未配置，无法启动研究工作流。",
                symbols=symbols,
            )
        running = self._latest_running_job(db, scope_key=scope_key, channel=channel)
        if running is not None:
            payload = _payload(running)
            return WorkflowJobView(
                job_id=running.strategy_key,
                workflow_name=WORKFLOW_NAME,
                status=running.signal_state or "running",
                message="已有研究工作流正在执行，请稍后发送“研究状态”查看进度。",
                symbols=list(payload.get("symbols") or []),
                markdown=str(payload.get("markdown") or ""),
                notification_sent=bool(payload.get("notification_sent")),
            )

        job_id = f"hermes_{beijing_now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        now = beijing_now()
        event = NotificationEvent(
            scope_key=scope_key,
            channel=channel,
            event_type=WORKFLOW_EVENT_TYPE,
            symbol=WORKFLOW_SYMBOL,
            name="Hermes 每日研究工作流",
            strategy_key=job_id,
            strategy_title=WORKFLOW_NAME,
            signal_state="queued",
            signal_rank=1,
            previous_signal_state="",
            upgraded=False,
            payload_json=json.dumps(
                {
                    "job_id": job_id,
                    "workflow_name": WORKFLOW_NAME,
                    "symbols": symbols,
                    "status": "queued",
                    "message": "任务已创建。",
                    "markdown": "",
                    "notification_sent": False,
                },
                ensure_ascii=False,
            ),
            last_seen_at=now,
        )
        db.add(event)
        db.commit()
        if self.run_async:
            thread = threading.Thread(
                target=self._run_job_in_background,
                kwargs={"job_id": job_id, "channel": channel, "symbols": symbols},
                daemon=True,
                name=f"hermes-workflow-{job_id[-8:]}",
            )
            thread.start()
        else:
            self._run_job(job_id=job_id, channel=channel, symbols=symbols, db=db)
        return WorkflowJobView(
            job_id=job_id,
            workflow_name=WORKFLOW_NAME,
            status="queued" if self.run_async else self.latest_daily_research(db, open_id=open_id).status,
            message="已启动 Hermes 研究工作流。完成后会推送飞书报告；可发送“研究状态”查看进度。",
            symbols=symbols,
        )

    def latest_daily_research(self, db: Session, *, open_id: str = "", channel: str = "feishu") -> WorkflowJobView:
        row = _latest_job(db, scope_key=_scope_key(open_id), channel=channel)
        if row is None:
            return WorkflowJobView(
                job_id="",
                workflow_name=WORKFLOW_NAME,
                status="not_found",
                message="暂无 Hermes 研究工作流记录。发送“研究”可启动。",
                symbols=[],
            )
        if _expire_stale_job(db, row):
            db.refresh(row)
        payload = _payload(row)
        return WorkflowJobView(
            job_id=row.strategy_key,
            workflow_name=WORKFLOW_NAME,
            status=row.signal_state or str(payload.get("status") or ""),
            message=str(payload.get("message") or ""),
            symbols=list(payload.get("symbols") or []),
            markdown=str(payload.get("markdown") or ""),
            notification_sent=bool(payload.get("notification_sent")),
        )

    def _latest_running_job(self, db: Session, *, scope_key: str, channel: str) -> NotificationEvent | None:
        row = _latest_job(db, scope_key=scope_key, channel=channel)
        if row is None or (row.signal_state or "") not in RUNNING_STATES:
            return None
        if _expire_stale_job(db, row):
            return None
        return row

    def _run_job_in_background(self, *, job_id: str, channel: str, symbols: list[str]) -> None:
        with SessionLocal() as db:
            self._run_job(job_id=job_id, channel=channel, symbols=symbols, db=db)

    def _run_job(self, *, job_id: str, channel: str, symbols: list[str], db: Session) -> None:
        row = _job_by_id(db, job_id)
        if row is None:
            return
        _update_job(
            db,
            row,
            status="running",
            payload_update={"status": "running", "message": "Hermes 正在执行 5 个角色研究流程。"},
        )
        result = self.runner.run_daily_research(symbols=symbols)
        if result.ok:
            notification_sent = self._push_markdown(result.markdown, channel=channel)
            _update_job(
                db,
                row,
                status="succeeded",
                payload_update={
                    "status": "succeeded",
                    "message": "Hermes 研究工作流已完成。",
                    "markdown": result.markdown,
                    "result": result.data,
                    "notification_sent": notification_sent,
                },
                notification_increment=1 if notification_sent else 0,
            )
            return
        _update_job(
            db,
            row,
            status=result.status or "failed",
            payload_update={
                "status": result.status or "failed",
                "message": result.message,
                "result": result.data,
                "markdown": result.markdown,
                "notification_sent": False,
            },
        )

    def _push_markdown(self, markdown: str, *, channel: str) -> bool:
        if not markdown.strip():
            return False
        response = self.notifications.send_test(
            AgentNotificationTestRequest(channel=channel, message=markdown[:3500])
        )
        return bool(response.ok)


def _latest_job(db: Session, *, scope_key: str, channel: str) -> NotificationEvent | None:
    return (
        db.execute(
            select(NotificationEvent)
            .where(
                NotificationEvent.scope_key == scope_key,
                NotificationEvent.channel == channel,
                NotificationEvent.event_type == WORKFLOW_EVENT_TYPE,
                NotificationEvent.symbol == WORKFLOW_SYMBOL,
            )
            .order_by(NotificationEvent.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _job_by_id(db: Session, job_id: str) -> NotificationEvent | None:
    return (
        db.execute(
            select(NotificationEvent).where(
                NotificationEvent.event_type == WORKFLOW_EVENT_TYPE,
                NotificationEvent.symbol == WORKFLOW_SYMBOL,
                NotificationEvent.strategy_key == job_id,
            )
        )
        .scalars()
        .first()
    )


def _update_job(
    db: Session,
    row: NotificationEvent,
    *,
    status: str,
    payload_update: dict,
    notification_increment: int = 0,
) -> None:
    payload = _payload(row)
    payload.update(payload_update)
    row.signal_state = status
    row.signal_rank = 5 if status == "succeeded" else 3 if status == "running" else 1
    row.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    row.last_seen_at = beijing_now()
    if notification_increment:
        row.notification_count = int(row.notification_count or 0) + notification_increment
        row.last_notified_at = beijing_now()
    db.commit()


def _payload(row: NotificationEvent) -> dict:
    try:
        decoded = json.loads(row.payload_json or "{}")
        return decoded if isinstance(decoded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _expire_stale_job(db: Session, row: NotificationEvent) -> bool:
    if (row.signal_state or "") not in RUNNING_STATES or not _is_stale(row):
        return False
    _update_job(
        db,
        row,
        status="failed",
        payload_update={
            "status": "failed",
            "message": "研究工作流执行超时，已自动释放。请重新发起。",
        },
    )
    return True


def _is_stale(row: NotificationEvent) -> bool:
    last_seen = row.last_seen_at
    if last_seen is None:
        return False
    now = beijing_now()
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=now.tzinfo)
    return now - last_seen > timedelta(minutes=STALE_WORKFLOW_MINUTES)


def _scope_key(open_id: str) -> str:
    cleaned = (open_id or "").strip()
    return f"feishu:{cleaned}" if cleaned else "global"


def _normalize_symbols(symbols: list[str] | None) -> list[str]:
    output: list[str] = []
    for symbol in symbols or []:
        cleaned = "".join(ch for ch in str(symbol).strip() if ch.isalnum())
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output[:10]
