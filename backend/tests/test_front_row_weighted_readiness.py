from __future__ import annotations

from backend.scripts.front_row_weighted_readiness_report import build_readiness_report


def _base():
    return {
        "summary": {"production_sort_replaced": False, "near_entry_production_score_count": 0},
        "decision": {"blockers": [], "warnings": []},
        "anti_future_function_audit": {"future_leak_check": "passed"},
    }


def test_readiness_blocks_oos_below_60_trade_days() -> None:
    report = build_readiness_report(
        base=_base(),
        freeze={"status": "insufficient_oos_window", "oos_window_trade_days": 59, "blockers": ["oos_window_below_60_trade_days"]},
        walk_forward={"overall": {"passed": True}, "blockers": []},
        tradability={"status": "passed", "blockers": []},
        weak_market={"decision": {"status": "weak_market_passed", "blockers": []}},
    )

    assert report["decision"]["status"] == "shadow_paper_extend_oos"
    assert "oos_window_below_60_trade_days" in report["decision"]["blockers"]


def test_readiness_blocks_near_entry_misclassification() -> None:
    base = _base()
    base["summary"]["near_entry_production_score_count"] = 1

    report = build_readiness_report(
        base=base,
        freeze={"blockers": []},
        walk_forward={"overall": {"passed": True}, "blockers": []},
        tradability={"status": "passed", "blockers": []},
        weak_market={"decision": {"status": "weak_market_passed", "blockers": []}},
    )

    assert "near_entry_misclassified_into_production" in report["decision"]["blockers"]
