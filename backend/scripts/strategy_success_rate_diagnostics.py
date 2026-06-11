from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Optional


REPORT_DATE = "2026-06-11"
TARGET_STRATEGIES = ("first_board", "volume_shrink", "late_session_strong_support")
CORE_STRATEGIES = ("first_board", "volume_shrink")
FORBIDDEN_PROMOTION_METRICS = ("spike_return_*", "avg_max_gain_5d", "max_gain_5d")

SOURCE_STRATEGY_24M = Path("backend/data/analytics/reports/strategy_24m_duckdb_report.json")
SOURCE_EXECUTION_MATRIX = Path(
    "backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json"
)
SOURCE_TARGET_EXECUTION_MATRIX = Path(
    "backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_first_board_volume_shrink_late_session_strong_support_auto_auto.json"
)
SOURCE_TRADABILITY = Path("docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json")
SOURCE_N_PATTERN_OBSERVE = Path("backend/data/reports/n_pattern_observe_confirmed/low_buy_market_backtest_24m_empty.json")
SOURCE_LATEST_BACKTEST = Path("backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.json")

DEFAULT_DOCS_REPORT_DIR = Path("docs/reports")
DEFAULT_DATA_REPORT_DIR = Path("backend/data/reports/strategy-success-rate")
SOURCE_PATHS: dict[str, Path] = {
    "strategy_24m": SOURCE_STRATEGY_24M,
    "execution_matrix": SOURCE_EXECUTION_MATRIX,
    "target_execution_matrix": SOURCE_TARGET_EXECUTION_MATRIX,
    "tradability": SOURCE_TRADABILITY,
    "n_pattern_observe": SOURCE_N_PATTERN_OBSERVE,
    "latest_backtest": SOURCE_LATEST_BACKTEST,
}


@dataclass(frozen=True)
class ReportResult:
    batch: str
    slug: str
    markdown_path: Path
    json_path: Path
    status: str


SourceBundle = dict[str, Any]
PayloadBuilder = Callable[[SourceBundle, Optional[dict[str, Any]]], dict[str, Any]]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_bundle(*, validate: bool = True) -> SourceBundle:
    bundle: SourceBundle = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    bundle["source_paths"] = {key: str(path) for key, path in SOURCE_PATHS.items()}
    if validate:
        validate_source_bundle(bundle)
    return bundle


def validate_source_bundle(sources: SourceBundle) -> None:
    source_paths = sources.get("source_paths") or {}
    missing = [
        f"{key}: {source_paths.get(key, '<unknown path>')}"
        for key in SOURCE_PATHS
        if (sources.get(key) or {}).get("_missing")
    ]
    if missing:
        details = "\n- ".join(missing)
        raise FileNotFoundError(
            "Missing required strategy success-rate source artifacts:\n"
            f"- {details}\n"
            "Regenerate the prerequisite 24M, execution-matrix, tradability, and observe-confirmed artifacts before "
            "building strategy success-rate reports."
        )


def git_snapshot() -> dict[str, Any]:
    return {
        "branch": _run_git(["branch", "--show-current"]),
        "status_short": [line for line in _run_git(["status", "--short"]).splitlines() if line],
    }


def _run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return result.stderr.strip()
    return result.stdout.strip()


def generated_at_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz=tz).replace(microsecond=0).isoformat()


def build_baseline_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    strategies = [_strategy_summary(row) for row in _target_strategy_rows(report)]
    return _payload(
        batch="D0",
        slug="strategy-success-rate-baseline",
        title="策略成功率优化基线报告",
        status="ready",
        sources=sources,
        git=git,
        body={
            "input_reports": {
                "strategy_report_status": report.get("status"),
                "manifest": report.get("manifest") or {},
                "data_quality_conclusion": report.get("data_quality_conclusion"),
                "live_vs_backtest": report.get("live_vs_backtest") or {},
            },
            "target_strategies": strategies,
            "code_anchors": [
                "backend/scripts/low_buy_market_backtest_reporting.py",
                "backend/scripts/low_buy_execution_matrix.py",
                "backend/app/services/low_buy/execution_simulation.py",
                "backend/app/services/decision_context/market_gate.py",
                "backend/app/services/low_buy/intraday_confirmation.py",
                "backend/app/services/track_record/",
            ],
            "test_anchors": [
                "backend/tests/test_strategy_24m_duckdb_report.py",
                "backend/tests/test_low_buy_trade_controls.py",
                "backend/tests/test_low_buy_backtest_isolation.py",
                "backend/tests/test_decision_context_market_gate.py",
                "backend/tests/test_low_buy_intraday_confirmation.py",
                "backend/tests/test_track_record_ledger.py",
                "backend/tests/test_track_record_realized.py",
                "backend/tests/test_track_record_drift.py",
                "backend/tests/test_low_buy_production_scoring.py",
                "backend/tests/test_low_buy_priority_board_strategy_variants.py",
                "backend/tests/test_strategy_engine_production_gate_guards.py",
                "backend/tests/test_strategy_engine_boundary.py",
            ],
            "metric_guardrails": _metric_guardrails(),
            "batch_conclusion": {
                "status": "ready",
                "production_change_allowed": False,
                "reason": "D0 only records current facts and constraints.",
            },
        },
    )


