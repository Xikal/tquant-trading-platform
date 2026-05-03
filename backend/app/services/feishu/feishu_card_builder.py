from __future__ import annotations

from typing import Any


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
                        "text": {"tag": "lark_md", "content": f"**{label}**\n{value}"},
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
                        "text": {"tag": "plain_text", "content": label},
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
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": elements,
        },
    }
