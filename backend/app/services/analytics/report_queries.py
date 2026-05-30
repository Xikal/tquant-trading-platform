from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.analytics.config import PROJECT_ROOT, analytics_config
from app.services.analytics.duckdb_repository import DuckDBRepository


LEGACY_STRATEGY_REPORT = PROJECT_ROOT / "docs" / "reports" / "strategy-24m-backtest-2026-05-28.json"


def build_strategy_24m_duckdb_report(
    manifest: dict[str, Any],
    *,
    output_root: str | Path | None = None,
    legacy_strategy_report: str | Path | None = None,
) -> dict[str, Any]:
    config = analytics_config(output_root)
    quality = dict(manifest.get("quality") or {})
    files = list(manifest.get("files") or [])
    parquet_glob = str(config.parquet_dir / "daily_bars" / "**" / "*.parquet")
    blocked = quality.get("status") != "ok"
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
    legacy = _load_legacy_report(legacy_strategy_report or LEGACY_STRATEGY_REPORT)
    strategies = [dict(item) for item in legacy.get("all_strategies") or []]
    recommendations = [_strategy_recommendation(item) for item in strategies]
    return {
        "title": "DuckDB 24个月策略分析报告",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "status": "blocked_by_data" if blocked else "ok",
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
        "strategy_summary_source": str(legacy_strategy_report or LEGACY_STRATEGY_REPORT),
        "strategy_summary_note": (
            "当前 Manifest 未通过完整性门禁，策略回测摘要仅保留历史 Python 24个月报告作参考，不作为本次 DuckDB 完整验收。"
            if blocked
            else "策略摘要来自指定 Python 24个月回测结果，DuckDB 本次负责数据 Manifest、Parquet 扫描和报告汇总。"
        ),
        "all_strategies": strategies,
        "strategy_adjustment_recommendations": recommendations,
    }


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
    lines.extend(["", "## 全策略 24个月摘要", "", report.get("strategy_summary_note", ""), ""])
    strategies = report.get("all_strategies") or []
    if strategies:
        lines.extend(
            [
                "| 策略 | 样本 | 成交 | 总收益 | 最大回撤 | PF | 平均单笔 | 建议 |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        recommendations = {item["strategy_key"]: item for item in report.get("strategy_adjustment_recommendations") or []}
        for item in strategies:
            rec = recommendations.get(item.get("strategy_key", ""), {})
            lines.append(
                "| {title} | {sample} | {filled} | {ret:.2f}% | {dd:.2f}% | {pf:.2f} | {avg:.3f}% | {action} |".format(
                    title=item.get("strategy_title") or item.get("strategy_key") or "",
                    sample=int(item.get("sample_count") or 0),
                    filled=int(item.get("filled_count") or 0),
                    ret=float(item.get("total_return_pct") or 0.0),
                    dd=float(item.get("max_drawdown_pct") or 0.0),
                    pf=float(item.get("profit_factor") or 0.0),
                    avg=float(item.get("avg_trade_return_pct") or 0.0),
                    action=rec.get("recommended_action", ""),
                )
            )
    else:
        lines.append("未找到可用策略摘要。")
    lines.extend(["", "## 策略调整建议", ""])
    for item in report.get("strategy_adjustment_recommendations") or []:
        lines.append(
            f"- {item.get('strategy_title') or item.get('strategy_key')}：{item.get('recommended_action_text')}。依据：{item.get('reason')}"
        )
    return "\n".join(lines) + "\n"


def write_strategy_24m_report(report: dict[str, Any], *, output_md: str | Path, output_json: str | Path) -> None:
    md_path = Path(output_md)
    json_path = Path(output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_strategy_24m_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _load_legacy_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _quality_conclusion(quality: dict[str, Any]) -> str:
    if quality.get("status") == "ok":
        return "24个月日线数据完整性通过，可以基于该 Manifest 继续报告。"
    task_id = quality.get("backfill_task_id")
    suffix = f"，已创建 data_backfill_24m 任务 #{task_id}" if task_id else "，需要先创建并完成 data_backfill_24m 任务"
    blockers = "、".join(quality.get("blockers") or ["数据覆盖不足"])
    return f"数据完整性未通过：{blockers}{suffix}；本次不得作为完整24个月回测验收。"


def _strategy_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    filled = int(item.get("filled_count") or 0)
    pf = float(item.get("profit_factor") or 0.0)
    avg = float(item.get("avg_trade_return_pct") or 0.0)
    max_dd = float(item.get("max_drawdown_pct") or 0.0)
    if filled < 100:
        action = "default_off"
        text = "默认关闭"
        reason = "成交样本不足 100，不能稳定评估。"
    elif pf < 0.9 or avg < -0.1:
        action = "delete_candidate"
        text = "删除候选"
        reason = "PF 低于 0.9 或平均单笔为明显负值。"
    elif pf < 1.05 or avg <= 0 or max_dd <= -50:
        action = "default_off"
        text = "默认关闭"
        reason = "收益质量弱或回撤过大，不能默认参与生产。"
    elif pf < 1.25 or max_dd <= -35:
        action = "downweight"
        text = "降权"
        reason = "PF/回撤未达到稳定生产标准，适合保留但降低权重。"
    else:
        action = "keep"
        text = "保留"
        reason = "PF、平均单笔和回撤处于可继续观察区间。"
    return {
        "strategy_key": item.get("strategy_key", ""),
        "strategy_title": item.get("strategy_title", ""),
        "recommended_action": action,
        "recommended_action_text": text,
        "reason": reason,
        "evidence": {
            "filled_count": filled,
            "profit_factor": pf,
            "avg_trade_return_pct": avg,
            "max_drawdown_pct": max_dd,
        },
    }
