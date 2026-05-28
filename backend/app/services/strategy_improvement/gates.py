from __future__ import annotations

from typing import Any

from app.services.strategy_improvement.types import Gate


def build_gates(
    *,
    daily: dict[str, Any],
    minute: dict[str, Any],
    quality: dict[str, Any],
    strategies: dict[str, Any],
    constraints: dict[str, Any],
    walk_forward: dict[str, Any],
    model_shadow: dict[str, Any],
    temporal_guard: dict[str, Any],
    min_daily_coverage_pct: float,
    min_stock_symbols: int,
    min_etf_minute_coverage_pct: float,
) -> list[Gate]:
    return [
        Gate(
            "daily_24m_coverage",
            "pass" if daily["coverage_pct"] >= min_daily_coverage_pct and daily["symbol_count"] >= min_stock_symbols else "fail",
            "blocking",
            "全 A 日线覆盖率必须达到阈值后才能正式回测和参数晋级。",
            {"coverage_pct": daily["coverage_pct"], "symbol_count": daily["symbol_count"], "threshold_pct": min_daily_coverage_pct, "threshold_symbols": min_stock_symbols},
        ),
        Gate(
            "daily_quality",
            "pass" if quality["status"] == "pass" else "fail",
            "blocking",
            "OHLC、重复 K 线、负成交量/成交额必须通过质量门禁。",
            {"issues": quality["issues"]},
        ),
        Gate(
            "market_metadata_coverage",
            "pass" if quality["metadata_coverage"]["status"] == "pass" else "fail",
            "blocking",
            "涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 执行元数据必须通过门禁。",
            {
                "gap_count": quality["metadata_coverage"]["blocking_gap_count"],
                "gaps": quality["metadata_coverage"]["blocking_gaps"][:30],
            },
        ),
        Gate(
            "etf_t0_minute_coverage",
            "pass" if minute["eligible_etf_minute_coverage_pct"] >= min_etf_minute_coverage_pct else "fail",
            "blocking",
            "ETF T0 必须有分钟线覆盖率，不能用日线代理验收。",
            {
                "coverage_pct": minute["eligible_etf_minute_coverage_pct"],
                "threshold_pct": min_etf_minute_coverage_pct,
                "data_status": minute["status"],
                "raw_data_status": minute.get("raw_data_status", ""),
                "blocked_reason": minute.get("blocked_reason", ""),
                "missing": minute["missing_etf_symbols"][:20],
            },
        ),
        Gate(
            "strategy_governance_report",
            "pass" if strategies["strategy_count"] else "fail",
            "blocking",
            "必须能列出所有策略并给出治理状态。",
            {"strategy_count": strategies["strategy_count"], "state_counts": strategies["state_counts"]},
        ),
        Gate(
            "constraint_policy_coverage",
            "pass" if constraints["status"] == "pass" else "fail",
            "blocking",
            "策略必须具备弱市/板块/流动性/ST/涨跌停/连续止损/data_quality 等约束，弱策略和样本不足策略不得晋级。",
            {"status": constraints["status"], "issue_count": constraints["issue_count"], "issues": constraints["issues"][:20]},
        ),
        Gate(
            "walk_forward_readiness",
            "pass" if walk_forward["status"] == "ready" else "fail",
            "blocking",
            "Walk-forward 只允许在两年数据和候选策略足够时启动。",
            {"status": walk_forward["status"], "blocked_reasons": walk_forward["blocked_reasons"]},
        ),
        Gate(
            "temporal_no_future_function",
            "pass" if temporal_guard["status"] == "pass" else "fail",
            "blocking",
            "禁止未来函数、随机时间序列切分和 Shadow 特征混入 future/next/outcome 字段。",
            {"status": temporal_guard["status"], "issues": temporal_guard["issues"][:20]},
        ),
        Gate(
            "exit_model_shadow",
            "pass" if model_shadow["status"] == "shadow_ready" else "warn",
            "warning",
            "退出辅助模型必须先积累 Shadow 样本，不能直接进入生产动作。",
            {
                "status": model_shadow["status"],
                "record_count": model_shadow["record_count"],
                "settled_count": model_shadow["settled_count"],
                "action_diff": model_shadow.get("action_diff", {}),
                "promotion_blockers": model_shadow.get("promotion_blockers", []),
            },
        ),
    ]
