from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    PaperAccount,
    PaperDailyReport,
    PaperMarketPerfDaily,
    PaperReviewReport,
    PaperStrategyPerfDaily,
)
from app.core.timezone import beijing_now, beijing_today
from app.services.ai_service import AiService
from app.services.paper.performance import PaperPerformanceService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class PaperArchiveService:
    """收盘后归档模拟盘绩效，用于趋势看板和日报回看。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.performance = PaperPerformanceService(db)

    def archive_all(
        self,
        account_id: int,
        *,
        target_date: date | None = None,
        include_report: bool = True,
    ) -> dict[str, Any]:
        archive_date = target_date or beijing_today()
        account = self.db.get(PaperAccount, account_id)
        if account is None:
            raise LookupError("模拟账户不存在")

        self.performance.create_daily_snapshot(account_id, target_date=archive_date)
        strategy_count = self._archive_strategy_perf(account_id, archive_date)
        market_count = self._archive_market_perf(account_id, archive_date)
        report = self.generate_daily_report(account_id, target_date=archive_date) if include_report else None
        self.db.commit()
        return {
            "account_id": account_id,
            "date": archive_date.isoformat(),
            "strategies_saved": strategy_count,
            "market_states_saved": market_count,
            "report_saved": report is not None,
            "close_review_saved": False,
            "review_scope": "market",
        }

    def archive_all_active(self, *, include_report: bool = True) -> list[dict[str, Any]]:
        accounts = self.db.execute(
            select(PaperAccount).where(PaperAccount.status.in_(["active", "paused"]))
        ).scalars().all()
        results: list[dict[str, Any]] = []
        for account in accounts:
            try:
                results.append(self.archive_all(account.id, include_report=include_report))
            except Exception as exc:
                logger.exception("模拟盘绩效归档失败: account_id=%s", account.id)
                results.append({"account_id": account.id, "error": "归档失败"})
        return results

    def generate_daily_report(
        self,
        account_id: int,
        *,
        target_date: date | None = None,
    ) -> PaperDailyReport:
        report_date = target_date or beijing_today()
        metrics = self._metrics_snapshot(account_id, target_date=report_date)
        summary, highlights, alerts, suggestion, model = self._build_rule_report(metrics)

        settings = SettingsService(self.db).get_payload().model_dump()
        if metrics["overall"].get("total_trades", 0) and settings.get("llm_api_key") and settings.get("llm_model"):
            summary, highlights, alerts, suggestion, model = self._build_ai_report(settings, metrics)

        report = self._find_report(account_id, report_date)
        if report is None:
            report = PaperDailyReport(account_id=account_id, report_date=report_date)
            self.db.add(report)
        report.overall_summary = summary
        report.strategy_highlights = _json_dumps(highlights)
        report.risk_alerts = _json_dumps(alerts)
        report.suggestion = suggestion
        report.raw_metrics_snapshot = _json_dumps(metrics)
        report.generated_at = beijing_now().replace(tzinfo=None)
        report.llm_model = model
        self.db.flush()
        return report

    def generate_review_report(
        self,
        account_id: int,
        *,
        report_slot: str,
        target_date: date | None = None,
    ) -> PaperReviewReport:
        slot = _normalize_report_slot(report_slot)
        report_date = target_date or beijing_today()
        metrics = self._metrics_snapshot(account_id, target_date=report_date)
        summary, highlights, alerts, suggestion, model = self._build_rule_report(metrics)
        summary, suggestion, alerts = _slot_guidance(slot, summary, suggestion, alerts, metrics)

        report = self._find_review_report(account_id, report_date, slot)
        if report is None:
            report = PaperReviewReport(account_id=account_id, report_date=report_date, report_slot=slot)
            self.db.add(report)
        report.overall_summary = summary
        report.strategy_highlights = _json_dumps(highlights)
        report.risk_alerts = _json_dumps(alerts)
        report.suggestion = suggestion
        report.raw_metrics_snapshot = _json_dumps({**metrics, "report_slot": slot})
        report.generated_at = beijing_now().replace(tzinfo=None)
        report.llm_model = model
        self.db.flush()
        return report

    def generate_review_reports_for_active(
        self,
        *,
        report_slot: str,
        target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        slot = _normalize_report_slot(report_slot)
        report_date = target_date or beijing_today()
        accounts = self.db.execute(
            select(PaperAccount).where(PaperAccount.status.in_(["active", "paused"]))
        ).scalars().all()
        results: list[dict[str, Any]] = []
        for account in accounts:
            try:
                report = self.generate_review_report(account.id, report_slot=slot, target_date=report_date)
                results.append(
                    {
                        "account_id": account.id,
                        "date": report_date.isoformat(),
                        "report_slot": slot,
                        "report_id": report.id,
                        "report_saved": True,
                    }
                )
            except Exception:
                logger.exception("模拟盘复盘报告生成失败: account_id=%s slot=%s", account.id, slot)
                results.append({"account_id": account.id, "report_slot": slot, "error": "复盘报告生成失败"})
        self.db.commit()
        return results

    def _archive_strategy_perf(self, account_id: int, snapshot_date: date) -> int:
        rows = self.performance.compute_by_strategy(account_id, target_date=snapshot_date)
        for item in rows:
            row = self._find_strategy_row(account_id, snapshot_date, item["key"])
            if row is None:
                row = PaperStrategyPerfDaily(
                    account_id=account_id,
                    snapshot_date=snapshot_date,
                    strategy_key=item["key"],
                )
                self.db.add(row)
            _apply_strategy_stats(row, item)
        return len(rows)

    def _archive_market_perf(self, account_id: int, snapshot_date: date) -> int:
        rows = self.performance.compute_by_market_state(account_id, target_date=snapshot_date)
        for item in rows:
            row = self._find_market_row(account_id, snapshot_date, item["key"])
            if row is None:
                row = PaperMarketPerfDaily(
                    account_id=account_id,
                    snapshot_date=snapshot_date,
                    market_state=item["key"],
                )
                self.db.add(row)
            _apply_market_stats(row, item)
        return len(rows)

    def _metrics_snapshot(self, account_id: int, *, target_date: date | None = None) -> dict[str, Any]:
        return {
            "overall": self.performance.compute_overall(account_id, target_date=target_date),
            "strategies": self.performance.compute_by_strategy(account_id, target_date=target_date),
            "markets": self.performance.compute_by_market_state(account_id, target_date=target_date),
        }

    def _build_ai_report(
        self,
        settings: dict[str, Any],
        metrics: dict[str, Any],
    ) -> tuple[str, list[dict[str, str]], list[dict[str, str]], str, str]:
        insight = AiService().build_task_insight(
            settings=settings,
            payload={"metrics": metrics, "instructions": "生成模拟盘每日战绩总结，不给收益承诺。"},
            system_prompt=(
                "你是A股模拟盘绩效分析助手。只基于输入数据做复盘，禁止承诺收益。"
                "请严格返回 JSON，字段为 overall_summary, strategy_highlights, risk_alerts, suggestion。"
                "strategy_highlights 是数组，每项包含 strategy, comment, trend；"
                "risk_alerts 是数组，每项包含 level, content。"
            ),
            include_ai=True,
            max_tokens=1200,
        )
        raw = insight.raw if isinstance(insight.raw, dict) else {}
        summary = str(raw.get("overall_summary") or insight.summary or "AI 已生成模拟盘复盘。")
        highlights = _safe_list(raw.get("strategy_highlights"))
        alerts = _safe_list(raw.get("risk_alerts"))
        suggestion = str(raw.get("suggestion") or (insight.suggestions[0] if insight.suggestions else "继续按规则记录，避免扩大试错仓位。"))
        model = str(settings.get("llm_model") or "llm")
        return summary, highlights, alerts, suggestion, model

    def _build_rule_report(
        self,
        metrics: dict[str, Any],
    ) -> tuple[str, list[dict[str, str]], list[dict[str, str]], str, str]:
        overall = metrics["overall"]
        total_trades = int(overall.get("total_trades") or 0)
        total_return = float(overall.get("total_return_pct") or 0.0)
        net_win = float(overall.get("net_win_rate_pct") or 0.0)
        summary = (
            f"模拟盘累计成交 {total_trades} 笔，总收益率 {total_return:.2f}%，"
            f"净胜率 {net_win:.2f}%。"
        )
        highlights = _strategy_highlights(metrics.get("strategies", []))
        alerts = _risk_alerts(overall, metrics.get("markets", []))
        suggestion = _rule_suggestion(total_trades, net_win, total_return)
        return summary, highlights, alerts, suggestion, "rule"

    def _find_strategy_row(
        self,
        account_id: int,
        snapshot_date: date,
        strategy_key: str,
    ) -> PaperStrategyPerfDaily | None:
        return self.db.execute(
            select(PaperStrategyPerfDaily).where(
                PaperStrategyPerfDaily.account_id == account_id,
                PaperStrategyPerfDaily.snapshot_date == snapshot_date,
                PaperStrategyPerfDaily.strategy_key == strategy_key,
            )
        ).scalar_one_or_none()

    def _find_market_row(
        self,
        account_id: int,
        snapshot_date: date,
        market_state: str,
    ) -> PaperMarketPerfDaily | None:
        return self.db.execute(
            select(PaperMarketPerfDaily).where(
                PaperMarketPerfDaily.account_id == account_id,
                PaperMarketPerfDaily.snapshot_date == snapshot_date,
                PaperMarketPerfDaily.market_state == market_state,
            )
        ).scalar_one_or_none()

    def _find_report(self, account_id: int, report_date: date) -> PaperDailyReport | None:
        return self.db.execute(
            select(PaperDailyReport).where(
                PaperDailyReport.account_id == account_id,
                PaperDailyReport.report_date == report_date,
            )
        ).scalar_one_or_none()

    def _find_review_report(self, account_id: int, report_date: date, report_slot: str) -> PaperReviewReport | None:
        return self.db.execute(
            select(PaperReviewReport).where(
                PaperReviewReport.account_id == account_id,
                PaperReviewReport.report_date == report_date,
                PaperReviewReport.report_slot == report_slot,
            )
        ).scalar_one_or_none()


def _apply_strategy_stats(row: PaperStrategyPerfDaily, item: dict[str, Any]) -> None:
    trades = int(item.get("trades") or 0)
    win_count = max(0, round(trades * float(item.get("win_rate_pct") or 0.0) / 100))
    row.trade_count = trades
    row.win_count = win_count
    row.loss_count = max(0, trades - win_count)
    row.win_rate_pct = float(item.get("win_rate_pct") or 0.0)
    row.net_win_rate_pct = float(item.get("net_win_rate_pct") or 0.0)
    row.avg_return_pct = float(item.get("avg_return_pct") or 0.0)
    row.total_pnl = float(item.get("total_pnl") or 0.0)
    row.profit_factor = item.get("profit_factor")
    row.avg_hold_hours = float(item.get("avg_hold_hours") or 0.0)


def _apply_market_stats(row: PaperMarketPerfDaily, item: dict[str, Any]) -> None:
    row.trade_count = int(item.get("trades") or 0)
    row.win_rate_pct = float(item.get("win_rate_pct") or 0.0)
    row.net_win_rate_pct = float(item.get("net_win_rate_pct") or 0.0)
    row.avg_return_pct = float(item.get("avg_return_pct") or 0.0)
    row.profit_factor = item.get("profit_factor")


def _strategy_highlights(strategies: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in sorted(strategies, key=lambda row: float(row.get("avg_return_pct") or 0.0), reverse=True)[:4]:
        avg_return = float(item.get("avg_return_pct") or 0.0)
        result.append(
            {
                "strategy": str(item.get("key") or "未分类"),
                "comment": f"成交 {int(item.get('trades') or 0)} 笔，平均收益 {avg_return:.2f}%。",
                "trend": "improving" if avg_return > 0 else "declining" if avg_return < 0 else "stable",
            }
        )
    return result


def _risk_alerts(overall: dict[str, Any], markets: list[dict[str, Any]]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if float(overall.get("max_drawdown_pct") or 0.0) < -5:
        alerts.append({"level": "warning", "content": "最大回撤偏大，建议降低单笔试错仓位。"})
    weak_markets = [
        str(item.get("key") or "未分类")
        for item in markets
        if float(item.get("avg_return_pct") or 0.0) < 0
    ][:3]
    if weak_markets:
        alerts.append({"level": "info", "content": f"{'、'.join(weak_markets)} 环境下表现偏弱，先减少主动交易。"})
    return alerts


def _rule_suggestion(total_trades: int, net_win: float, total_return: float) -> str:
    if total_trades == 0:
        return "今日没有可复盘成交，继续等待明确规则信号。"
    if net_win < 0 or total_return < 0:
        return "先缩小仓位，重点复盘亏损样本是否违反市场环境、板块强度或止损规则。"
    return "维持当前规则执行，优先扩大样本记录，不因单日结果临时放宽买点。"


def _normalize_report_slot(value: str) -> str:
    slot = str(value or "").strip().lower()
    if slot not in {"midday", "close"}:
        raise ValueError("复盘报告类型必须是 midday 或 close")
    return slot


def _slot_guidance(
    slot: str,
    summary: str,
    suggestion: str,
    alerts: list[dict[str, str]],
    metrics: dict[str, Any],
) -> tuple[str, str, list[dict[str, str]]]:
    overall = metrics.get("overall", {})
    total_return = float(overall.get("total_return_pct") or 0.0)
    if slot == "midday":
        prefix = "午盘复盘："
        if total_return < 0:
            guidance = "下午优先降频和确认止损，不加码修复亏损样本。"
        else:
            guidance = "下午只延续已验证方向，新增交易必须等待市场强弱和板块承接同步确认。"
        alerts = [
            *alerts,
            {
                "level": "info",
                "content": "午盘报告用于约束下午执行，不作为放宽买点或提高仓位的依据。",
            },
        ]
    else:
        prefix = "收盘复盘："
        guidance = "收盘后只做记录、归因和次日计划，不追认盘中临时交易。"
    return f"{prefix}{summary}", f"{suggestion} {guidance}", alerts


def _safe_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            result.append({str(key): str(val) for key, val in item.items() if val is not None})
    return result


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