def build_first_board_oos_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    strategy = _strategy_by_key(report).get("first_board", {})
    quarter = _row_by_key(strategy.get("quarter_breakdown") or [], "2026Q2")
    aggregate = _aggregate_fade_indicators(sources, TARGET_STRATEGIES)
    return _payload(
        batch="D1",
        slug="first-board-oos-diagnosis",
        title="first_board OOS 诊断与回吐池报告",
        status="blocked_by_data",
        sources=sources,
        git=git,
        body={
            "first_board_oos": {
                "oos": strategy.get("oos") or {},
                "quarter_2026q2": quarter,
                "market_state_breakdown": strategy.get("market_state_breakdown") or [],
                "sector_breakdown_caveat": (strategy.get("sector_breakdown") or {}).get("production_caveat", ""),
            },
            "diagnosis": {
                "status": "blocked_by_data",
                "category": "数据不足，阻断调参",
                "production_tuning_allowed": False,
                "reason": (
                    "The stored 24M artifact contains quarter-level aggregates and limited top examples, "
                    "but not the complete per-trade OOS outcome records required for month x market_state x sector attribution."
                ),
                "required_inputs": [
                    "full TradeOutcome rows for first_board 2026Q2 quarter_proxy",
                    "per-trade market_state, sector_name, entry_trade_date, exit_trade_date",
                    "per-trade max_gain_5d and return_5d for throwback-pool counting",
                    "cost/liquidity fields or join keys to daily_bars amount",
                ],
            },
            "throwback_pool": {
                "status": "blocked_by_data",
                "definition": "max_gain_5d >= 3 and return_5d <= 0",
                "production_tuning_allowed": False,
                "reason": "The available report exposes only aggregate avg_max_gain_5d/avg_return_5d and top examples, not complete per-trade rows.",
                "aggregate_fade_indicators": aggregate,
            },
            "batch_conclusion": {
                "status": "blocked_by_data",
                "production_change_allowed": False,
                "next_step": "Regenerate or persist full outcome rows before tuning first_board.",
            },
        },
    )


def build_exit_variants_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    matrix = sources["execution_matrix"]
    target_matrix = sources["target_execution_matrix"]
    rows = matrix.get("rows") or []
    target_rows = target_matrix.get("rows") or []
    coverage_status = sorted({str(row.get("coverage_status") or "") for row in rows if row})
    best_by_pf = matrix.get("best_by_profit_factor")
    return _payload(
        batch="D2",
        slug="strategy-exit-variants",
        title="出场矩阵与分批出场研究结论",
        status="partial_data",
        sources=sources,
        git=git,
        body={
            "existing_execution_matrix": {
                "scope": matrix.get("scope") or {},
                "rows": [_execution_matrix_row(row) for row in rows],
                "best_by_profit_factor": best_by_pf,
                "best_by_avg_net_return": matrix.get("best_by_avg_net_return"),
                "best_by_drawdown": matrix.get("best_by_drawdown"),
            },
            "target_strategy_matrix_run": {
                "scope": target_matrix.get("scope") or {},
                "rows": [_execution_matrix_row(row) for row in target_rows],
                "status": _matrix_status(target_rows),
                "note": (
                    "Target-strategy matrix command was executed locally. Empty coverage is treated as no evidence, "
                    "not as a green production result."
                ),
            },
            "partial_exit_model_decision": {
                "needed_now": False,
                "reason": (
                    "Existing matrix already shows the quick_tp3_trailing1 research variant as strongest, "
                    "but the artifact is partial coverage and all-strategy scope. A strict half-take-profit model "
                    "would be premature without full target-strategy outcome rows."
                ),
                "default_behavior_changed": False,
                "production_change_allowed": False,
            },
            "batch_conclusion": {
                "status": "partial_data",
                "production_change_allowed": False,
                "required_before_production": [
                    "target-only full coverage matrix for first_board/volume_shrink/late_session_strong_support",
                    "24M + walk-forward + OOS comparison against baseline",
                    "guard tests if any production exit semantics are proposed",
                ],
                "coverage_status": coverage_status,
            },
        },
    )


