#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .agent_os_acceptance_common import (
        DEFAULT_DATASET,
        DEFAULT_ORCHESTRATION,
        DEFAULT_OUTPUT,
        StepResult,
        overall_status,
        summary,
        timed,
    )
    from .agent_os_acceptance_research import (
        _empty_strategy_samples,
        load_priority_symbols,
        run_feishu_daily_push,
        run_openbb_check,
        run_qlib_report,
    )
    from .agent_os_acceptance_workflow import (
        load_orchestration,
        run_hermes_workflow,
        validate_hermes_workflow_result,
        validate_orchestration_contract,
    )
except ImportError:
    from agent_os_acceptance_common import (
        DEFAULT_DATASET,
        DEFAULT_ORCHESTRATION,
        DEFAULT_OUTPUT,
        StepResult,
        overall_status,
        summary,
        timed,
    )
    from agent_os_acceptance_research import (
        _empty_strategy_samples,
        load_priority_symbols,
        run_feishu_daily_push,
        run_openbb_check,
        run_qlib_report,
    )
    from agent_os_acceptance_workflow import (
        load_orchestration,
        run_hermes_workflow,
        validate_hermes_workflow_result,
        validate_orchestration_contract,
    )
from app.core.config import get_settings
from app.core.database import SessionLocal

_load_orchestration = load_orchestration
_overall_status = overall_status
_summary = summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TQuant Agent OS real acceptance checks.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="验收总报告输出路径")
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET), help="qlib 样本 CSV 输出路径")
    parser.add_argument("--orchestration", default=str(DEFAULT_ORCHESTRATION), help="Hermes 编排配置 YAML")
    parser.add_argument("--lookback-days", type=int, default=504, help="qlib 实盘样本回看交易日数量")
    parser.add_argument("--symbols", default="", help="Hermes workflow 标的，逗号分隔；默认取全策略榜前 10")
    parser.add_argument("--limit", type=int, default=10, help="Hermes workflow 标的数量")
    parser.add_argument("--strategy-key", action="append", dest="strategy_keys", help="限制 qlib 报告策略，可重复")
    parser.add_argument("--skip-hermes", action="store_true")
    parser.add_argument("--skip-feishu", action="store_true")
    parser.add_argument("--skip-qlib", action="store_true")
    parser.add_argument("--skip-openbb", action="store_true")
    args = parser.parse_args()

    report = run_acceptance(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"agent_os_acceptance_report={output_path}")
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    orchestration = load_orchestration(Path(args.orchestration))
    with SessionLocal() as db:
        symbols = _symbols_from_args(args.symbols) or load_priority_symbols(db, limit=args.limit)
        steps = _run_steps(args, settings=settings, orchestration=orchestration, symbols=symbols, db=db)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": "TQuant 维斯量化平台",
        "symbols": symbols,
        "steps": [item.to_dict() for item in steps],
        "overall_status": overall_status(steps),
        "notes": [
            "Hermes/飞书/OpenBB 依赖外部配置；缺配置会返回 not_configured，不影响核心 A 股链路。",
            "qlib 报告使用本地实盘物化信号和 daily_bar_snapshots 计算，不调用外部行情源。",
        ],
    }


def _run_steps(
    args: argparse.Namespace,
    *,
    settings: Any,
    orchestration: dict[str, Any],
    symbols: list[str],
    db: Any,
) -> list[StepResult]:
    steps: list[StepResult] = []
    if not args.skip_hermes:
        steps.append(timed("hermes_orchestration_contract", lambda: validate_orchestration_contract(orchestration)))
        steps.append(timed("hermes_workflow", lambda: run_hermes_workflow(settings, symbols, orchestration)))
    if not args.skip_feishu:
        steps.append(timed("feishu_daily_push", lambda: run_feishu_daily_push(db)))
    if not args.skip_qlib:
        steps.append(
            timed(
                "qlib_research_report",
                lambda: run_qlib_report(
                    db,
                    dataset_path=Path(args.dataset_output),
                    lookback_days=args.lookback_days,
                    strategy_keys=args.strategy_keys,
                ),
            )
        )
    if not args.skip_openbb:
        steps.append(timed("openbb_degrade_check", run_openbb_check))
    return steps


def _symbols_from_args(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


if __name__ == "__main__":
    main()
