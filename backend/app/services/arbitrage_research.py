from __future__ import annotations

from typing import Any

from app.core.timezone import beijing_now


def build_multi_exchange_arbitrage_research(symbols: list[str] | None = None) -> dict[str, Any]:
    """Return a safe research envelope for arbitrage ideas.

    TQuant is scoped to A-share decision support. Cross-exchange arbitrage needs
    real venues, borrow/settlement rules, FX, latency and compliance checks.
    This endpoint deliberately does not create orders; it exposes the boundary
    so UI/Agent callers do not mistake data-provider price differences for a
    tradable arbitrage signal.
    """

    clean_symbols = [item.strip() for item in symbols or [] if item.strip()]
    return {
        "generated_at": beijing_now().isoformat(timespec="seconds"),
        "mode": "research_only",
        "production_enabled": False,
        "tradable": False,
        "symbols": clean_symbols,
        "opportunities": [],
        "required_before_production": [
            "接入真实多市场订单簿和成交回报，而不是行情 Provider 差价。",
            "明确可交易标的、融券/申赎/跨境结算、汇率和交易费用。",
            "完成延迟、滑点、撤单失败和资金占用压力测试。",
            "通过合规审批后才能进入任何自动交易链路。",
        ],
        "summary": "当前仅支持套利研究边界诊断，不把跨 Provider 报价差异当成可交易套利。",
    }