def build_market_state_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    rows: list[dict[str, Any]] = []
    for strategy in _target_strategy_rows(report):
        for state in strategy.get("market_state_breakdown") or []:
            rows.append(
                {
                    "strategy_key": strategy.get("strategy_key"),
                    "strategy_title": strategy.get("strategy_title"),
                    "market_state": state.get("key"),
                    "sample_count": state.get("sample_count"),
                    "filled_count": state.get("filled_count"),
                    "win_rate_pct": state.get("win_rate_pct"),
                    "profit_factor": state.get("profit_factor"),
                    "avg_trade_return_pct": state.get("avg_trade_return_pct"),
                    "max_drawdown_pct": state.get("max_drawdown_pct"),
                    "total_return_pct": state.get("total_return_pct"),
                }
            )
    weak_rows = [
        row
        for row in rows
        if (row.get("profit_factor") or 0) < 1.0 or (row.get("avg_trade_return_pct") or 0) < 0
    ]
    return _payload(
        batch="D3",
        slug="strategy-market-state-matrix",
        title="策略 x market_state 矩阵",
        status="ready",
        sources=sources,
        git=git,
        body={
            "matrix": rows,
            "research_gate_recommendation": {
                "status": "no_strategy_gate_change",
                "feature_flag_required_if_added": True,
                "production_change_allowed": False,
                "reason": (
                    "The available confirmed target-strategy breakdown does not show a direct weak/retreat state concentration "
                    "that justifies changing production market_gate semantics."
                ),
                "weak_rows": weak_rows,
            },
            "batch_conclusion": {
                "status": "ready",
                "production_change_allowed": False,
                "priority_board_sort_changed": False,
            },
        },
    )


def build_intraday_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    tradability = sources["tradability"]
    minute_coverage = tradability.get("minute_coverage") or {}
    tick_coverage = tradability.get("tick_coverage") or {}
    coverage_pct = float(minute_coverage.get("coverage_pct") or 0.0)
    status = "partial_minute_coverage" if coverage_pct < 60.0 else "ready_for_research"
    return _payload(
        batch="D4",
        slug="strategy-volume-shrink-intraday-confirmation",
        title="volume_shrink 分时确认研究",
        status=status,
        sources=sources,
        git=git,
        body={
            "confirmation_research": {
                "strategy_key": "volume_shrink",
                "status": status,
                "minute_coverage": minute_coverage,
                "tick_coverage": tick_coverage,
                "sample_retention_gate_pct": 60.0,
                "production_confirmation_collection_changed": False,
                "volume_shrink_requires_production_confirmation_now": _volume_shrink_requires_production_confirmation(),
            },
            "batch_conclusion": {
                "status": status,
                "production_change_allowed": False,
                "reason": "Minute/tick coverage is insufficient for production confirmation research; missing data is not treated as pass.",
            },
        },
    )


def build_cost_liquidity_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    strategies = []
    for strategy in _target_strategy_rows(report):
        strategies.append(
            {
                "strategy_key": strategy.get("strategy_key"),
                "avg_trade_return_pct": strategy.get("avg_trade_return_pct"),
                "portfolio_backtests": _portfolio_summaries(strategy),
                "base_cost_bps": _first_portfolio_value(strategy, "base_round_trip_cost_bps"),
                "extra_cost_bps": _first_portfolio_value(strategy, "extra_cost_bps"),
            }
        )
    return _payload(
        batch="D5",
        slug="strategy-cost-liquidity-sensitivity",
        title="成本/滑点/流动性敏感性报告",
        status="blocked_by_data",
        sources=sources,
        git=git,
        body={
            "available_cost_baseline": strategies,
            "amount_bucket_research": {
                "status": "blocked_by_data",
                "bucket_definitions": ["<5000万", "5000万-2亿", ">2亿"],
                "production_change_allowed": False,
                "reason": (
                    "Stored strategy reports do not include complete per-trade amount or joinable full outcome rows. "
                    "portfolio_backtest_metrics default extra_cost_bps behavior remains unchanged."
                ),
            },
            "batch_conclusion": {
                "status": "blocked_by_data",
                "portfolio_backtest_metrics_default_changed": False,
                "production_change_allowed": False,
            },
        },
    )


