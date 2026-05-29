from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "main_force_model_backtest.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("main_force_model_backtest", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_research_proxy_oos_cannot_promote_without_true_walk_forward_split():
    module = _load_module()
    args = argparse.Namespace(
        start="2024-05-28",
        end="2026-05-28",
        train_months=12,
        valid_months=3,
        test_months=3,
        purged_gap_days=10,
    )
    records = [
        {
            "action": "buy_confirmed",
            "return_20d_pct": 12.0,
            "success": True,
            "fallback": False,
            "temporal_guard_pass": True,
            "max_adverse_20d_pct": -2.0,
            "stage": "markup",
            "strategy_key": "main_force_research",
            "sector_name": "测试行业",
            "market_state": "unknown",
            "score": 70,
        },
        {
            "action": "buy_probe",
            "return_20d_pct": 8.0,
            "success": True,
            "fallback": False,
            "temporal_guard_pass": True,
            "max_adverse_20d_pct": -1.0,
            "stage": "washout",
            "strategy_key": "main_force_research",
            "sector_name": "测试行业",
            "market_state": "unknown",
            "score": 66,
        },
    ]
    shadow_gate = {
        "record_count": 300,
        "settled_count": 120,
        "success_rate_pct": 60.0,
        "profit_factor": 2.0,
        "fallback_rate_pct": 0.0,
        "promotion_ready": True,
        "promotion_blockers": [],
    }

    report = module._build_report(records, args, shadow_gate=shadow_gate)

    assert report["oos_promotion_ready"] is False
    assert "true_walk_forward_train_valid_test_not_implemented" in report["oos_promotion_blockers"]
    assert report["promotion_ready"] is False
    assert "true_walk_forward_train_valid_test_not_implemented" in report["promotion_blockers"]
    assert report["walk_forward"]["production_eligible"] is False
    assert report["walk_forward"]["evidence_status"] == "research_proxy_not_true_train_valid_test_split"

    markdown = module._render_markdown(report, args)

    assert "当前结论：不可晋级" in markdown
    assert "证据状态：research_proxy_not_true_train_valid_test_split" in markdown
    assert "OOS 晋级：阻断" in markdown
    assert "true_walk_forward_train_valid_test_not_implemented" in markdown
    assert "注意：当前收益是未来标签研究指标，不是可成交账户收益。" in markdown
