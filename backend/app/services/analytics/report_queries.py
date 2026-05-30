from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services.analytics.config import PROJECT_ROOT, analytics_config
from app.services.analytics.duckdb_repository import DuckDBRepository
from app.services.low_buy.strategy_policy import (
    StrategyTier,
    get_strategy_tier,
    is_low_sample_capped_strategy,
    participates_in_priority_board,
)


DEFAULT_STRATEGY_REPORT = PROJECT_ROOT / "docs" / "reports" / "strategy-24m-backtest-2026-05-30.json"
FOCUS_WALK_FORWARD_REPORT = PROJECT_ROOT / "docs" / "reports" / "focus-strategy-walk-forward-plan-2026-05-28" / "summary.json"
PARAMETER_WALK_FORWARD_REPORT = (
    PROJECT_ROOT / "docs" / "reports" / "focus-strategy-parameter-walk-forward-2026-05-28" / "summary.json"
)


def build_strategy_24m_duckdb_report(
    manifest: dict[str, Any],
    *,
    output_root: str | Path | None = None,
    legacy_strategy_report: str | Path | None = None,
    focus_walk_forward_report: str | Path | None = None,
    parameter_walk_forward_report: str | Path | None = None,
) -> dict[str, Any]:
    config = analytics_config(output_root)
    quality = dict(manifest.get("quality") or {})
    files = list(manifest.get("files") or [])
    parquet_glob = str(config.parquet_dir / "daily_bars" / "**" / "*.parquet")
    data_blocked = quality.get("status") != "ok"
    duckdb_summary: dict[str, Any] = {}
    monthly_market: list[dict[str, Any]] = []
    if files:
        repo = DuckDBRepository(output_root=config.root)
        try:
            duckdb_summary = repo.query_one(
                f"""
                SELECT
                    count(*) AS row_count,
                    count(DISTINCT symbol) AS symbol_count,
                    count(DISTINCT trade_date) AS trade_day_count,
                    min(trade_date) AS min_trade_date,
                    max(trade_date) AS max_trade_date,
                    avg(pct_chg) AS avg_pct_chg,
                    sum(amount) AS total_amount
                FROM read_parquet('{parquet_glob}')
                """
            )
            monthly_market = repo.query_all(
                f"""
                SELECT
                    strftime(CAST(trade_date AS DATE), '%Y-%m') AS month,
                    count(*) AS row_count,
                    count(DISTINCT symbol) AS symbol_count,
                    count(DISTINCT trade_date) AS trade_day_count,
                    round(avg(pct_chg), 4) AS avg_pct_chg,
                    round(sum(amount), 2) AS total_amount
                FROM read_parquet('{parquet_glob}')
                GROUP BY 1
                ORDER BY 1
                """
            )
        finally:
            repo.close()
    strategy_source = Path(legacy_strategy_report or DEFAULT_STRATEGY_REPORT)
    legacy = _load_json(strategy_source)
    walk_forward = _walk_forward_evidence(
        focus_walk_forward_report or FOCUS_WALK_FORWARD_REPORT,
        parameter_walk_forward_report or PARAMETER_WALK_FORWARD_REPORT,
    )
    strategies = [_strategy_summary(dict(item), legacy, walk_forward) for item in legacy.get("all_strategies") or []]
    recommendations = [_strategy_recommendation(item) for item in strategies]
    missing = _critical_input_gaps(strategies)
    status = "ok"
    if data_blocked:
        status = "blocked_by_data"
    elif missing:
        status = "blocked_by_validation_inputs"
    return _json_safe(
        {
            "title": "DuckDB 24个月策略分析报告",
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "status": status,
            "manifest": {
                "dataset_version": manifest.get("dataset_version"),
                "manifest_path": manifest.get("manifest_path"),
                "period_start": manifest.get("period_start"),
                "period_end": manifest.get("period_end"),
                "row_count": manifest.get("row_count"),
                "symbol_count": manifest.get("symbol_count"),
                "quality": quality,
            },
            "data_quality_conclusion": _quality_conclusion(quality),
            "duckdb_daily_bar_summary": duckdb_summary,
            "duckdb_monthly_market_summary": monthly_market,
            "strategy_summary_source": str(strategy_source),
            "strategy_summary_note": _strategy_summary_note(data_blocked, bool(missing)),
            "validation_input_gaps": missing,
            "execution_assumptions": _execution_assumptions(),
            "sensitivity_notes": _sensitivity_notes(),
            "all_strategies": strategies,
            "strategy_adjustment_recommendations": recommendations,
        }
    )


