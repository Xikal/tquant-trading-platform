"""Model review assembly for the 24-month strategy optimization report."""

from __future__ import annotations

from typing import Any


def model_reviews(sources: dict[str, Any]) -> dict[str, Any]:
    main_force = sources["main_force"]
    closed_loop = sources["closed_loop"]
    exit_model = closed_loop.get("auxiliary_model_shadow", {})
    execution_matrix = sources.get("execution_matrix", {})
    exit_walk_forward = sources.get("exit_walk_forward", {})
    return {
        "main_force_model": {
            "model_key": main_force.get("model_key"),
            "oos_metrics": _main_force_oos_metrics(main_force),
            "walk_forward": main_force.get("walk_forward"),
            "oos_promotion_ready": main_force.get("oos_promotion_ready"),
            "oos_promotion_blockers": main_force.get("oos_promotion_blockers") or [],
            "oos_evidence_status": "research_proxy_not_true_train_valid_test_split",
            "oos_evidence_caveat": (
                "main_force_model_backtest.py 目前按全窗口生成启发式标签表现；"
                "train/valid/test/purged_gap 参数写入报告，但未形成真实滚动训练验证测试切窗。"
            ),
            "shadow_gate": main_force.get("shadow_gate"),
            "parameter_stability": main_force.get("parameter_stability"),
            "temporal_guard": main_force.get("temporal_guard"),
            "production_conclusion": (
                "离线 OOS 字段只能当研究代理指标；线上 Shadow settled 样本为 0，"
                "且未完成真实滚动训练/验证/测试切窗，不得直接作为生产下单模型或强制调参依据。"
            ),
        },
        "exit_model": {
            "model_key": exit_model.get("model_key"),
            "status": exit_model.get("status"),
            "record_count": exit_model.get("record_count"),
            "settled_count": exit_model.get("settled_count"),
            "shadow_only": exit_model.get("shadow_only"),
            "hard_stop_override_allowed": exit_model.get("hard_stop_override_allowed"),
            "promotion_ready": exit_model.get("promotion_ready"),
            "blockers": exit_model.get("blockers"),
            "execution_matrix_shadow_evidence": execution_matrix,
            "walk_forward_summary": exit_walk_forward,
            "walk_forward_shadow_summary": _walk_forward_shadow_summary(exit_walk_forward),
            "production_conclusion": _exit_model_conclusion(exit_walk_forward),
        },
        "next_day_event_model": {
            "status": "no_standalone_24m_model_readiness_artifact",
            "production_conclusion": (
                "当前证据只覆盖相关规则策略和事件型信号表现；没有独立模型的"
                "walk-forward、Shadow、漂移报告，不建议接入生产模型链路。"
            ),
        },
    }


def _main_force_oos_metrics(main_force: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_count": main_force.get("record_count"),
        "eligible_count": main_force.get("eligible_count"),
        "success_rate_pct": main_force.get("success_rate_pct"),
        "profit_factor": main_force.get("profit_factor"),
        "avg_return_20d_pct": main_force.get("avg_return_20d_pct"),
        "avg_max_adverse_20d_pct": main_force.get("avg_max_adverse_20d_pct"),
        "fallback_rate_pct": main_force.get("fallback_rate_pct"),
    }


def _walk_forward_shadow_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {
            "status": "missing",
            "shadow_candidate": False,
            "production_eligible": False,
            "reason": "未找到止盈止损辅助模型 walk-forward 实算摘要。",
        }
    return {
        "status": "shadow_candidate" if summary.get("shadow_candidate") else "not_ready",
        "variant_under_test": summary.get("variant_under_test"),
        "baseline_variant": summary.get("baseline_variant"),
        "window_count": summary.get("window_count"),
        "passed_window_count": summary.get("passed_window_count"),
        "pass_rate_pct": summary.get("pass_rate_pct"),
        "aggregate_delta": summary.get("aggregate_delta"),
        "shadow_candidate": bool(summary.get("shadow_candidate")),
        "production_eligible": False,
        "hard_stop_override_allowed": False,
        "promotion_blockers": summary.get("promotion_blockers") or [
            "online_shadow_settled_sample_lt_required",
        ],
    }


def _exit_model_conclusion(summary: dict[str, Any]) -> str:
    if summary.get("shadow_candidate"):
        return (
            "quick_tp3_trailing1 已通过 7 个 OOS 窗口相对基线验证，可进入下一阶段 Shadow；"
            "但线上 settled 样本不足，仍不能写生产，且不能取消、放宽或覆盖硬止损。"
        )
    return "只能继续 Shadow；不能取消、放宽或覆盖硬止损。"
