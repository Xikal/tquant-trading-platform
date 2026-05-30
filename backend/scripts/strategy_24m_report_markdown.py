from __future__ import annotations

from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 全策略最近 24 个月回测报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 请求窗口：{report['scope']['requested_window']['start']} 至 {report['scope']['requested_window']['end']}",
        f"- 实际评估窗口：{report['scope']['actual_evaluation_window']['start']} 至 {report['scope']['actual_evaluation_window']['end']}，{report['scope']['actual_evaluation_window']['trade_days']} 个交易日",
        f"- 数据覆盖率：{report['coverage']['coverage_pct']}%（{report['coverage']['status']}）",
        f"- 数据缺失原因：{report['coverage']['missing_reason'] or '未发现缺口'}",
        f"- 结论：{report['production_observation_conclusion']['reason']}",
        "",
        "## 方法与约束",
        "",
    ]
    lines.extend(f"- {item}" for item in report["summary"]["execution_constraints"])
    lines.extend(_inventory_lines(report))
    lines.extend(_strategy_summary_lines(report))
    lines.extend(_ranking_lines(report))
    lines.extend(_strategy_family_summary_lines(report))
    lines.extend(_front_row_filter_lines(report))
    lines.extend(_render_breakdown("市场状态分段结果", report["performance_by_market_state"]))
    lines.extend(_render_breakdown("季度分段结果", report["performance_by_quarter"]))
    lines.extend(_render_breakdown("策略族分段结果", report["performance_by_family"]))
    lines.extend(_render_breakdown("信号状态分段结果", report["performance_by_signal_state"]))
    lines.extend(_etf_lines(report))
    lines.extend(_sector_etf_lines(report))
    lines.extend(_smart_t_lines(report))
    lines.extend(_abnormal_lines(report))
    lines.extend(_parameter_lines(report))
    lines.extend(_strategy_detail_lines(report))
    lines.extend(_gap_lines(report))
    return "\n".join(lines) + "\n"


def _inventory_lines(report: dict[str, Any]) -> list[str]:
    return [
        "",
        "## 策略、脚本、API 与数据源识别",
        "",
        f"- 策略来源：`{report['inventory']['strategy_source']}`，共 {report['inventory']['strategy_count']} 个。",
        f"- 回测脚本：{', '.join(f'`{item}`' for item in report['inventory']['backtest_scripts'])}",
        f"- 回测 API：{', '.join(f'`{item}`' for item in report['inventory']['backtest_api'])}",
        f"- 数据源：{', '.join(f'`{item}`' for item in report['inventory']['data_sources'])}",
    ]


def _strategy_summary_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## 全策略汇总表",
        "",
        "| 策略 | 样本 | 成交 | 每日信号等权复利收益 | 年化 | 真实组合max5 | 真实组合max10 | 最大回撤 | Sharpe | 胜率 | PF | 平均单笔 | 止损率 | 平均持仓 | 状态 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["all_strategies"]:
        portfolio = item.get("portfolio_backtests") or {}
        max5 = (portfolio.get("max_5") or {}).get("portfolio_return_pct", 0.0)
        max10 = (portfolio.get("max_10") or {}).get("portfolio_return_pct", 0.0)
        lines.append(
            "| {strategy_title} | {sample_count} | {filled_count} | {return_pct:.2f}% | {annualized_return_pct:.2f}% | {max5:.2f}% | {max10:.2f}% | {max_drawdown_pct:.2f}% | {sharpe_ratio:.2f} | {win_rate_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% | {stop_loss_rate_pct:.2f}% | {avg_holding_days:.2f} | {status} |".format(
                **item,
                return_pct=float(item.get("daily_signal_equal_weight_compound_return_pct", item.get("total_return_pct", 0.0)) or 0.0),
                max5=float(max5 or 0.0),
                max10=float(max10 or 0.0),
            )
        )
    return lines


