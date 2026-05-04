from __future__ import annotations

from typing import Any


def _plain_text(content: str) -> dict[str, str]:
    return {"tag": "plain_text", "content": content}


def _markdown(content: str) -> dict[str, str]:
    return {"tag": "lark_md", "content": content}


def text_card(title: str, lines: list[str]) -> dict[str, Any]:
    content = "\n".join(line for line in lines if line)
    return {
        "msg_type": "text",
        "content": {"text": f"{title}\n{content}" if content else title},
    }


def help_card() -> dict[str, Any]:
    return text_card(
        "维斯量化平台指令",
        [
            "持仓：查看模拟盘持仓摘要",
            "成交：查看最近模拟成交",
            "绩效：查看最近绩效摘要",
            "策略：查看全策略优先榜摘要",
            "风控：查看模拟盘风险状态",
            "自选：查看自选监控摘要",
            "帮助：查看可用指令",
        ],
    )


def interactive_card(title: str, fields: list[tuple[str, str]], actions: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Build a compact Feishu interactive card without coupling callers to card JSON."""

    elements: list[dict[str, Any]] = []
    if fields:
        elements.append(
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": _markdown(f"**{label}**\n{value}"),
                    }
                    for label, value in fields
                ],
            }
        )
    if actions:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": _plain_text(label),
                        "type": "default",
                        "url": url,
                    }
                    for label, url in actions
                ],
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": _plain_text(title)},
            "elements": elements,
        },
    }


def signal_card(
    *,
    title: str,
    signal_title: str,
    summary: str,
    fields: list[tuple[str, str]],
    actions: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a Feishu card for one actionable signal."""

    elements: list[dict[str, Any]] = [
        {"tag": "div", "text": _markdown(f"**{signal_title}**\n{summary}")},
    ]
    if fields:
        elements.append(_field_block(fields))
    if actions:
        elements.append(_action_block(actions))
    return _interactive_payload(title=title, elements=elements, template="blue")


def daily_report_card(
    *,
    headline: str,
    summaries: list[str],
    risk_notes: list[str],
    next_actions: list[str],
) -> dict[str, Any]:
    """Build a structured daily-report card that can be reused by bot and schedulers."""

    elements: list[dict[str, Any]] = [{"tag": "div", "text": _markdown(headline)}]
    for section_title, lines in (
        ("今日摘要", summaries),
        ("风险提醒", risk_notes),
        ("下一步", next_actions),
    ):
        if lines:
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": _markdown(f"**{section_title}**\n" + "\n".join(f"- {line}" for line in lines[:6]))})
    return _interactive_payload(title="维斯量化日报", elements=elements, template="wathet")


def risk_alert_card(
    *,
    title: str,
    level: str,
    summary: str,
    fields: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a compact risk alert card with explicit severity."""

    template = "red" if level in {"high", "danger", "critical"} else "orange"
    elements: list[dict[str, Any]] = [{"tag": "div", "text": _markdown(summary)}]
    if fields:
        elements.append(_field_block(fields))
    return _interactive_payload(title=title, elements=elements, template=template)


def _field_block(fields: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "tag": "div",
        "fields": [
            {"is_short": True, "text": _markdown(f"**{label}**\n{value}")}
            for label, value in fields
        ],
    }


def _action_block(actions: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": _plain_text(label),
                "type": "default",
                "url": url,
            }
            for label, url in actions
        ],
    }


def _interactive_payload(*, title: str, elements: list[dict[str, Any]], template: str) -> dict[str, Any]:
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"template": template, "title": _plain_text(title)},
            "elements": elements,
        },
    }
