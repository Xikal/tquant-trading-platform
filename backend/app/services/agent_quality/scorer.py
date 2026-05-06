from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import AgentResultQuality
from app.models.schema_defs.phase4 import (
    AgentQualityIssueOut,
    AgentQualityScoreRequest,
    AgentQualityScoreResponse,
)


_DEFAULT_REQUIRED_FIELDS = ("final_action", "confidence", "reasons", "risks")
_ACTION_FIELDS = ("action", "final_action", "recommendation")


@dataclass(frozen=True)
class AgentQualityScorer:
    """Deterministic guardrail for Agent/Hermes outputs.

    This does not judge whether a market opinion is profitable. It checks that
    structured answers are complete, auditable, and do not bypass risk control.
    """

    min_score: float | None = None

    def score(
        self,
        payload: AgentQualityScoreRequest,
        *,
        db: Session | None = None,
        persist: bool = True,
    ) -> AgentQualityScoreResponse:
        output = payload.output_payload or {}
        required = tuple(payload.required_fields or _DEFAULT_REQUIRED_FIELDS)
        issues: list[AgentQualityIssueOut] = []
        issues.extend(_missing_required_fields(output, required))
        issues.extend(_quality_warnings(payload.input_payload or {}, output))
        score = _score_from_issues(issues)
        threshold = self.min_score if self.min_score is not None else float(get_settings().agent_quality_min_score)
        passed = score >= threshold and not any(issue.severity == "error" for issue in issues)
        blocked = not passed
        response = AgentQualityScoreResponse(
            trace_id=payload.trace_id,
            provider=payload.provider,
            agent_id=payload.agent_id,
            score=score,
            passed=passed,
            blocked=blocked,
            issues=issues,
            summary=_summary(score, passed, issues),
        )
        if db is not None and persist:
            _persist_quality(db, payload, response)
        return response


def score_agent_result(
    payload: AgentQualityScoreRequest,
    *,
    db: Session | None = None,
    persist: bool = True,
) -> AgentQualityScoreResponse:
    return AgentQualityScorer().score(payload, db=db, persist=persist)


def _missing_required_fields(output: dict[str, Any], required: tuple[str, ...]) -> list[AgentQualityIssueOut]:
    issues: list[AgentQualityIssueOut] = []
    for field in required:
        value = output.get(field)
        if value in (None, "", [], {}):
            issues.append(
                AgentQualityIssueOut(
                    code="missing_required_field",
                    severity="error",
                    message=f"缺少必填字段: {field}",
                )
            )
    return issues


def _quality_warnings(input_payload: dict[str, Any], output: dict[str, Any]) -> list[AgentQualityIssueOut]:
    issues: list[AgentQualityIssueOut] = []
    data_quality = output.get("data_quality")
    if isinstance(data_quality, dict) and data_quality.get("is_stale"):
        issues.append(AgentQualityIssueOut(code="stale_data", severity="warning", message="输出使用了过期数据。"))
    if not output.get("risks") and not output.get("risk") and not output.get("risk_notes"):
        issues.append(AgentQualityIssueOut(code="missing_risk_notes", severity="warning", message="缺少风险提示。"))
    if not output.get("reasons") and not output.get("reason"):
        issues.append(AgentQualityIssueOut(code="missing_reasons", severity="warning", message="缺少决策理由。"))
    if _has_executable_action(output) and _is_blocked_by_risk(input_payload, output):
        issues.append(
            AgentQualityIssueOut(
                code="action_conflicts_with_risk",
                severity="error",
                message="输出存在可执行动作，但风控上下文已阻断。",
            )
        )
    confidence = _to_float(output.get("confidence"))
    if confidence is not None and (confidence < 0 or confidence > 1):
        issues.append(AgentQualityIssueOut(code="invalid_confidence", severity="error", message="confidence 必须在 0 到 1 之间。"))
    if "source" not in output and "sources" not in output and "agent_votes" not in output:
        issues.append(AgentQualityIssueOut(code="missing_source_trace", severity="warning", message="缺少来源或 Agent 投票记录。"))
    return issues


def _score_from_issues(issues: list[AgentQualityIssueOut]) -> float:
    score = 1.0
    for issue in issues:
        score -= 0.35 if issue.severity == "error" else 0.12 if issue.severity == "warning" else 0.04
    return round(max(score, 0.0), 3)


def _summary(score: float, passed: bool, issues: list[AgentQualityIssueOut]) -> str:
    if passed:
        return f"Agent 输出质量通过，评分 {score:.2f}。"
    severe = [issue.message for issue in issues if issue.severity == "error"]
    if severe:
        return f"Agent 输出被拦截，评分 {score:.2f}；{severe[0]}"
    return f"Agent 输出低置信，评分 {score:.2f}。"


def _has_executable_action(output: dict[str, Any]) -> bool:
    executable = {"buy", "sell", "positive_t", "negative_t", "execute", "confirm_buy"}
    for field in _ACTION_FIELDS:
        value = str(output.get(field) or "").lower()
        if value in executable:
            return True
    return False


def _is_blocked_by_risk(input_payload: dict[str, Any], output: dict[str, Any]) -> bool:
    if output.get("blocked") is True:
        return True
    risk = input_payload.get("risk_control") or input_payload.get("risk") or {}
    return isinstance(risk, dict) and risk.get("blocked") is True


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _persist_quality(db: Session, payload: AgentQualityScoreRequest, response: AgentQualityScoreResponse) -> None:
    row = AgentResultQuality(
        trace_id=payload.trace_id,
        provider=payload.provider,
        agent_id=payload.agent_id,
        score=response.score,
        passed=response.passed,
        issue_count=len(response.issues),
        issues_json=_json_dumps([issue.model_dump() for issue in response.issues]),
        input_summary=_json_dumps(_compact(payload.input_payload)),
        output_summary=_json_dumps(_compact(payload.output_payload)),
    )
    db.add(row)
    db.commit()


def _compact(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in sorted(value.keys())[:20]}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