def build_correlation_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    skip_rows = []
    for strategy in _target_strategy_rows(report):
        if strategy.get("strategy_key") not in CORE_STRATEGIES:
            continue
        portfolios = _portfolio_summaries(strategy)
        skip_rows.append(
            {
                "strategy_key": strategy.get("strategy_key"),
                "portfolio_backtests": portfolios,
                "same_symbol_open_skips": {
                    key: value.get("skipped_by_duplicate_symbol")
                    for key, value in portfolios.items()
                },
                "sector_limit_skips": {
                    key: value.get("skipped_by_sector_limit")
                    for key, value in portfolios.items()
                },
            }
        )
    return _payload(
        batch="D6",
        slug="strategy-correlation-dedup",
        title="信号去相关与组合执行层报告",
        status="blocked_by_data",
        sources=sources,
        git=git,
        body={
            "available_portfolio_overlap_guards": skip_rows,
            "same_day_overlap_research": {
                "status": "blocked_by_data",
                "production_change_allowed": False,
                "reason": (
                    "Same-day same-symbol/same-sector overlap requires full per-trade signal_date, symbol, sector_name and score rows. "
                    "Current artifacts only expose portfolio skip counters after existing no-overlap rules."
                ),
            },
            "batch_conclusion": {
                "status": "blocked_by_data",
                "single_strategy_signals_changed": False,
                "portfolio_execution_variant_added": False,
                "production_change_allowed": False,
            },
        },
    )


def build_retired_reentry_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    strategies = _strategy_by_key(report)
    late = _strategy_summary(strategies.get("late_session_strong_support", {}))
    n_pattern = sources["n_pattern_observe"]
    return _payload(
        batch="D7",
        slug="strategy-retired-reentry-research",
        title="退役/限权策略回归研究报告",
        status="ready",
        sources=sources,
        git=git,
        body={
            "late_session_strong_support": {
                "baseline": late,
                "decision": "keep_low_sample_capped",
                "promotion_allowed": False,
                "required_before_promotion": ["filled_count >= 100", "walk_forward passed_window_count >= 4/7"],
            },
            "n_pattern_observe_confirmed": {
                "artifact_status": "available_empty" if not n_pattern.get("_missing") else "missing",
                "summary": n_pattern.get("summary") or {},
                "promotion_allowed": False,
                "decision": "research_only_no_override",
            },
            "batch_conclusion": {
                "status": "ready",
                "strategy_policy_changed": False,
                "production_override_written": False,
            },
        },
    )


def build_drift_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    report = sources["strategy_24m"]
    live_vs_backtest = report.get("live_vs_backtest") or {}
    return _payload(
        batch="D8",
        slug="strategy-drift-observation",
        title="track record 漂移观察包",
        status="ready",
        sources=sources,
        git=git,
        body={
            "live_vs_backtest": live_vs_backtest,
            "drift_observation_package": {
                "status": "prepared_local_only",
                "drift_alert_enabled_default": False,
                "online_capture_executed": False,
                "online_write_executed": False,
                "advisory_only": True,
                "local_acceptance_tests": [
                    "backend/tests/test_track_record_ledger.py",
                    "backend/tests/test_track_record_realized.py",
                    "backend/tests/test_track_record_drift.py",
                ],
            },
            "batch_conclusion": {
                "status": "ready",
                "production_change_allowed": False,
                "reason": "Online ledger capture and drift task writes need separate authorization.",
            },
        },
    )


def build_production_review_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers = [
        "D1 full first_board OOS attribution is blocked by missing per-trade outcomes.",
        "D4 volume_shrink intraday confirmation is partial_minute_coverage.",
        "D5 cost/liquidity buckets are blocked by missing per-trade amount or joinable outcomes.",
        "D6 same-day overlap research is blocked by missing full signal rows.",
        "No candidate has passed 24M + walk-forward + OOS + real portfolio + cost sensitivity + guard tests.",
    ]
    return _payload(
        batch="D9",
        slug="strategy-success-rate-production-review",
        title="策略成功率优化生产评审包",
        status="not_ready",
        sources=sources,
        git=git,
        body={
            "production_review": {
                "status": "not_ready",
                "production_code_change_required": False,
                "production_change_allowed": False,
                "candidate_to_promote": None,
                "blockers": blockers,
            },
            "required_gates": {
                "24m": "available",
                "walk_forward": "available for current tiers",
                "oos": "aggregate_only_for_current quarter_proxy",
                "real_portfolio": "available via portfolio_backtest_metrics",
                "cost_sensitivity": "blocked_by_data for amount buckets",
                "guard_tests": "must pass before any authorized production change",
            },
            "batch_conclusion": {
                "status": "not_ready",
                "production_change_allowed": False,
                "deployment_executed": False,
                "cutover_executed": False,
                "online_write_executed": False,
            },
        },
    )


