from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.services.low_buy.front_row_weighted_validation_config import (
    MIN_FORMAL_OOS_FILLED_COUNT,
    MIN_FORMAL_OOS_TRADE_DAYS,
    VALIDATION_CONFIG_VERSION,
)


@dataclass(frozen=True)
class ManifestValidationResult:
    passed: bool
    blockers: list[str]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


def build_freeze_manifest(
    *,
    freeze_date: str,
    source_report_json: str,
    trade_dates: list[str],
    git_commit: str = "",
    config_version: str = VALIDATION_CONFIG_VERSION,
) -> dict[str, Any]:
    dates = sorted(str(item) for item in trade_dates if str(item or "").strip())
    formal_oos_start = next((item for item in dates if item > freeze_date), "")
    oos_dates = [item for item in dates if formal_oos_start and item >= formal_oos_start]
    status = "collecting_oos"
    blockers: list[str] = []
    if not formal_oos_start:
        status = "awaiting_post_freeze_trade_dates"
        blockers.append("formal_oos_start_unavailable")
    elif len(oos_dates) < MIN_FORMAL_OOS_TRADE_DAYS:
        status = "insufficient_oos_window"
        blockers.append("oos_window_below_60_trade_days")
    return {
        "model_key": "front_row_weighted",
        "scoring_config_version": config_version,
        "freeze_date": freeze_date,
        "freeze_git_commit": git_commit,
        "source_report_json": source_report_json,
        "formal_oos_start": formal_oos_start,
        "formal_oos_end": oos_dates[-1] if oos_dates else "",
        "oos_window_trade_days": len(oos_dates),
        "oos_signal_days": 0,
        "oos_sample_count": 0,
        "oos_filled_count": 0,
        "minimum_oos_trade_days": MIN_FORMAL_OOS_TRADE_DAYS,
        "minimum_oos_filled_count": MIN_FORMAL_OOS_FILLED_COUNT,
        "random_split_allowed": False,
        "production_sort_replaced": False,
        "near_entry_production_score_allowed": False,
        "status": status,
        "blockers": blockers,
        "warnings": [],
    }


def validate_freeze_manifest(manifest: dict[str, Any], *, root_dir: str | Path = ".") -> ManifestValidationResult:
    blockers: list[str] = []
    warnings: list[str] = []
    freeze_date = str(manifest.get("freeze_date") or "")
    formal_oos_start = str(manifest.get("formal_oos_start") or "")
    source_report = str(manifest.get("source_report_json") or "")
    if not manifest.get("scoring_config_version"):
        blockers.append("missing_scoring_config_version")
    if formal_oos_start and freeze_date and formal_oos_start <= freeze_date:
        blockers.append("oos_start_not_after_freeze")
    if bool(manifest.get("random_split_allowed")):
        blockers.append("random_split_forbidden")
    if bool(manifest.get("production_sort_replaced")):
        blockers.append("production_sort_replacement_forbidden")
    if not source_report:
        blockers.append("source_report_missing")
    else:
        report_path = Path(source_report)
        if not report_path.is_absolute():
            report_path = Path(root_dir) / report_path
        if not report_path.exists():
            blockers.append("source_report_missing")
    if not formal_oos_start:
        warnings.append("formal_oos_start_unavailable")
    if int(manifest.get("oos_window_trade_days") or 0) < MIN_FORMAL_OOS_TRADE_DAYS:
        warnings.append("oos_window_below_60_trade_days")
    return ManifestValidationResult(passed=not blockers, blockers=sorted(set(blockers)), warnings=sorted(set(warnings)))


def today_iso() -> str:
    return date.today().isoformat()
