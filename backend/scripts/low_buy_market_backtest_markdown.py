from __future__ import annotations


def render_markdown_report(report: dict) -> str:
    summary = report["summary"]
    coverage = summary.get("data_coverage", {})
    coverage_warning = str(coverage.get("warning") or "")
    lines = [
        f"# {report['title']}",
        "",
        "## 结论",
        "",
        f"- 总体判断：{summary['conclusion']}",
        f"- A 股股票数：{summary['universe_count']}",
        f"- 目标回测区间：{summary['evaluation_start']} 至 {summary['evaluation_end']}，共 {summary['evaluation_trade_days']} 个评估交易日",
        f"- 数据覆盖：请求 {coverage.get('requested_months', summary.get('backtest_window_months', 0))} 个月，实际约 {coverage.get('actual_months_estimate', 0.0)} 个月，覆盖率 {coverage.get('coverage_pct', 0.0)}%，状态 {coverage.get('status', 'unknown')}",
        *( [f"- 数据覆盖警告：{coverage_warning}"] if coverage_warning else [] ),
        f"- 实际快照区间：{summary['snapshot_start']} 至 {summary['snapshot_end']}，共 {summary['snapshot_trade_days']} 个有数据交易日",
        f"- 快照模式：{_materialization_mode_text(summary.get('materialization_mode', ''))}",
        f"- 执行模型：{summary.get('execution_model', 'candidate_exit_plan')}",
        f"- 市场保护研究模型：{summary.get('market_guard', 'none')}",
        f"- 预筛参数研究覆盖：{summary.get('prefilter_overrides', 'none')}",
        f"- 实际读取/计算快照：{summary['completed_snapshot_count']} / {summary['expected_snapshot_count']}，覆盖率 {summary['completed_snapshot_coverage_pct']}%",
        f"- 回放失败快照：{summary['failed_snapshot_count']}",
        f"- 本次评估信号状态：{', '.join(summary.get('selected_signal_states', [])) or '未指定'}",
        f"- 扫描样本：{summary['scanned_count']}，候选命中：{summary['matched_count']}，确定买入：{summary['confirmed_count']}，观察确认：{summary.get('observe_confirmed_count', 0)}，接近买点：{summary['near_entry_count']}",
        f"- 市场保护触发：{summary.get('market_guard_count', 0)}，分布：{_render_counts(summary.get('market_guard_counts', {}))}",
        f"- 状态过滤跳过：{summary.get('skipped_by_state_count', 0)}，分布：{_render_counts(summary.get('skipped_by_state_counts', {}))}",
        f"- 未成交原因：{_render_counts(summary.get('not_filled_reason_counts', {}))}",
        f"- 退出原因：{_render_counts(summary.get('filled_exit_reason_counts', {}))}",
        f"- 已完成评估：{summary['evaluated_count']}，待完成：{summary['pending_count']}，样本质量：{summary['sample_quality']}",
        f"- 确定买入真实执行：成交 {summary['filled_count']}，净胜率 {summary['net_win_rate']}%，均净收益 {summary['avg_net_return_pct']}%，未成交率 {summary['not_filled_rate']}%，止损率 {summary['stop_loss_rate']}%",
        _render_performance_summary("生产信号执行绩效（buy_now/soft_buy_now）", summary.get("backtest_metrics", {})),
        _render_performance_summary("全观察信号诊断绩效", summary.get("all_evaluated_backtest_metrics", {})),
        f"- 次日事件验证：T+1 冲高3%命中 {summary['t1_high_3_hit_rate']}%，冲高5%命中 {summary['t1_high_5_hit_rate']}%，冲高回落到买点率 {summary['t1_fade_to_entry_rate']}%，T+1最高均收 {summary['avg_t1_high_return_pct']}%，T+1收盘均收 {summary['avg_t1_close_return_pct']}%，T+2收盘均收 {summary['avg_t2_close_return_pct']}%",
        _render_signal_group_summary("确定买入", summary["confirmed_result"]),
        _render_signal_group_summary("立即买入 buy_now", summary.get("buy_now_result", {})),
        _render_signal_group_summary("轻仓买入 soft_buy_now", summary.get("soft_buy_now_result", {})),
        _render_signal_group_summary("观察确认", summary.get("observe_confirmed_result", {})),
        _render_signal_group_summary("接近买点", summary["near_entry_result"]),
        "",
        "## 口径",
        "",
    ]
    lines.extend(f"- {item}" for item in report["methodology"])
    lines.extend(
        [
            "",
            "## 策略族汇总",
            "",
            "| 策略族 | 策略数 | 类型 | 已评估 | 成交 | 净胜率 | 均净收 | 未成交 | 止损 | 冲高命中 | 1日胜率 | 2日胜率 | 3日胜率 | 4日胜率 | 5日胜率 | 最佳持有 | 结论 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for item in report.get("families", []):
        lines.append(_render_family_group_row(item, "确定买入", item["confirmed_result"]))
        lines.append(_render_family_group_row(item, "立即买入 buy_now", item.get("buy_now_result", {})))
        lines.append(_render_family_group_row(item, "轻仓买入 soft_buy_now", item.get("soft_buy_now_result", {})))
        lines.append(_render_family_group_row(item, "观察确认", item.get("observe_confirmed_result", {})))
        lines.append(_render_family_group_row(item, "接近买点", item["near_entry_result"]))
    lines.extend(
        [
            "",
            "## 策略执行绩效",
            "",
            "| 策略 | 成交 | 每日信号等权复利收益 | 年化 | 真实组合max5 | 真实组合max10 | 最大回撤 | 均笔净收益 | 日均信号收益 | 诊断复利 | Sharpe | 胜率 | PF | 平均持仓 | 回撤恢复 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in report["strategies"]:
        lines.append(_render_strategy_performance_row(item))
    lines.extend(
        [
            "",
            "## 策略诊断",
            "",
            "| 策略 | 评估状态 | 信号分布 | 市场保护 | 状态过滤跳过 | 未成交原因 | 退出原因 | 待评估原因 |",
            "|---|---|---|---|---:|---|---|---|",
        ]
    )
    for item in report["strategies"]:
        lines.append(_render_strategy_diagnostics_row(item))
    lines.extend(
        [
            "",
            "## 策略明细",
            "",
            "| 策略族 | 策略 | 类型 | 快照 | 已评估 | 成交 | 净胜率 | 均净收 | 未成交 | 止损 | 冲高命中 | 1日胜率 | 1日均收 | 2日胜率 | 2日均收 | 3日胜率 | 3日均收 | 4日胜率 | 4日均收 | 5日胜率 | 5日均收 | 最佳持有 | 最大冲高 | 最大回撤 | 结论 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
        ]
    )
    for item in report["strategies"]:
        lines.append(_render_strategy_group_row(item, "确定买入", item["confirmed_result"]))
        lines.append(_render_strategy_group_row(item, "立即买入 buy_now", item.get("buy_now_result", {})))
        lines.append(_render_strategy_group_row(item, "轻仓买入 soft_buy_now", item.get("soft_buy_now_result", {})))
        lines.append(_render_strategy_group_row(item, "观察确认", item.get("observe_confirmed_result", {})))
        lines.append(_render_strategy_group_row(item, "接近买点", item["near_entry_result"]))
    return "\n".join(lines) + "\n"


def _materialization_mode_text(mode: str) -> str:
    labels = {
        "isolated": "隔离计算，不写入线上物化结果表",
        "production": "写入线上物化结果表，仅用于明确需要回灌缓存的任务",
        "read-only": "只读取已有物化结果，不补算缺失日期",
    }
    return labels.get(mode, mode)


def _render_signal_group_summary(label: str, item: dict) -> str:
    item = _safe_result(item)
    best = item.get("best_holding_day") or {}
    best_text = (
        f"最佳持有 {best.get('day', 0)} 日，均收 {best.get('avg_return', 0.0)}%，胜率 {best.get('win_rate', 0.0)}%"
        if int(best.get("day", 0) or 0) > 0
        else "最佳持有天数：样本不足"
    )
    return (
        f"- {label}：已评估 {item['evaluated_count']}，成交 {item['filled_count']}，净胜率 {item['net_win_rate']}%，均净收益 {item['avg_net_return_pct']}%，未成交率 {item['not_filled_rate']}%；"
        f"T+1冲高3%命中 {item['t1_high_3_hit_rate']}%，T+1冲高5%命中 {item['t1_high_5_hit_rate']}%，T+1冲高回落到买点 {item['t1_fade_to_entry_rate']}%；"
        f"5日冲高3%命中 {item['hit_rate']}%；"
        f"冲高兑现均收 1日 {item['avg_spike_return_1d']}% / 2日 {item['avg_spike_return_2d']}% / 3日 {item['avg_spike_return_3d']}% / 4日 {item['avg_spike_return_4d']}% / 5日 {item['avg_spike_return_5d']}%；"
        f"胜率 1日 {item['win_rate_1d']}% / 2日 {item['win_rate_2d']}% / 3日 {item['win_rate_3d']}% / 4日 {item['win_rate_4d']}% / 5日 {item['win_rate_5d']}%；"
        f"平均收益 1日 {item['avg_return_1d']}% / 2日 {item['avg_return_2d']}% / 3日 {item['avg_return_3d']}% / 4日 {item['avg_return_4d']}% / 5日 {item['avg_return_5d']}%；{best_text}。"
    )


def _render_performance_summary(label: str, metrics: dict) -> str:
    metrics = _safe_performance(metrics)
    return (
        f"- {label}：成交 {metrics['trade_count']}，每日信号等权复利收益 {metrics['daily_signal_equal_weight_compound_return_pct']}%，年化 {metrics['daily_signal_equal_weight_annualized_return_pct']}%，"
        f"真实组合max5收益 {metrics['portfolio_max_5_return_pct']}%，真实组合max10收益 {metrics['portfolio_max_10_return_pct']}%，"
        f"最大回撤 {metrics['max_drawdown_pct']}%，Sharpe {metrics['sharpe_ratio']}，胜率 {metrics['win_rate_pct']}%，"
        f"均笔净收益 {metrics['avg_net_return_pct']}%，日均信号收益 {metrics['avg_daily_signal_return_pct']}%，"
        f"盈亏比 {metrics['profit_loss_ratio']}，PF {metrics['profit_factor']}，平均持仓 {metrics['avg_holding_days']} 天；"
        f"{metrics['drawdown_recovery_status']}。原逐信号复利诊断值 {metrics['diagnostic_compound_return_pct']}%，不作为真实资金收益。"
    )


def _render_strategy_performance_row(strategy: dict) -> str:
    metrics = _safe_performance(strategy.get("backtest_metrics", {}))
    return (
        "| {title} | {trades} | {total}% | {annualized}% | {portfolio5}% | {portfolio10}% | {drawdown}% | {avg_net}% | {avg_daily}% | {diag}% | {sharpe} | {win}% | {pf} | {holding} | {recovery} |"
    ).format(
        title=strategy["strategy_title"],
        trades=metrics["trade_count"],
        total=metrics["daily_signal_equal_weight_compound_return_pct"],
        annualized=metrics["daily_signal_equal_weight_annualized_return_pct"],
        portfolio5=metrics["portfolio_max_5_return_pct"],
        portfolio10=metrics["portfolio_max_10_return_pct"],
        drawdown=metrics["max_drawdown_pct"],
        avg_net=metrics["avg_net_return_pct"],
        avg_daily=metrics["avg_daily_signal_return_pct"],
        diag=metrics["diagnostic_compound_return_pct"],
        sharpe=metrics["sharpe_ratio"],
        win=metrics["win_rate_pct"],
        pf=metrics["profit_factor"],
        holding=metrics["avg_holding_days"],
        recovery=metrics["drawdown_recovery_status"],
    )


def _render_strategy_diagnostics_row(strategy: dict) -> str:
    diagnostics = strategy.get("evaluation_diagnostics", {}) or {}
    return "| {title} | {states} | {state_counts} | {guard} | {skipped} | {not_filled} | {exits} | {pending} |".format(
        title=strategy["strategy_title"],
        states=", ".join(diagnostics.get("selected_signal_states", []) or []),
        state_counts=_render_counts(strategy.get("signal_state_counts", {})),
        guard=_render_counts(diagnostics.get("market_guard_counts", {})),
        skipped=diagnostics.get("skipped_by_state_count", 0),
        not_filled=_render_counts(diagnostics.get("not_filled_reason_counts", {})),
        exits=_render_counts(diagnostics.get("filled_exit_reason_counts", {})),
        pending=_render_counts(diagnostics.get("pending_reason_counts", {})),
    )


def _render_counts(values: dict | None, *, limit: int = 4) -> str:
    rows = list((values or {}).items())
    if not rows:
        return "-"
    head = [f"{key}: {value}" for key, value in rows[:limit]]
    if len(rows) > limit:
        head.append(f"其余 {len(rows) - limit} 项")
    return "；".join(head)


def _render_strategy_group_row(
    strategy: dict,
    label: str,
    result: dict,
) -> str:
    result = _safe_result(result)
    return (
        "| {family} | {title} | {label} | {snapshots} | {evaluated} | {filled} | {net_win}% | {net_avg}% | {not_filled}% | {stop_loss}% | {hit}% | "
        "{win1}% | {avg1}% | {win2}% | {avg2}% | {win3}% | {avg3}% | "
        "{win4}% | {avg4}% | {win5}% | {avg5}% | {best} | {gain}% | {dd}% | {conclusion} |"
    ).format(
        family=strategy["strategy_family_text"],
        title=strategy["strategy_title"],
        label=label,
        snapshots=strategy["snapshot_count"],
        evaluated=result["evaluated_count"],
        filled=result["filled_count"],
        net_win=result["net_win_rate"],
        net_avg=result["avg_net_return_pct"],
        not_filled=result["not_filled_rate"],
        stop_loss=result["stop_loss_rate"],
        hit=result["hit_rate"],
        win1=result["win_rate_1d"],
        avg1=result["avg_return_1d"],
        win2=result["win_rate_2d"],
        avg2=result["avg_return_2d"],
        win3=result["win_rate_3d"],
        avg3=result["avg_return_3d"],
        win4=result["win_rate_4d"],
        avg4=result["avg_return_4d"],
        win5=result["win_rate_5d"],
        avg5=result["avg_return_5d"],
        best=_best_holding_text(result),
        gain=result["avg_max_gain_5d"],
        dd=result["avg_max_drawdown_5d"],
        conclusion=strategy["conclusion"] if label in {"确定买入", "立即买入 buy_now", "轻仓买入 soft_buy_now"} else "观察信号，只用于判断提前量。",
    )


def _render_family_group_row(
    family: dict,
    label: str,
    result: dict,
) -> str:
    result = _safe_result(result)
    conclusion = family["conclusion"] if label in {"确定买入", "立即买入 buy_now", "轻仓买入 soft_buy_now"} else "观察信号，只用于判断提前量。"
    return (
        "| {family} | {strategy_count} | {label} | {evaluated} | {filled} | {net_win}% | {net_avg}% | {not_filled}% | {stop_loss}% | {hit}% | "
        "{win1}% | {win2}% | {win3}% | {win4}% | {win5}% | {best} | {conclusion} |"
    ).format(
        family=family["strategy_family_text"],
        strategy_count=family["strategy_count"],
        label=label,
        evaluated=result["evaluated_count"],
        filled=result["filled_count"],
        net_win=result["net_win_rate"],
        net_avg=result["avg_net_return_pct"],
        not_filled=result["not_filled_rate"],
        stop_loss=result["stop_loss_rate"],
        hit=result["hit_rate"],
        win1=result["win_rate_1d"],
        win2=result["win_rate_2d"],
        win3=result["win_rate_3d"],
        win4=result["win_rate_4d"],
        win5=result["win_rate_5d"],
        best=_best_holding_text(result),
        conclusion=conclusion,
    )


def _best_holding_text(result: dict) -> str:
    best = result.get("best_holding_day") or {}
    day = int(best.get("day", 0) or 0)
    if day <= 0:
        return "样本不足"
    return f"{day}日 / {best.get('avg_return', 0.0)}%"


def _safe_result(item: dict | None) -> dict:
    defaults = {
        "evaluated_count": 0,
        "filled_count": 0,
        "net_win_rate": 0.0,
        "avg_net_return_pct": 0.0,
        "not_filled_rate": 0.0,
        "stop_loss_rate": 0.0,
        "t1_high_3_hit_rate": 0.0,
        "t1_high_5_hit_rate": 0.0,
        "t1_fade_to_entry_rate": 0.0,
        "avg_t1_high_return_pct": 0.0,
        "avg_t1_close_return_pct": 0.0,
        "avg_t1_spike_fade_pct": 0.0,
        "avg_t2_high_return_pct": 0.0,
        "avg_t2_close_return_pct": 0.0,
        "hit_rate": 0.0,
        "win_rate_1d": 0.0,
        "win_rate_2d": 0.0,
        "win_rate_3d": 0.0,
        "win_rate_4d": 0.0,
        "win_rate_5d": 0.0,
        "avg_return_1d": 0.0,
        "avg_return_2d": 0.0,
        "avg_return_3d": 0.0,
        "avg_return_4d": 0.0,
        "avg_return_5d": 0.0,
        "avg_spike_return_1d": 0.0,
        "avg_spike_return_2d": 0.0,
        "avg_spike_return_3d": 0.0,
        "avg_spike_return_4d": 0.0,
        "avg_spike_return_5d": 0.0,
        "spike_win_rate_1d": 0.0,
        "spike_win_rate_2d": 0.0,
        "spike_win_rate_3d": 0.0,
        "spike_win_rate_4d": 0.0,
        "spike_win_rate_5d": 0.0,
        "avg_max_gain_5d": 0.0,
        "avg_max_drawdown_5d": 0.0,
        "best_holding_day": {"day": 0, "avg_return": 0.0, "win_rate": 0.0},
    }
    return {**defaults, **(item or {})}


def _safe_performance(item: dict | None) -> dict:
    raw = item or {}
    defaults = {
        "trade_count": 0,
        "total_return_pct": 0.0,
        "daily_signal_equal_weight_compound_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "daily_signal_equal_weight_annualized_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "drawdown_recovery_status": "无成交",
        "sharpe_ratio": 0.0,
        "win_rate_pct": 0.0,
        "profit_loss_ratio": 0.0,
        "profit_factor": 0.0,
        "avg_holding_days": 0.0,
        "avg_net_return_pct": 0.0,
        "avg_daily_signal_return_pct": 0.0,
        "diagnostic_compound_return_pct": 0.0,
        "portfolio_backtests": {},
    }
    merged = {**defaults, **raw}
    if "daily_signal_equal_weight_compound_return_pct" not in raw:
        merged["daily_signal_equal_weight_compound_return_pct"] = merged.get("total_return_pct", 0.0)
    if "daily_signal_equal_weight_annualized_return_pct" not in raw:
        merged["daily_signal_equal_weight_annualized_return_pct"] = merged.get("annualized_return_pct", 0.0)
    portfolios = merged.get("portfolio_backtests") or {}
    merged["portfolio_max_5_return_pct"] = float((portfolios.get("max_5") or {}).get("portfolio_return_pct") or 0.0)
    merged["portfolio_max_10_return_pct"] = float((portfolios.get("max_10") or {}).get("portfolio_return_pct") or 0.0)
    return merged