def render_strategy_24m_markdown(report: dict[str, Any]) -> str:
    quality = report.get("manifest", {}).get("quality", {})
    lines = [
        "# DuckDB 24个月策略分析报告",
        "",
        f"- 生成时间：{report.get('generated_at', '')}",
        f"- 状态：{report.get('status', '')}",
        f"- Manifest：{report.get('manifest', {}).get('dataset_version', '')}",
        f"- 数据窗口：{report.get('manifest', {}).get('period_start', '')} 至 {report.get('manifest', {}).get('period_end', '')}",
        f"- 数据完整性：{quality.get('status', '')}",
        f"- 结论：{report.get('data_quality_conclusion', '')}",
        "",
        "## DuckDB 日线扫描摘要",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
    ]
    summary = report.get("duckdb_daily_bar_summary") or {}
    for key in ("row_count", "symbol_count", "trade_day_count", "min_trade_date", "max_trade_date", "avg_pct_chg", "total_amount"):
        lines.append(f"| {key} | {summary.get(key, '')} |")
    lines.extend(["", "## 24M 报告口径", "", report.get("strategy_summary_note", ""), ""])
    strategies = report.get("all_strategies") or []
    if strategies:
        lines.extend(
            [
                "| 策略 | 层级 | 样本 | 成交 | 每日信号等权复利收益 | 真实组合 max5 | 真实组合 max10 | 最大回撤 | PF | 平均单笔 | 季度稳定性 | walk-forward | OOS | 建议 |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|",
            ]
        )
        recommendations = {item["strategy_key"]: item for item in report.get("strategy_adjustment_recommendations") or []}
        for item in strategies:
            rec = recommendations.get(item.get("strategy_key", ""), {})
            lines.append(
                "| {title} | {tier} | {sample} | {filled} | {ret} | {max5} | {max10} | {dd} | {pf} | {avg} | {quarter} | {wf} | {oos} | {action} |".format(
                    title=item.get("strategy_title") or item.get("strategy_key") or "",
                    tier=item.get("policy_tier", ""),
                    sample=int(item.get("sample_count") or 0),
                    filled=int(item.get("filled_count") or 0),
                    ret=_fmt_pct(item.get("daily_signal_equal_weight_compound_return_pct")),
                    max5=_fmt_pct(_portfolio_metric(item, "max_5", "portfolio_return_pct")),
                    max10=_fmt_pct(_portfolio_metric(item, "max_10", "portfolio_return_pct")),
                    dd=_fmt_pct(item.get("max_drawdown_pct")),
                    pf=_fmt_num(item.get("profit_factor"), 2),
                    avg=_fmt_pct(item.get("avg_trade_return_pct"), digits=3),
                    quarter=_quarter_text(item.get("quarter_stability") or {}),
                    wf=_walk_forward_text(item.get("walk_forward") or {}),
                    oos=_oos_text(item.get("oos") or {}),
                    action=rec.get("recommended_action", ""),
                )
            )
    else:
        lines.append("未找到可用策略摘要。")
    gaps = report.get("validation_input_gaps") or []
    lines.extend(["", "## 关键输入门禁", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap.get('strategy_key')}：{gap.get('field')} 缺失，{gap.get('impact')}")
    else:
        lines.append("- 生产准入所需真实组合、walk-forward 和 OOS 字段齐备。")
    lines.extend(["", "## Batch B 决策上下文", ""])
    lines.extend(
        [
            "- 板块/龙头确认：只作为生产分外侧加权，CORE 最高 +12，AUX 最高 +6；RESEARCH 策略不获得生产先验。",
            "- 真实组合执行：Paper 组合预览与本报告 max5/max10 复用同一个 portfolio_backtest_metrics 口径。",
            "- 策略晋级：只产出 promotion review 建议，can_apply_override=false，不自动修改 strategy_policy.py 或 StrategyTierOverride。",
            "- 数据质量：关键输入缺失时必须返回 blocked_by_data 或 blocked_by_validation_inputs，不用空分或假分继续验收。",
        ]
    )
    lines.extend(["", "## 策略调整建议", ""])
    for item in report.get("strategy_adjustment_recommendations") or []:
        evidence = item.get("evidence") or {}
        lines.append(
            "- {title}：{action_text}。样本 {sample}，成交 {filled}，PF {pf}，平均单笔 {avg}，最大回撤 {dd}，max5 {max5}，max10 {max10}，季度 {quarter}，walk-forward {wf}，OOS {oos}。依据：{reason}".format(
                title=item.get("strategy_title") or item.get("strategy_key"),
                action_text=item.get("recommended_action_text"),
                sample=evidence.get("sample_count", 0),
                filled=evidence.get("filled_count", 0),
                pf=_fmt_num(evidence.get("profit_factor"), 2),
                avg=_fmt_pct(evidence.get("avg_trade_return_pct"), digits=3),
                dd=_fmt_pct(evidence.get("max_drawdown_pct")),
                max5=_fmt_pct(evidence.get("max5_portfolio_return_pct")),
                max10=_fmt_pct(evidence.get("max10_portfolio_return_pct")),
                quarter=_quarter_text(evidence.get("quarter_stability") or {}),
                wf=_walk_forward_text(evidence.get("walk_forward") or {}),
                oos=_oos_text(evidence.get("oos") or {}),
                reason=item.get("reason"),
            )
        )
    lines.extend(["", "## 执行与成本假设", ""])
    for item in report.get("execution_assumptions") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 敏感性与可信度", ""])
    for item in report.get("sensitivity_notes") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_strategy_24m_report(report: dict[str, Any], *, output_md: str | Path, output_json: str | Path) -> None:
    md_path = Path(output_md)
    json_path = Path(output_json)
    safe_report = _json_safe(report)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_strategy_24m_markdown(safe_report), encoding="utf-8")
    json_path.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _strategy_summary(item: dict[str, Any], source: dict[str, Any], walk_forward: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = str(item.get("strategy_key") or "")
    metrics = item.get("all_signal_metrics") if int(item.get("filled_count") or 0) <= 0 else item
    if isinstance(metrics, dict):
        for field in (
            "daily_signal_equal_weight_compound_return_pct",
            "daily_signal_equal_weight_annualized_return_pct",
            "max_drawdown_pct",
            "profit_factor",
            "avg_trade_return_pct",
        ):
            item[field] = metrics.get(field, item.get(field))
        item["portfolio_backtests"] = item.get("portfolio_backtests") or metrics.get("portfolio_backtests")
    item["policy_tier"] = get_strategy_tier(key).value
    item["priority_board_eligible"] = participates_in_priority_board(key)
    item["low_sample_capped"] = is_low_sample_capped_strategy(key)
    item["quarter_stability"] = _quarter_stability(item)
    item["walk_forward"] = walk_forward.get(key) or _missing_validation("not_available", "未找到真实 walk-forward 证据")
    item["oos"] = _oos_summary(item, source)
    return item


def _walk_forward_evidence(focus_path: str | Path, parameter_path: str | Path) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    focus = _load_json(focus_path)
    for item in focus.get("strategies") or []:
        key = str(item.get("strategy_key") or "")
        if not key:
            continue
        windows = item.get("windows") or []
        current_windows = [dict(window.get("current") or {}) for window in windows if isinstance(window, dict)]
        avg_pf = _avg([window.get("profit_factor") for window in current_windows])
        avg_dd = _avg([window.get("max_drawdown_pct") for window in current_windows])
        avg_return = _avg([window.get("total_return_pct") for window in current_windows])
        evidence[key] = {
            "status": "complete",
            "source": str(focus_path),
            "window_count": int(item.get("window_count") or len(windows)),
            "passed_window_count": int(item.get("passed_window_count") or 0),
            "pass_rate_pct": float(item.get("pass_rate_pct") or 0.0),
            "avg_profit_factor": avg_pf,
            "avg_total_return_pct": avg_return,
            "avg_max_drawdown_pct": avg_dd,
            "production_eligible": bool(item.get("production_eligible")),
            "note": str(item.get("execution_priority") or "walk-forward current exit evidence"),
        }
    parameter = _load_json(parameter_path)
    for item in parameter.get("strategies") or []:
        key = str(item.get("scope_key") or "")
        if not key:
            continue
        current = evidence.get(key, {})
        current.update(
            {
                "status": "complete",
                "source": str(parameter_path),
                "window_count": int(item.get("window_count") or current.get("window_count") or 0),
                "passed_window_count": int(item.get("passed_window_count") or current.get("passed_window_count") or 0),
                "pass_rate_pct": float(item.get("pass_rate_pct") or current.get("pass_rate_pct") or 0.0),
                "production_eligible": bool(item.get("production_eligible")),
                "shadow_candidate": bool(item.get("shadow_candidate")),
                "note": "parameter walk-forward complete; production write still blocked by shadow gate",
            }
        )
        evidence[key] = current
    return evidence


def _quarter_stability(item: dict[str, Any]) -> dict[str, Any]:
    quarters = [dict(row) for row in item.get("quarter_breakdown") or [] if int(row.get("filled_count") or 0) > 0]
    positive = [row for row in quarters if float(row.get("daily_signal_equal_weight_compound_return_pct") or row.get("total_return_pct") or 0) > 0]
    pf_pass = [row for row in quarters if float(row.get("profit_factor") or 0) >= 1.0]
    count = len(quarters)
    return {
        "status": "complete" if count else "missing",
        "quarter_count": count,
        "positive_quarter_count": len(positive),
        "pf_pass_quarter_count": len(pf_pass),
        "positive_rate_pct": round(len(positive) / count * 100, 2) if count else None,
        "pf_pass_rate_pct": round(len(pf_pass) / count * 100, 2) if count else None,
    }


def _oos_summary(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    split = source.get("strategy_family_summary", {}).get("time_series_splits") or {}
    roles = split.get("roles") or {}
    quarters = set(split.get("out_of_sample_quarters") or [])
    rows = [dict(row) for row in item.get("quarter_breakdown") or [] if row.get("key") in quarters]
    if not rows:
        return _missing_validation("missing", "未找到 OOS 季度明细")
    return {
        "status": "quarter_proxy" if split.get("evidence_level") else "complete",
        "evidence_level": split.get("evidence_level", ""),
        "quarters": sorted(quarters),
        "sample_count": sum(int(row.get("sample_count") or 0) for row in rows),
        "filled_count": sum(int(row.get("filled_count") or 0) for row in rows),
        "profit_factor": _weighted_avg(rows, "profit_factor", "filled_count"),
        "daily_signal_equal_weight_compound_return_pct": sum(float(row.get("daily_signal_equal_weight_compound_return_pct") or 0.0) for row in rows),
        "max_drawdown_pct": min((float(row.get("max_drawdown_pct") or 0.0) for row in rows), default=None),
        "global_role": roles.get("out_of_sample") or {},
    }


def _strategy_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    key = str(item.get("strategy_key") or "")
    filled = int(item.get("filled_count") or item.get("all_signal_filled_count") or 0)
    sample = int(item.get("sample_count") or item.get("all_signal_sample_count") or 0)
    pf = float(item.get("profit_factor") or 0.0)
    avg = float(item.get("avg_trade_return_pct") or 0.0)
    max_dd = float(item.get("max_drawdown_pct") or 0.0)
    max5 = _portfolio_metric(item, "max_5", "portfolio_return_pct")
    max10 = _portfolio_metric(item, "max_10", "portfolio_return_pct")
    quarter = item.get("quarter_stability") or {}
    walk_forward = item.get("walk_forward") or {}
    oos = item.get("oos") or {}
    tier = get_strategy_tier(key)
    reason_parts: list[str] = []
    if key == "n_pattern_short_wash" or pf < 0.9 or avg < -0.1:
        action, text = "delete_candidate", "删除候选"
        reason_parts.append("PF 低于 0.9 或平均单笔为明显负值")
    elif tier == StrategyTier.AUXILIARY and is_low_sample_capped_strategy(key):
        action, text = "low_sample_capped", "辅助低样本限权"
        reason_parts.append("辅助生产层但必须低样本限权")
    elif filled < 100:
        action, text = "default_off", "默认关闭"
        reason_parts.append("成交样本不足 100")
    elif pf < 1.05 or avg <= 0 or max_dd <= -50:
        action, text = "default_off", "默认关闭"
        reason_parts.append("收益质量弱或回撤过大")
    elif tier == StrategyTier.CORE and _validation_ready_for_admission(item):
        action, text = "core_admit", "核心生产保留"
        reason_parts.append("核心层指标、组合回测和验证输入齐备")
    elif tier == StrategyTier.CORE:
        action, text = "default_off", "默认关闭"
        reason_parts.append("核心层缺少生产准入验证输入")
    else:
        action, text = "default_off", "默认关闭"
        reason_parts.append("研究层不进入生产排序")
    return {
        "strategy_key": key,
        "strategy_title": item.get("strategy_title", ""),
        "recommended_action": action,
        "recommended_action_text": text,
        "reason": "；".join(reason_parts),
        "evidence": {
            "sample_count": sample,
            "filled_count": filled,
            "profit_factor": pf,
            "avg_trade_return_pct": avg,
            "max_drawdown_pct": max_dd,
            "max5_portfolio_return_pct": max5,
            "max10_portfolio_return_pct": max10,
            "quarter_stability": quarter,
            "walk_forward": walk_forward,
            "oos": oos,
        },
    }


def _critical_input_gaps(strategies: list[dict[str, Any]]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for item in strategies:
        key = str(item.get("strategy_key") or "")
        if not participates_in_priority_board(key):
            continue
        for label, value in (
            ("portfolio_backtests.max_5.portfolio_return_pct", _portfolio_metric(item, "max_5", "portfolio_return_pct")),
            ("portfolio_backtests.max_10.portfolio_return_pct", _portfolio_metric(item, "max_10", "portfolio_return_pct")),
        ):
            if value is None:
                gaps.append({"strategy_key": key, "field": label, "impact": "真实组合回测缺失，生产准入失败"})
        if (item.get("walk_forward") or {}).get("status") != "complete":
            gaps.append({"strategy_key": key, "field": "walk_forward", "impact": "缺少真实 walk-forward，生产准入失败"})
        if (item.get("oos") or {}).get("status") not in {"complete", "quarter_proxy"}:
            gaps.append({"strategy_key": key, "field": "oos", "impact": "缺少样本外验证，生产准入失败"})
    return gaps


def _validation_ready_for_admission(item: dict[str, Any]) -> bool:
    return (
        _portfolio_metric(item, "max_5", "portfolio_return_pct") is not None
        and _portfolio_metric(item, "max_10", "portfolio_return_pct") is not None
        and (item.get("walk_forward") or {}).get("status") == "complete"
        and (item.get("oos") or {}).get("status") in {"complete", "quarter_proxy"}
    )


def _portfolio_metric(item: dict[str, Any], portfolio: str, field: str) -> float | None:
    value = (((item.get("portfolio_backtests") or {}).get(portfolio) or {}).get(field))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _missing_validation(status: str, note: str) -> dict[str, Any]:
    return {"status": status, "note": note}


def _quality_conclusion(quality: dict[str, Any]) -> str:
    if quality.get("status") == "ok":
        return "24个月日线数据完整性通过，可以基于该 Manifest 继续报告。"
    task_id = quality.get("backfill_task_id")
    suffix = f"，已创建 data_backfill_24m 任务 #{task_id}" if task_id else "，需要先创建并完成 data_backfill_24m 任务"
    blockers = "、".join(quality.get("blockers") or ["数据覆盖不足"])
    return f"数据完整性未通过：{blockers}{suffix}；本次不得作为完整24个月回测验收。"


def _strategy_summary_note(data_blocked: bool, validation_blocked: bool) -> str:
    if data_blocked:
        return "当前 Manifest 未通过完整性门禁，策略回测摘要仅保留历史 Python 24个月报告作参考，不作为本次 DuckDB 完整验收。"
    note = "策略收益口径统一为“每日信号等权复利收益”，同时列出真实组合回测 max5/max10，避免把逐信号无资金约束收益误称为收益。"
    if validation_blocked:
        note += " 生产准入如缺 walk-forward/OOS/组合回测字段会显式阻断。"
    return note


def _execution_assumptions() -> list[str]:
    return [
        "费用与滑点：基础双边成本按报告输入的 16 bps 读取，max5/max10 组合字段保留 total_cost_bps_assumption。",
        "冲击成本：当前报告未接入逐笔盘口冲击成本，敏感性必须在后续组合回测中用 extra_cost_bps 单独复跑。",
        "涨跌停：买入成交依赖信号后可成交价格，涨跌停无法成交应计入未成交或跳过原因。",
        "停牌/缺价：组合回测若出现 missing_dates 必须显式统计，关键输入缺失时报告阻断。",
        "T+1：同日买入不允许同日卖出，退出按后续交易日规则执行。",
        "同票不重复买：真实组合 max5/max10 启用 same_symbol_reentry_blocked，持仓未释放前不重复开同票。",
    ]


def _sensitivity_notes() -> list[str]:
    return [
        "建议对费用/滑点追加 0、10、20、50 bps 梯度复跑，观察 PF、平均单笔和 max5/max10 收益弹性。",
        "建议对 max_positions=5/10、strategy_daily_limit、weak_market_position_cap 分别复跑，避免单一容量假设掩盖拥挤风险。",
        "季度稳定性、walk-forward、OOS 必须同时展示；任一关键输入缺失，生产建议不得升为 core_admit。",
    ]


def _fmt_pct(value: Any, *, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "缺失"


def _fmt_num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "缺失"


def _quarter_text(value: dict[str, Any]) -> str:
    if value.get("status") != "complete":
        return "缺失"
    return f"{value.get('positive_quarter_count', 0)}/{value.get('quarter_count', 0)} 正收益；PF>=1 {value.get('pf_pass_quarter_count', 0)}/{value.get('quarter_count', 0)}"


def _walk_forward_text(value: dict[str, Any]) -> str:
    if value.get("status") != "complete":
        return f"缺失({value.get('note', '')})"
    return f"{value.get('passed_window_count', 0)}/{value.get('window_count', 0)} 窗口，pass {float(value.get('pass_rate_pct') or 0.0):.1f}%"


def _oos_text(value: dict[str, Any]) -> str:
    status = value.get("status")
    if status not in {"complete", "quarter_proxy"}:
        return f"缺失({value.get('note', '')})"
    return f"{status}，成交 {value.get('filled_count', 0)}，PF {_fmt_num(value.get('profit_factor'), 2)}，收益 {_fmt_pct(value.get('daily_signal_equal_weight_compound_return_pct'))}"


def _avg(values: list[Any]) -> float | None:
    nums = [float(value) for value in values if value is not None]
    return round(sum(nums) / len(nums), 4) if nums else None


def _weighted_avg(rows: list[dict[str, Any]], field: str, weight_field: str) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        weight = float(row.get(weight_field) or 0.0)
        try:
            value = float(row.get(field))
        except (TypeError, ValueError):
            continue
        numerator += value * weight
        denominator += weight
    return round(numerator / denominator, 4) if denominator else None
