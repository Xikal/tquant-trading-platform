from __future__ import annotations

import argparse
from typing import Any

from app.services.strategy_improvement.types import Gate


def data_backfill_plan(*, args: argparse.Namespace, daily: dict[str, Any], minute: dict[str, Any]) -> dict[str, Any]:
    commands = []
    if daily["status"] != "complete":
        commands.append(
            "DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db "
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/daily_history_backfill_runner.py "
            f"--scope all-stock --start-date {args.start} --end-date {daily.get('requested_end') or args.end} "
            "--batch-size 50 --workers 4 --resume"
        )
    if minute["status"] != "complete":
        commands.append(
            "DATABASE_URL=sqlite:////Users/j/Documents/gupiao/backend/data/t_quant.db "
            "PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backfill_etf_minute_history.py "
            f"--scope t0-etf --start-date {args.start} --end-date {daily.get('requested_end') or args.end} "
            "--period 5m --workers 2 --allow-partial"
        )
        commands.append(
            "ETF 1m 免费接口通常只返回近 5 个交易日；24 个月 ETF T0 验收应优先补 5m 历史分钟线，"
            "或接入正式分钟数据源后再启用 1m 验收。"
        )
    return {
        "status": "needed" if commands else "not_needed",
        "priority_sources": ["project_configured_provider_or_tushare", "akshare", "eastmoney_sina_tencent_exchange_public"],
        "required_fields": [
            "source",
            "fetch_time",
            "trade_date",
            "symbol",
            "adjusted_mode",
            "checksum_or_version",
            "data_quality",
            "limit_up_down",
            "suspend_st_delist_listing_date",
            "industry_concept_history",
            "etf_t0_capability_liquidity_premium_discount",
        ],
        "commands_or_tasks": commands,
        "blocked_policy": "补齐失败时标记 blocked_by_data/partial_data，并列出缺失 symbol/date/字段/原因；禁止硬填价格。",
    }


def next_actions(*, gates: list[Gate], walk_forward: dict[str, Any], model_shadow: dict[str, Any]) -> list[str]:
    actions = []
    failed = {gate.key for gate in gates if gate.status == "fail"}
    if "daily_24m_coverage" in failed:
        actions.append("先补齐全 A 最近 24 个月日线、复权、涨跌停、停牌/ST/退市/上市日期与行业历史字段，再重跑基线。")
    if "market_metadata_coverage" in failed:
        actions.append("补齐并持久化涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 折溢价/流动性/盘口价差元数据；OHLCV 通过不等于可验收。")
    if "etf_t0_minute_coverage" in failed:
        actions.append("补齐 ETF 白名单分钟线、费用/滑点/溢折价/流动性/T+0 字段；分钟线不足时 ETF T0 继续 blocked_by_data。")
    if "walk_forward_readiness" in failed:
        actions.append("数据门禁通过后，对正期望候选和高回撤策略执行 12m/3m/3m monthly rolling Walk-forward。")
    if model_shadow["status"] != "shadow_ready":
        actions.append("继续积累退出模型 Shadow 样本；只记录规则动作和模型建议差异，不改变订单和账本。")
    actions.append("将治理结果接入回测页/策略工作台/模拟盘展示，但保持生产参数只读。")
    return actions


def invariants() -> list[str]:
    return [
        "T 日信号只能使用 T 日及以前可得数据；T+1 交易不能使用 T+1 收盘后数据。",
        "分钟策略只能使用当前分钟及以前数据；市场情绪、板块强度、龙头强度必须使用当时快照。",
        "Python 保持策略、风控、回测语义和模拟盘账本真源；Go/Rust 不输出买卖决策。",
        "所有新增策略、参数、模型、约束必须可关闭、可回滚、可观测。",
        "回测与治理脚本只读，不修改生产参数、订单、成交、持仓或账本。",
    ]
