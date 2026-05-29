"""Extract Shadow-only evidence from existing low-buy execution matrices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MATRIX_PATHS = (
    Path("backend/data/reports/execution_matrix_full/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json"),
    Path("backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json"),
)

PARAMETER_HINTS = {
    "fixed_stop_m2p5": {"stop_loss_pct": -2.5},
    "atr_stop_1p0": {"atr_stop_multiplier": 1.0},
    "force_t1_close": {"first_take_profit_pct": 8.0, "force_t1_exit": True},
    "force_t2_close": {"first_take_profit_pct": 8.0, "force_t2_exit": True},
    "quick_tp3_trailing1": {"first_take_profit_pct": 3.0, "trailing_stop_pct": 1.0, "max_holding_days": 3},
}


def load_execution_matrix_evidence(root: Path) -> dict[str, Any]:
    source_path = next((root / rel for rel in MATRIX_PATHS if (root / rel).exists()), None)
    if source_path is None:
        return {"status": "missing", "production_eligible": False, "shadow_only": True, "reason": "未找到低吸执行参数矩阵 JSON。"}
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    rows = [_normalize_row(row) for row in payload.get("rows", []) or []]
    coverage_pct = min((float(row.get("coverage_pct") or 0.0) for row in rows), default=0.0)
    baseline = next((row for row in rows if row.get("variant_key") == "default_exit"), None)
    rows = [_with_baseline_delta(row, baseline) for row in rows]
    best_pf = _best(rows, "profit_factor")
    return {
        "status": "partial_window_research_only" if coverage_pct < 90.0 else "research_only",
        "source_path": str(source_path),
        "scope": payload.get("scope", {}),
        "warning": payload.get("warning"),
        "coverage_pct": coverage_pct,
        "production_eligible": False,
        "shadow_only": True,
        "promotion_blockers": [
            "execution_matrix_coverage_below_90pct",
            "not_recomputed_with_full_24m_walk_forward",
            "not_validated_with_purged_gap",
            "not_settled_in_online_shadow",
        ],
        "baseline": baseline,
        "best_by_profit_factor": best_pf,
        "best_by_drawdown": _best(rows, "max_drawdown_pct"),
        "rows": rows,
        "conclusion": _conclusion(best_pf, coverage_pct),
    }


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    key = str(row.get("variant_key") or "")
    fields = [
        "variant_key", "title", "purpose", "execution_model", "evaluation_start", "evaluation_end",
        "coverage_pct", "coverage_status", "evaluated_count", "filled_count", "net_win_rate",
        "avg_net_return_pct", "stop_loss_rate", "execution_profit_factor", "total_return_pct",
        "annualized_return_pct", "max_drawdown_pct", "sharpe_ratio", "profit_loss_ratio",
        "profit_factor", "avg_holding_days", "drawdown_recovery_status", "filled_exit_reason_counts",
    ]
    normalized = {field: row.get(field) for field in fields}
    normalized["candidate_parameter_changes"] = PARAMETER_HINTS.get(key, {})
    normalized["production_parameter_change_allowed"] = False
    normalized["recommended_stage"] = "shadow_only_partial_window"
    return normalized


def _with_baseline_delta(row: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline or row.get("variant_key") == "default_exit":
        return row
    row = dict(row)
    row["delta_vs_default"] = {
        "profit_factor": _round(_float(row.get("profit_factor")) - _float(baseline.get("profit_factor"))),
        "avg_net_return_pct": _round(_float(row.get("avg_net_return_pct")) - _float(baseline.get("avg_net_return_pct"))),
        "max_drawdown_pct": _round(_float(row.get("max_drawdown_pct")) - _float(baseline.get("max_drawdown_pct"))),
        "stop_loss_rate": _round(_float(row.get("stop_loss_rate")) - _float(baseline.get("stop_loss_rate"))),
    }
    return row


def _best(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get("variant_key") != "default_exit"]
    return max(candidates, key=lambda row: _float(row.get(field))) if candidates else None


def _conclusion(best_pf: dict[str, Any] | None, coverage_pct: float) -> str:
    if not best_pf:
        return "没有可比较的执行参数候选。"
    return f"{best_pf.get('variant_key')} 在现有短窗矩阵中表现最好，但覆盖率仅 {coverage_pct:.2f}%，只能进入 Shadow/完整 walk-forward 复验，不能写生产。"


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _round(value: float) -> float:
    return round(value, 4)