def _strategy_family_summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report.get("strategy_family_summary") or {}
    families = summary.get("families") or []
    splits = summary.get("time_series_splits") or {}
    lines = [
        "",
        "## 策略族回测闭环",
        "",
        f"- 状态：{summary.get('status', 'research_only')}，策略族 {summary.get('family_count', len(families))} 个，覆盖策略 {summary.get('strategy_count', 0)} 个。",
        f"- 排序影响：{summary.get('sorting_effect', 'none')}；生产参数变更：{'允许' if summary.get('production_parameter_change_allowed') else '不允许'}。",
        "- 防未来函数：信号日只允许使用当日及之前数据；随机切分禁用，生产晋级仍需真实 walk-forward 与 purged gap。",
        "- 训练/验证/样本外：train={train}；validation={validation}；oos={oos}；证据={status}。".format(
            train=", ".join(splits.get("train_quarters") or []) or "-",
            validation=", ".join(splits.get("validation_quarters") or []) or "-",
            oos=", ".join(splits.get("out_of_sample_quarters") or []) or "-",
            status=splits.get("status", "missing_quarter_breakdown"),
        ),
        "",
        "| 策略族 | 策略数 | 策略 | 成交 | 胜率 | PF | 每日信号等权复利收益 | 最大回撤 | 参数建议 | 验证状态 |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not families:
        lines.append("| 无 | 0 | - | 0 | 0.00% | 0.00 | 0.00% | 0.00% | 0 | no_sample |")
        return lines
    for item in families:
        return_pct = float(item.get("daily_signal_equal_weight_compound_return_pct", item.get("total_return_pct") or 0.0) or 0.0)
        lines.append(
            "| {title} | {strategy_count} | {strategies} | {filled_count} | {win_rate_pct:.2f}% | {profit_factor:.2f} | {total_return_pct:.2f}% | {max_drawdown_pct:.2f}% | {parameter_change_count} | {validation_status} |".format(
                title=item.get("title"),
                strategy_count=item.get("strategy_count", 0),
                strategies=", ".join(item.get("strategy_keys") or []),
                filled_count=item.get("filled_count", 0),
                win_rate_pct=float(item.get("win_rate_pct") or 0.0),
                profit_factor=float(item.get("profit_factor") or 0.0),
                total_return_pct=return_pct,
                max_drawdown_pct=float(item.get("max_drawdown_pct") or 0.0),
                parameter_change_count=item.get("parameter_change_count", 0),
                validation_status=item.get("validation_status", ""),
            )
        )
    return lines


def _front_row_filter_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("front_row_filter") or {}
    baseline = payload.get("baseline") or {}
    front_row = payload.get("front_row_only") or {}
    delta = payload.get("delta") or {}
    lines = [
        "",
        "## 前排票过滤 A/B 回测",
        "",
        f"- 状态：{payload.get('status', 'not_run')}；决策：{payload.get('decision', 'not_run')}。",
        "- 生产影响：只读研究结论，不改变默认生产排序或放行参数。",
        "- 防未来函数：baseline 与 front_row_only 使用同一信号日候选，收益从信号后计算，禁止随机切分。",
        "",
        "| 变体 | 样本 | 成交 | 信号日 | 每日信号等权复利收益 | 最大回撤 | 胜率 | PF | 平均单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| baseline | {sample_count} | {filled_count} | {signal_days} | {total_return_pct:.2f}% | {max_drawdown_pct:.2f}% | {win_rate_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% |".format(
            **_front_row_metrics_defaults(baseline)
        ),
        "| front_row_only | {sample_count} | {filled_count} | {signal_days} | {total_return_pct:.2f}% | {max_drawdown_pct:.2f}% | {win_rate_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% |".format(
            **_front_row_metrics_defaults(front_row)
        ),
        "",
        "- 留存/变化：样本 {sample_retention_rate_pct:.2f}%，成交 {filled_retention_rate_pct:.2f}%，信号日 {signal_day_retention_rate_pct:.2f}%；平均单笔 {avg_trade_return_pct_delta:+.3f}%，PF {profit_factor_delta:+.3f}，每日信号等权复利收益 {total_return_pct_delta:+.2f}%，最大回撤改善值 {max_drawdown_reduction_pct:+.2f}%。".format(
            **_front_row_delta_defaults(delta)
        ),
    ]
    notes = payload.get("notes") or []
    lines.extend(f"- {item}" for item in notes)
    strategy_rows = list(payload.get("by_strategy") or [])[:8]
    if strategy_rows:
        lines.extend([
            "",
            "| 策略 | 前排成交 | 成交留存 | 平均单笔变化 | PF变化 |",
            "|---|---:|---:|---:|---:|",
        ])
        for row in strategy_rows:
            item_delta = row.get("delta") or {}
            front = row.get("front_row_only") or {}
            lines.append(
                "| {title} | {filled} | {retention:.2f}% | {avg_delta:+.3f}% | {pf_delta:+.3f} |".format(
                    title=row.get("strategy_title") or row.get("strategy_key") or "",
                    filled=int(front.get("filled_count") or 0),
                    retention=float(item_delta.get("filled_retention_rate_pct") or 0.0),
                    avg_delta=float(item_delta.get("avg_trade_return_pct_delta") or 0.0),
                    pf_delta=float(item_delta.get("profit_factor_delta") or 0.0),
                )
            )
    return lines


def _front_row_metrics_defaults(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_count": int(item.get("sample_count") or 0),
        "filled_count": int(item.get("filled_count") or 0),
        "signal_days": int(item.get("signal_days") or 0),
        "total_return_pct": float(item.get("total_return_pct") or 0.0),
        "max_drawdown_pct": float(item.get("max_drawdown_pct") or 0.0),
        "win_rate_pct": float(item.get("win_rate_pct") or 0.0),
        "profit_factor": float(item.get("profit_factor") or 0.0),
        "avg_trade_return_pct": float(item.get("avg_trade_return_pct") or 0.0),
    }


def _front_row_delta_defaults(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_retention_rate_pct": float(item.get("sample_retention_rate_pct") or 0.0),
        "filled_retention_rate_pct": float(item.get("filled_retention_rate_pct") or 0.0),
        "signal_day_retention_rate_pct": float(item.get("signal_day_retention_rate_pct") or 0.0),
        "avg_trade_return_pct_delta": float(item.get("avg_trade_return_pct_delta") or 0.0),
        "profit_factor_delta": float(item.get("profit_factor_delta") or 0.0),
        "total_return_pct_delta": float(item.get("daily_signal_equal_weight_compound_return_pct_delta", item.get("total_return_pct_delta")) or 0.0),
        "max_drawdown_reduction_pct": float(item.get("max_drawdown_reduction_pct") or 0.0),
    }


def _ranking_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## 策略优先级排名",
        "",
        "- 排名口径：仅使用 buy_now / soft_buy_now 的生产确定买入样本；near_entry 单独展示，不进入生产收益排行。",
        "",
        "| 排名 | 策略 | 分数 | 样本 | 成交 | 胜率 | PF | 平均单笔 | 最大回撤 | 状态 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["strategy_ranking"]:
        lines.append(f"| {row['rank']} | {row['strategy_title']} | {row['score']:.2f} | {row['sample_count']} | {row['filled_count']} | {row['win_rate_pct']:.2f}% | {row['profit_factor']:.2f} | {row['avg_trade_return_pct']:.3f}% | {row['max_drawdown_pct']:.2f}% | {row['status']} |")
    return lines


def _etf_lines(report: dict[str, Any]) -> list[str]:
    etf = report["etf_t0"]
    lines = [
        "",
        "## ETF T0 回测",
        "",
        f"- 状态：{etf['status']}",
        f"- 可 T0 ETF profiles：{etf['eligible_profile_count']}",
        f"- 本地分钟线条数：{etf['minute_bar_count']}，窗口内分钟线：{etf.get('window_minute_bar_count', 0)}。",
        f"- 达标 ETF：{etf.get('accepted_symbol_count', 0)} / {etf['eligible_profile_count']}，验收交易日：{etf.get('expected_trade_day_count', 0)}，阈值：{etf.get('min_trade_day_coverage_pct', 0)}%。",
    ]
    lines.extend(f"- {item}" for item in etf["notes"])
    if etf.get("reports"):
        lines.extend(["", "| ETF | 分类 | 状态 | 样本 | 交易 | 交易日覆盖 | 备注 |", "|---|---|---|---:|---:|---:|---|"])
        for item in etf["reports"]:
            notes = "; ".join(item.get("notes", [])[:2]) if isinstance(item.get("notes"), list) else ""
            lines.append(f"| {item.get('symbol', '')} {item.get('name', '')} | {item.get('category', item.get('base_report', {}).get('category', ''))} | {item.get('status', etf['status'])} | {item.get('sample_count', item.get('base_report', {}).get('bar_count', 0))} | {item.get('trade_count', item.get('base_report', {}).get('trade_count', 0))} | {item.get('trade_day_coverage_pct', 0)}% | {notes} |")
    return lines


def _sector_etf_lines(report: dict[str, Any]) -> list[str]:
    sector = report["sector_etf_t0"]
    lines = [
        "",
        "## 行业 ETF 替代做T（sector_etf_t0）",
        "",
        f"- 状态：{sector['status']}",
        f"- 影子样本/已结算/待结算：{sector['sample_count']} / {sector['settled_count']} / {sector['pending_count']}。",
        f"- 影子胜率/平均置信度/平均预期价差：{sector['success_rate_pct']}% / {sector['avg_confidence']} / {sector['avg_expected_edge_pct']}%。",
        f"- 模拟委托/已成委托/成交：{sector['simulated_order_count']} / {sector['simulated_filled_order_count']} / {sector['simulated_trade_count']}。",
        f"- 本地分钟线条数：{sector['minute_bar_count']}。",
    ]
    lines.extend(f"- {item}" for item in sector["notes"])
    return lines


def _smart_t_lines(report: dict[str, Any]) -> list[str]:
    smart = report["smart_t"]
    payload = smart.get("report", {})
    lines = [
        "",
        "## SmartT 日线代理验证",
        "",
        f"- 状态：{smart['status']}",
        "- 策略链路：`backend/app/services/paper/smart_t_backtest.py`，API `/api/paper/performance/smart-t-backtest`。",
        f"- 信号数：{payload.get('signal_count', 0)}，洗盘加仓样本：{payload.get('washout_signal_count', 0)}。",
        f"- 胜率：{payload.get('success_rate_pct', 0)}%，平均净最大反弹：{payload.get('avg_net_max_return_pct', 0)}%。",
    ]
    lines.extend(f"- {item}" for item in smart["notes"])
    return lines


def _abnormal_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 表现异常策略清单", ""]
    if report["abnormal_strategies"]:
        lines.extend(f"- {item['strategy_title']}（{item['strategy_key']}）：{'; '.join(item['reasons'])}" for item in report["abnormal_strategies"])
    else:
        lines.append("- 未发现异常策略。")
    return lines


def _parameter_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 参数调整建议", ""]
    if report["parameter_adjustment_suggestions"]:
        for item in report["parameter_adjustment_suggestions"]:
            combos = "; ".join(combo["name"] for combo in item["parameter_combinations_for_second_backtest"])
            lines.append(f"- {item['strategy_title']}：{combos}。{item['reason']}")
    else:
        lines.append("- 暂无建议。")
    return lines


def _strategy_detail_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 单策略详细结果", ""]
    for item in report["all_strategies"]:
        lines.extend([
            f"### {item['strategy_title']}（{item['strategy_key']}）",
            "",
            f"- 样本/成交：{item['sample_count']} / {item['filled_count']}，未成交率 {item['unfilled_rate_pct']}%。",
            f"- 收益/风险：每日信号等权复利收益 {item.get('daily_signal_equal_weight_compound_return_pct', item['total_return_pct'])}%，年化 {item['annualized_return_pct']}%，最大回撤 {item['max_drawdown_pct']}%，Sharpe {item['sharpe_ratio']}。",
            f"- 真实组合：max5 收益 {_portfolio_return(item, 'max_5')}%，max10 收益 {_portfolio_return(item, 'max_10')}%，持仓占用资金，同票持有中不重复买。",
            f"- 胜率/PF/平均单笔：{item['win_rate_pct']}% / {item['profit_factor']} / {item['avg_trade_return_pct']}%。",
            f"- 止损率/平均持仓：{item['stop_loss_rate_pct']}% / {item['avg_holding_days']} 天。",
            f"- 退出原因：{_format_counts(item['exit_reason_distribution'])}",
            f"- 未成交/未触发原因：{_format_counts(item['unfilled_reason_distribution']) or '无'}",
            f"- 状态：{item['status']}。{'；'.join(item['notes']) or '无额外说明'}",
            "",
        ])
    return lines


def _gap_lines(report: dict[str, Any]) -> list[str]:
    lines = ["", "## 需要补数据或补测试的问题", ""]
    lines.extend(f"- {item}" for item in report["data_and_test_gaps"])
    conclusion = report["production_observation_conclusion"]
    lines.extend([
        "",
        "## 是否具备进入模拟盘/生产观察",
        "",
        f"- 完整 24m 验收：{conclusion['complete_24m_acceptance']}",
        f"- ETF T0 验收：{conclusion['etf_t0_acceptance']}",
        f"- 行业 ETF 替代做T 验收：{conclusion['sector_etf_t0_acceptance']}",
        f"- SmartT 验收：{conclusion['smart_t_acceptance']}",
        f"- 生产放行：{conclusion['production_ready']}",
        f"- 说明：{conclusion['reason']}",
    ])
    return lines


def _render_breakdown(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = ["", f"## {title}", "", "| 分组 | 样本 | 成交 | 每日信号等权复利收益 | 最大回撤 | Sharpe | 胜率 | PF | 平均单笔 | 止损率 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    if not rows:
        lines.append("| 无 | 0 | 0 | 0.00% | 0.00% | 0.00 | 0.00% | 0.00 | 0.000% | 0.00% |")
        return lines
    for item in rows:
        row = dict(item)
        row["return_pct"] = float(row.get("daily_signal_equal_weight_compound_return_pct", row.get("total_return_pct", 0.0)) or 0.0)
        lines.append("| {title} | {sample_count} | {filled_count} | {return_pct:.2f}% | {max_drawdown_pct:.2f}% | {sharpe_ratio:.2f} | {win_rate_pct:.2f}% | {profit_factor:.2f} | {avg_trade_return_pct:.3f}% | {stop_loss_rate_pct:.2f}% |".format(**row))
    return lines


def _format_counts(values: dict[str, int]) -> str:
    return "；".join(f"{key} {value}" for key, value in values.items())


def _portfolio_return(item: dict[str, Any], key: str) -> float:
    return float(((item.get("portfolio_backtests") or {}).get(key) or {}).get("portfolio_return_pct") or 0.0)
