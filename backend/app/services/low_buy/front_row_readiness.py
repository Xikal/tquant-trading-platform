from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.low_buy.strategy_lanes import (
    BASELINE_VARIANT,
    FRONT_ROW_ONLY_VARIANT,
    FRONT_ROW_WEIGHTED_VARIANT,
    normalize_strategy_variant,
    plain_status_for_lane,
)


READINESS_REPORT_PATTERN = "front-row-weighted-production-readiness-*.json"


def front_row_readiness_summary(strategy_variant: str | None) -> dict[str, Any]:
    variant = normalize_strategy_variant(strategy_variant)
    if variant == BASELINE_VARIANT:
        return {
            "status": "production_baseline",
            "recommend_small_traffic_observation": False,
            "plain_status": plain_status_for_lane(variant),
            "blockers": [],
            "blocker_texts": [],
        }
    if variant == FRONT_ROW_ONLY_VARIANT:
        blockers = ["front_row_only_not_production_filter", "low_frequency_long_no_signal_risk"]
        return {
            "status": "elite_watch_only",
            "recommend_small_traffic_observation": False,
            "plain_status": plain_status_for_lane(variant),
            "blockers": blockers,
            "blocker_texts": [plain_blocker_text(item) for item in blockers],
        }

    report = _load_latest_readiness_report()
    if not report:
        blockers = ["front_row_readiness_report_missing"]
        return {
            "status": "readiness_unknown",
            "recommend_small_traffic_observation": False,
            "plain_status": {
                "conclusion": "暂不建议小流量观察",
                "reason": "验证报告缺失，不能默认通过",
                "next_step": "先补齐 readiness 报告再判断",
            },
            "blockers": blockers,
            "blocker_texts": [plain_blocker_text(item) for item in blockers],
        }

    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    blockers = [str(item) for item in decision.get("blockers", []) if str(item)]
    return {
        "status": str(decision.get("status") or "shadow_paper_extend_oos"),
        "recommend_small_traffic_observation": bool(decision.get("recommend_small_traffic_observation")),
        "plain_status": {
            "conclusion": "暂不建议小流量观察",
            "reason": _plain_reason_from_blockers(blockers),
            "next_step": "继续影子验证和观察验证",
        },
        "blockers": blockers,
        "blocker_texts": [plain_blocker_text(item) for item in blockers],
        "source_report": str(_latest_report_path() or ""),
    }


def plain_blocker_text(blocker: str) -> str:
    mapping = {
        "oos_window_below_60_trade_days": "样本外验证还不够 60 个交易日，暂未通过",
        "oos_filled_count_below_150": "样本外成交样本不足，暂未通过",
        "formal_oos_start_unavailable": "冻结日期之后还没有足够新交易日，不能伪造通过",
        "walk_forward_pass_rate_below_70pct": "滚动验证通过率不足，表现还不稳定",
        "walk_forward_two_consecutive_failed_windows": "滚动验证出现连续失败窗口，暂未通过",
        "walk_forward_window_count_below_6": "滚动验证窗口数量不足，暂未通过",
        "minute_coverage_below_95pct": "分钟行情覆盖不足，暂无法确认能否按计划买到",
        "tradability_fill_retention_below_70pct": "可成交回放留存不足，暂未通过",
        "tick_data_insufficient_for_real_money_production": "逐笔成交数据不足，暂不能用于真实交易判断",
        "weak_market_sample_insufficient_keep_watch_only": "弱市压缩后样本仍不足，只能继续观察",
        "front_row_only_not_production_filter": "前排极精选只做提醒，不作为生产硬过滤",
        "low_frequency_long_no_signal_risk": "信号很少，可能连续多天没有票",
        "front_row_readiness_report_missing": "验证报告缺失，不能默认显示通过",
    }
    return mapping.get(blocker, blocker.replace("_", " "))


def _plain_reason_from_blockers(blockers: list[str]) -> str:
    if not blockers:
        return "仍需人工审批，不能自动替换生产排序"
    texts = [plain_blocker_text(item) for item in blockers[:3]]
    return "；".join(texts)


def _load_latest_readiness_report() -> dict[str, Any] | None:
    path = _latest_report_path()
    if not path:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _latest_report_path() -> Path | None:
    report_dir = Path(__file__).resolve().parents[4] / "docs" / "reports"
    paths = sorted(report_dir.glob(READINESS_REPORT_PATTERN))
    return paths[-1] if paths else None