def build_implementation_report_payload(sources: SourceBundle, git: dict[str, Any] | None = None) -> dict[str, Any]:
    return _payload(
        batch="SUMMARY",
        slug="strategy-success-rate-implementation-report",
        title="策略成功率优化收口实施报告",
        status="completed_research_reports",
        sources=sources,
        git=git,
        body={
            "batch_statuses": [
                {"batch": "D0", "status": "ready", "artifact": "strategy-success-rate-baseline"},
                {"batch": "D1", "status": "blocked_by_data", "artifact": "first-board-oos-diagnosis"},
                {"batch": "D2", "status": "partial_data", "artifact": "strategy-exit-variants"},
                {"batch": "D3", "status": "ready", "artifact": "strategy-market-state-matrix"},
                {"batch": "D4", "status": "partial_minute_coverage", "artifact": "strategy-volume-shrink-intraday-confirmation"},
                {"batch": "D5", "status": "blocked_by_data", "artifact": "strategy-cost-liquidity-sensitivity"},
                {"batch": "D6", "status": "blocked_by_data", "artifact": "strategy-correlation-dedup"},
                {"batch": "D7", "status": "ready", "artifact": "strategy-retired-reentry-research"},
                {"batch": "D8", "status": "ready", "artifact": "strategy-drift-observation"},
                {"batch": "D9", "status": "not_ready", "artifact": "strategy-success-rate-production-review"},
            ],
            "hard_boundaries": _hard_boundaries(),
            "online_actions": {
                "deployment_executed": False,
                "cutover_executed": False,
                "online_write_executed": False,
                "container_stop_executed": False,
                "docker_cache_cleanup_executed": False,
                "sysctl_changed": False,
            },
        },
    )


REPORT_BUILDERS: dict[str, PayloadBuilder] = {
    "D0": build_baseline_payload,
    "D1": build_first_board_oos_payload,
    "D2": build_exit_variants_payload,
    "D3": build_market_state_payload,
    "D4": build_intraday_payload,
    "D5": build_cost_liquidity_payload,
    "D6": build_correlation_payload,
    "D7": build_retired_reentry_payload,
    "D8": build_drift_payload,
    "D9": build_production_review_payload,
    "SUMMARY": build_implementation_report_payload,
}


def build_all_payloads(sources: SourceBundle | None = None, git: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    bundle = sources or load_source_bundle()
    return {batch: builder(bundle, git) for batch, builder in REPORT_BUILDERS.items()}


def generate_reports(
    *,
    batch: str,
    docs_report_dir: Path = DEFAULT_DOCS_REPORT_DIR,
    data_report_dir: Path = DEFAULT_DATA_REPORT_DIR,
    sources: SourceBundle | None = None,
    git: dict[str, Any] | None = None,
) -> list[ReportResult]:
    normalized = batch.upper()
    selected = list(REPORT_BUILDERS) if normalized == "ALL" else [normalized]
    bundle = sources or load_source_bundle()
    validate_source_bundle(bundle)
    git_info = git if git is not None else git_snapshot()
    docs_report_dir.mkdir(parents=True, exist_ok=True)
    data_report_dir.mkdir(parents=True, exist_ok=True)
    results: list[ReportResult] = []
    for item in selected:
        if item not in REPORT_BUILDERS:
            raise ValueError(f"Unknown batch: {batch}")
        payload = REPORT_BUILDERS[item](bundle, git_info)
        slug = str(payload["report_slug"])
        json_path = data_report_dir / f"{slug}-{REPORT_DATE}.json"
        md_path = docs_report_dir / f"{slug}-{REPORT_DATE}.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        results.append(ReportResult(item, slug, md_path, json_path, str(payload.get("status") or "")))
    return results


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['title']}（{REPORT_DATE}）",
        "",
        f"- 批次：`{payload['batch']}`",
        f"- 状态：`{payload['status']}`",
        f"- 生成时间：`{payload['generated_at']}`",
        f"- 分支：`{payload.get('git', {}).get('branch', '')}`",
        "",
        "## 硬边界",
    ]
    for item in payload["hard_boundaries"]:
        lines.append(f"- {item}")
    lines.extend(["", "## 数据源"])
    for key, path in payload.get("source_paths", {}).items():
        lines.append(f"- `{key}`：`{path}`")
    status_short = payload.get("git", {}).get("status_short") or []
    lines.extend(["", "## Git 保护状态"])
    if status_short:
        for line in status_short:
            lines.append(f"- `{line}`")
    else:
        lines.append("- 工作树无 `git status --short` 输出。")
    lines.extend(["", "## 核心内容"])
    lines.extend(_render_body(payload.get("body") or {}))
    lines.extend(["", "## 机器产物"])
    lines.append(f"- JSON：`backend/data/reports/strategy-success-rate/{payload['report_slug']}-{REPORT_DATE}.json`")
    lines.append(f"- Markdown：`docs/reports/{payload['report_slug']}-{REPORT_DATE}.md`")
    lines.append("")
    return "\n".join(lines)


