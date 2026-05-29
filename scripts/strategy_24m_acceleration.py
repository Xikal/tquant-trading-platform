"""Acceleration and profiling summary assembly."""

from __future__ import annotations

from typing import Any


def acceleration_summary(profile: dict[str, Any]) -> dict[str, Any]:
    recommendation = profile.get("go_rust_recommendation") or {}
    return {
        "gpu_used": False,
        "gpu_needed": False,
        "gpu_reason": "本轮为规则策略和既有报告聚合，无深度学习/RL/LLM训练；CPU足够。",
        "go_rust_acceleration_used": False,
        "go_rust_reason": recommendation.get("reason")
        or "本轮用 Python/SQLite 完成24个月全量回测刷新；未新增 Go/Rust 加速路径。",
        "profile_scope": profile.get("profile_scope") or "not_recorded",
        "profile_bottleneck_step": profile.get("bottleneck_step") or "",
        "profile_bottleneck_avg_ms": profile.get("bottleneck_avg_ms") or 0.0,
        "existing_rust_parity": profile.get("existing_rust_parity") or {},
        "candidate_future_go_rust_modules": recommendation.get("candidate_future_modules") or [],
    }
