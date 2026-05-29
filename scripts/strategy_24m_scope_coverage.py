"""Scope coverage inventory for strategy/model optimization reports."""

from __future__ import annotations

from typing import Any

from app.services.strategy_metadata_defaults import DEFAULT_PRESETS


def scope_coverage(sources: dict[str, Any]) -> dict[str, Any]:
    strategy_24m = sources["strategy_24m"]
    closed_loop = sources["closed_loop"]
    main_force = sources["main_force"]
    exit_wf = sources.get("exit_walk_forward", {})
    low_buy_keys = list(strategy_24m.get("scope", {}).get("strategy_keys") or [])
    items = [
        _low_buy_daily_item(strategy_24m, low_buy_keys),
        _etf_t0_item(strategy_24m.get("etf_t0") or {}),
        _sector_etf_t0_item(strategy_24m.get("sector_etf_t0") or {}),
        _smart_t_item(strategy_24m.get("smart_t") or {}),
        _main_force_item(main_force),
        _exit_model_item(closed_loop.get("auxiliary_model_shadow", {}), exit_wf),
        _next_day_event_item(),
        _backtest_preset_item(low_buy_keys),
    ]
    return {
        "inventory_status": "explicit_platform_scope_inventory",
        "item_count": len(items),
        "production_eligible_item_count": sum(1 for item in items if item["production_eligible"]),
        "blocked_or_shadow_item_count": sum(1 for item in items if not item["production_eligible"]),
        "coverage_gaps": _coverage_gaps(items),
        "items": items,
    }


def _low_buy_daily_item(strategy_24m: dict[str, Any], low_buy_keys: list[str]) -> dict[str, Any]:
    coverage = strategy_24m.get("coverage") or {}
    return _item(
        key="low_buy_daily_24m",
        title="低吸/主线/龙头日线策略 24 个月基线",
        surface="low_buy_playbooks",
        status="completed_research_baseline" if coverage.get("status") == "complete" else "partial_data",
        production_eligible=False,
        covered_strategy_keys=low_buy_keys,
        metrics={
            "strategy_count": len(low_buy_keys),
            "coverage_pct": coverage.get("coverage_pct"),
            "actual_window": strategy_24m.get("scope", {}).get("actual_evaluation_window"),
        },
        blockers=[
            "candidate_parameter_grid_not_fully_walk_forwarded",
            "purged_gap_not_executed_for_candidate_grid",
            "production_param_write_from_backtest_forbidden",
        ],
        notes=["已有日线研究基线，但候选参数不能直接写生产。"],
    )


def _etf_t0_item(etf_t0: dict[str, Any]) -> dict[str, Any]:
    return _item(
        key="etf_t0_minute",
        title=etf_t0.get("strategy_title") or "ETF T0 分钟级做T",
        surface="etf_backtest_and_research",
        status=etf_t0.get("status") or "missing",
        production_eligible=False,
        covered_strategy_keys=["etf_t0"],
        metrics={
            "eligible_profile_count": etf_t0.get("eligible_profile_count"),
            "accepted_symbol_count": etf_t0.get("accepted_symbol_count"),
            "minute_bar_count": etf_t0.get("minute_bar_count"),
            "expected_trade_day_count": etf_t0.get("expected_trade_day_count"),
            "min_trade_day_coverage_pct": etf_t0.get("min_trade_day_coverage_pct"),
        },
        blockers=["etf_t0_24m_minute_coverage_not_accepted"],
        notes=etf_t0.get("notes") or [],
    )


def _sector_etf_t0_item(section: dict[str, Any]) -> dict[str, Any]:
    return _item(
        key="sector_etf_t0",
        title=section.get("strategy_title") or "行业 ETF 替代做T",
        surface="paper_auto_and_market_monitor",
        status=section.get("status") or "missing",
        production_eligible=False,
        covered_strategy_keys=["sector_etf_t0"],
        metrics={
            "sample_count": section.get("sample_count"),
            "settled_count": section.get("settled_count"),
            "simulated_order_count": section.get("simulated_order_count"),
            "simulated_trade_count": section.get("simulated_trade_count"),
            "minute_bar_count": section.get("minute_bar_count"),
        },
        blockers=["sector_etf_t0_shadow_or_trade_samples_insufficient"],
        notes=section.get("notes") or [],
    )