def _render_body(body: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "target_strategies" in body:
        lines.append(_table(
            ["策略", "层级", "样本", "成交", "胜率", "PF", "平均单笔", "回撤", "WF", "OOS"],
            [
                [
                    row["strategy_key"],
                    row["policy_tier"],
                    row["sample_count"],
                    row["filled_count"],
                    _pct_text(row["win_rate_pct"]),
                    row["profit_factor"],
                    _pct_text(row["avg_trade_return_pct"]),
                    _pct_text(row["max_drawdown_pct"]),
                    row["walk_forward_summary"],
                    row["oos_summary"],
                ]
                for row in body["target_strategies"]
            ],
        ))
    if "first_board_oos" in body:
        oos = body["first_board_oos"].get("oos") or {}
        lines.append(f"- first_board OOS：成交 `{oos.get('filled_count')}`，PF `{oos.get('profit_factor')}`，收益 `{_pct_text(oos.get('daily_signal_equal_weight_compound_return_pct'))}`。")
        lines.append(f"- 诊断状态：`{body['diagnosis']['status']}`，结论：{body['diagnosis']['category']}。")
        lines.append(f"- 回吐池状态：`{body['throwback_pool']['status']}`；未使用 `max_gain_5d` 作为生产晋级收益。")
    if "existing_execution_matrix" in body:
        lines.append(_table(
            ["变体", "覆盖", "成交", "胜率", "PF", "平均净收益", "最大回撤"],
            [
                [
                    row["variant_key"],
                    row["coverage_status"],
                    row["filled_count"],
                    _pct_text(row["net_win_rate"]),
                    row["execution_profit_factor"],
                    _pct_text(row["avg_net_return_pct"]),
                    _pct_text(row["max_drawdown_pct"]),
                ]
                for row in body["existing_execution_matrix"]["rows"]
            ],
        ))
        target_run = body.get("target_strategy_matrix_run") or {}
        if target_run:
            lines.append(f"- 目标策略矩阵状态：`{target_run.get('status')}`，空样本/非完整覆盖不作为生产通过证据。")
        lines.append(f"- 分批出场新增：`{body['partial_exit_model_decision']['needed_now']}`，默认行为未变。")
    if "matrix" in body:
        lines.append(_table(
            ["策略", "market_state", "样本", "成交", "胜率", "PF", "平均单笔", "最大回撤"],
            [
                [
                    row["strategy_key"],
                    row["market_state"],
                    row["sample_count"],
                    row["filled_count"],
                    _pct_text(row["win_rate_pct"]),
                    row["profit_factor"],
                    _pct_text(row["avg_trade_return_pct"]),
                    _pct_text(row["max_drawdown_pct"]),
                ]
                for row in body["matrix"]
            ],
        ))
        lines.append(f"- 策略级门控：`{body['research_gate_recommendation']['status']}`，仅 research/flag-off。")
    if "confirmation_research" in body:
        research = body["confirmation_research"]
        coverage = research.get("minute_coverage") or {}
        lines.append(f"- volume_shrink 分时确认状态：`{research['status']}`，分钟覆盖 `{coverage.get('coverage_pct', 0)}`%。")
        lines.append("- 未把 `volume_shrink` 加入生产 VWAP/尾盘确认集合。")
    if "available_cost_baseline" in body:
        lines.append(f"- 成本分桶状态：`{body['amount_bucket_research']['status']}`。")
        lines.append("- `portfolio_backtest_metrics(extra_cost_bps)` 默认行为未变。")
    if "available_portfolio_overlap_guards" in body:
        lines.append(f"- 同日同票/同板块重叠统计：`{body['same_day_overlap_research']['status']}`。")
        lines.append("- 单策略信号未变，组合层去重变体未启用。")
    if "late_session_strong_support" in body:
        late = body["late_session_strong_support"]["baseline"]
        lines.append(f"- late_session：成交 `{late.get('filled_count')}`，walk-forward `{late.get('walk_forward_summary')}`，继续低样本限权。")
        lines.append("- N 字家族仅 observe_confirmed 研究态，不写生产 override。")
    if "drift_observation_package" in body:
        pkg = body["drift_observation_package"]
        lines.append(f"- 漂移包：`{pkg['status']}`，`DRIFT_ALERT_ENABLED` 默认 `{pkg['drift_alert_enabled_default']}`。")
        lines.append("- 未执行线上账本捕获或线上写库。")
    if "production_review" in body:
        review = body["production_review"]
        lines.append(f"- 生产评审状态：`{review['status']}`；生产代码改动：`{review['production_code_change_required']}`。")
        for blocker in review.get("blockers") or []:
            lines.append(f"- 阻断：{blocker}")
    if "batch_statuses" in body:
        lines.append(_table(
            ["批次", "状态", "产物"],
            [[row["batch"], row["status"], row["artifact"]] for row in body["batch_statuses"]],
        ))
    if "batch_conclusion" in body:
        lines.append("")
        lines.append(f"批次结论：`{body['batch_conclusion'].get('status')}`；生产变更允许：`{body['batch_conclusion'].get('production_change_allowed', False)}`。")
    return lines


def _payload(
    *,
    batch: str,
    slug: str,
    title: str,
    status: str,
    sources: SourceBundle,
    git: dict[str, Any] | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    return {
        "batch": batch,
        "report_slug": slug,
        "title": title,
        "status": status,
        "generated_at": generated_at_iso(),
        "source_paths": sources.get("source_paths") or {},
        "git": git or {},
        "hard_boundaries": _hard_boundaries(),
        "metric_guardrails": _metric_guardrails(),
        "body": body,
    }


def _hard_boundaries() -> list[str]:
    return [
        "不修改 backend/app/services/low_buy/strategy_policy.py。",
        "不改变 production_score、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。",
        "strategy_engine 保持 shadow-only，replacement_enabled=false。",
        "research/ML/因子/重分析任务不回到 Web 主进程。",
        "portfolio_backtest_metrics 继续作为真实组合回测唯一事实源。",
        "spike_return_*、avg_max_gain_5d、max_gain_5d 只作诊断，不作生产晋级收益指标。",
        "本轮不部署、不切流、不执行线上写操作。",
    ]


def _metric_guardrails() -> dict[str, Any]:
    return {
        "production_return_fact_source": "portfolio_backtest_metrics",
        "forbidden_promotion_metrics": list(FORBIDDEN_PROMOTION_METRICS),
        "win_rate_role": "auxiliary_only",
    }


def _target_strategy_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    by_key = _strategy_by_key(report)
    return [by_key[key] for key in TARGET_STRATEGIES if key in by_key]


def _strategy_by_key(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("strategy_key")): row
        for row in report.get("all_strategies") or []
        if row.get("strategy_key")
    }


def _strategy_summary(row: dict[str, Any]) -> dict[str, Any]:
    walk_forward = row.get("walk_forward") or {}
    oos = row.get("oos") or {}
    return {
        "strategy_key": row.get("strategy_key"),
        "strategy_title": row.get("strategy_title"),
        "policy_tier": row.get("policy_tier"),
        "sample_count": row.get("sample_count"),
        "filled_count": row.get("filled_count"),
        "win_rate_pct": row.get("win_rate_pct"),
        "profit_factor": row.get("profit_factor"),
        "avg_trade_return_pct": row.get("avg_trade_return_pct"),
        "max_drawdown_pct": row.get("max_drawdown_pct"),
        "quarter_stability": row.get("quarter_stability") or {},
        "walk_forward": walk_forward,
        "walk_forward_summary": _walk_forward_summary(walk_forward),
        "oos": oos,
        "oos_summary": _oos_summary(oos),
        "portfolio_backtests": _portfolio_summaries(row),
        "priority_board_eligible": row.get("priority_board_eligible"),
    }


def _portfolio_summaries(strategy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    portfolios = strategy.get("portfolio_backtests") or {}
    return {key: _portfolio_summary(value) for key, value in portfolios.items()}


def _portfolio_summary(value: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "capital_model_label",
        "candidate_count",
        "trade_count",
        "portfolio_return_pct",
        "profit_factor",
        "avg_trade_return_pct",
        "max_drawdown_pct",
        "base_round_trip_cost_bps",
        "extra_cost_bps",
        "total_cost_bps_assumption",
        "same_symbol_reentry_blocked",
        "sector_daily_limit",
        "skipped_by_duplicate_symbol",
        "skipped_by_sector_limit",
        "skipped_by_strategy_daily_limit",
    )
    return {key: value.get(key) for key in keys}


def _first_portfolio_value(strategy: dict[str, Any], key: str) -> Any:
    portfolios = strategy.get("portfolio_backtests") or {}
    for value in portfolios.values():
        if key in value:
            return value.get(key)
    return None


def _execution_matrix_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "variant_key",
        "title",
        "purpose",
        "coverage_status",
        "coverage_pct",
        "evaluated_count",
        "filled_count",
        "net_win_rate",
        "avg_net_return_pct",
        "execution_profit_factor",
        "max_drawdown_pct",
        "total_return_pct",
        "filled_exit_reason_counts",
    )
    return {key: row.get(key) for key in keys}


def _matrix_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "missing"
    if all(int(row.get("filled_count") or 0) == 0 for row in rows):
        return "empty_no_evidence"
    if any(str(row.get("coverage_status") or "") != "complete" for row in rows):
        return "partial_data"
    return "ready"


def _aggregate_fade_indicators(sources: SourceBundle, strategies: tuple[str, ...]) -> list[dict[str, Any]]:
    report = sources["strategy_24m"]
    latest = sources["latest_backtest"]
    latest_by_key = {
        str(row.get("strategy_key")): row
        for row in latest.get("strategies") or []
        if row.get("strategy_key")
    }
    rows = []
    for strategy in strategies:
        source = latest_by_key.get(strategy) or _strategy_by_key(report).get(strategy, {})
        rows.append(
            {
                "strategy_key": strategy,
                "avg_max_gain_5d": source.get("avg_max_gain_5d") or (source.get("confirmed_result") or {}).get("avg_max_gain_5d"),
                "avg_return_5d": source.get("avg_return_5d") or (source.get("confirmed_result") or {}).get("avg_return_5d"),
                "note": "aggregate_diagnostic_only_not_promotion_metric",
            }
        )
    return rows


def _row_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    for row in rows:
        if row.get("key") == key:
            return row
    return {}


def _walk_forward_summary(value: dict[str, Any]) -> str:
    if not value:
        return "missing"
    return f"{value.get('passed_window_count', 0)}/{value.get('window_count', 0)} pass"


def _oos_summary(value: dict[str, Any]) -> str:
    if not value:
        return "missing"
    return f"{value.get('status')} filled={value.get('filled_count')} PF={value.get('profit_factor')} return={value.get('daily_signal_equal_weight_compound_return_pct')}%"


def _volume_shrink_requires_production_confirmation() -> bool:
    try:
        from app.services.low_buy.intraday_confirmation import strategy_requires_intraday_confirmation
    except Exception:
        return False
    return bool(strategy_requires_intraday_confirmation("volume_shrink"))


def _table(headers: list[Any], rows: list[list[Any]]) -> str:
    text = ["| " + " | ".join(str(item) for item in headers) + " |"]
    text.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        text.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(text)


def _pct_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value}%"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate strategy success-rate optimization research reports.")
    parser.add_argument(
        "--batch",
        default="ALL",
        help="Batch to generate: D0..D9, SUMMARY, or ALL.",
    )
    parser.add_argument("--docs-report-dir", default=str(DEFAULT_DOCS_REPORT_DIR))
    parser.add_argument("--data-report-dir", default=str(DEFAULT_DATA_REPORT_DIR))
    args = parser.parse_args()
    results = generate_reports(
        batch=args.batch,
        docs_report_dir=Path(args.docs_report_dir),
        data_report_dir=Path(args.data_report_dir),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "reports": [
                    {
                        "batch": item.batch,
                        "slug": item.slug,
                        "status": item.status,
                        "markdown": str(item.markdown_path),
                        "json": str(item.json_path),
                    }
                    for item in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