def _smart_t_item(section: dict[str, Any]) -> dict[str, Any]:
    report = section.get("report") or {}
    return _item(
        key="smart_t",
        title=section.get("strategy_title") or "个股底仓 SmartT",
        surface="paper_smart_t",
        status=section.get("status") or "missing",
        production_eligible=False,
        covered_strategy_keys=list(report.get("strategies") or ["smart_t"]),
        metrics={
            "signal_count": report.get("signal_count"),
            "washout_signal_count": report.get("washout_signal_count"),
            "success_rate_pct": report.get("success_rate_pct"),
            "forward_days": report.get("forward_days"),
        },
        blockers=["smart_t_minute_or_signal_samples_insufficient"],
        notes=section.get("notes") or [],
    )


def _main_force_item(main_force: dict[str, Any]) -> dict[str, Any]:
    return _item(
        key="main_force_observation_model",
        title="主力建仓/洗盘/拉升观测模型",
        surface="low_buy_shadow_model",
        status=main_force.get("walk_forward", {}).get("evidence_status") or "research_proxy",
        production_eligible=False,
        covered_strategy_keys=["main_force_accumulation_washout_markup_v1"],
        metrics={
            "record_count": main_force.get("record_count"),
            "eligible_count": main_force.get("eligible_count"),
            "oos_promotion_ready": main_force.get("oos_promotion_ready"),
            "shadow_record_count": (main_force.get("shadow_gate") or {}).get("record_count"),
            "shadow_settled_count": (main_force.get("shadow_gate") or {}).get("settled_count"),
        },
        blockers=list(main_force.get("promotion_blockers") or []),
        notes=["只能只读 Shadow；不得直接变成买入规则或生产排序加分。"],
    )


def _exit_model_item(exit_model: dict[str, Any], exit_wf: dict[str, Any]) -> dict[str, Any]:
    return _item(
        key="paper_exit_model",
        title="止盈止损辅助模型",
        surface="paper_exit_shadow",
        status="shadow_candidate" if exit_wf.get("shadow_candidate") else exit_model.get("status", "missing"),
        production_eligible=False,
        covered_strategy_keys=["paper_exit_model_v1"],
        metrics={
            "record_count": exit_model.get("record_count"),
            "settled_count": exit_model.get("settled_count"),
            "walk_forward_passed": exit_wf.get("passed_window_count"),
            "walk_forward_windows": exit_wf.get("window_count"),
            "hard_stop_override_allowed": exit_model.get("hard_stop_override_allowed"),
        },
        blockers=list(exit_model.get("blockers") or []) + list(exit_wf.get("promotion_blockers") or []),
        notes=["可继续 Shadow；不得覆盖硬止损或绕过模拟盘风控。"],
    )


def _next_day_event_item() -> dict[str, Any]:
    return _item(
        key="next_day_event_model",
        title="次日事件模型",
        surface="low_buy_event_metrics",
        status="no_standalone_24m_model_readiness_artifact",
        production_eligible=False,
        covered_strategy_keys=["next_day_event_model"],
        metrics={},
        blockers=["standalone_walk_forward_shadow_drift_report_missing"],
        notes=["当前仅作为事件统计和特征观察，不作为独立生产模型。"],
    )


def _backtest_preset_item(low_buy_keys: list[str]) -> dict[str, Any]:
    preset_rows = [
        {
            "key": preset["key"],
            "strategies": list(preset.get("config", {}).get("strategies") or []),
        }
        for preset in DEFAULT_PRESETS
    ]
    preset_keys = sorted({key for row in preset_rows for key in row["strategies"]})
    uncovered = [key for key in preset_keys if key not in set(low_buy_keys)]
    return _item(
        key="backtest_page_presets",
        title="回测页默认 preset 策略范围",
        surface="backtest_page",
        status="covered_by_low_buy_daily_baseline" if not uncovered else "partial_coverage",
        production_eligible=False,
        covered_strategy_keys=preset_keys,
        metrics={"preset_count": len(preset_rows), "presets": preset_rows, "uncovered_keys": uncovered},
        blockers=["backtest_page_presets_require_same_walk_forward_governance"],
        notes=["回测页 preset 只作为研究入口，不能绕过策略治理直接写生产参数。"],
    )


def _item(**kwargs: Any) -> dict[str, Any]:
    return {
        "key": kwargs["key"],
        "title": kwargs["title"],
        "surface": kwargs["surface"],
        "status": kwargs["status"],
        "production_eligible": bool(kwargs["production_eligible"]),
        "covered_strategy_keys": kwargs["covered_strategy_keys"],
        "metrics": kwargs["metrics"],
        "blockers": [item for item in kwargs["blockers"] if item],
        "notes": kwargs["notes"],
    }


def _coverage_gaps(items: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for item in items:
        if item["production_eligible"]:
            continue
        gaps.extend(f"{item['key']}:{blocker}" for blocker in item["blockers"])
    return gaps
