from __future__ import annotations

from statistics import mean
from typing import Any

import numpy as np

from app.services.rl.position_envs import PositionSample, make_continuous_env, make_discrete_env, sample_obs


def run_position_shadow(samples: list[PositionSample]) -> dict[str, Any]:
    if len(samples) < 30:
        return {
            "algorithm": "ppo_shadow_mode",
            "production_enabled": False,
            "trained": False,
            "summary": "样本不足，PPO/SAC 仅登记为影子研究，不参与自动交易。",
            "sample_count": len(samples),
            "policy": [],
        }
    try:
        return _train_ppo_shadow(samples)
    except Exception as exc:
        return {
            "algorithm": "ppo_shadow_mode",
            "production_enabled": False,
            "trained": False,
            "summary": f"PPO shadow 训练失败，已降级统计策略：{str(exc)[:120]}",
            "sample_count": len(samples),
            "policy": _fallback_policy(samples),
        }


def _train_ppo_shadow(samples: list[PositionSample]) -> dict[str, Any]:
    from stable_baselines3 import PPO
    from stable_baselines3 import SAC

    env = make_discrete_env(samples)
    model = PPO("MlpPolicy", env, verbose=0, n_steps=min(64, max(8, len(samples))), batch_size=16)
    model.learn(total_timesteps=min(max(len(samples) * 20, 512), 4096))
    sac_payload = _train_sac_shadow(samples, SAC)
    return {
        "algorithm": "ppo_sac_shadow_mode",
        "production_enabled": False,
        "trained": True,
        "sample_count": len(samples),
        "summary": "PPO/SAC shadow 已离线训练完成，仅用于影子对照和研究，不参与自动交易。",
        "policy": _policy_from_model(model, samples),
        "sac_policy": sac_payload.get("policy", []),
        "sac_trained": bool(sac_payload.get("trained")),
        "sac_warning": str(sac_payload.get("warning") or ""),
    }


def _train_sac_shadow(samples: list[PositionSample], sac_cls: Any) -> dict[str, Any]:
    try:
        env = make_continuous_env(samples)
        model = sac_cls("MlpPolicy", env, verbose=0, buffer_size=2048, batch_size=16, learning_starts=16)
        model.learn(total_timesteps=min(max(len(samples) * 20, 512), 2048))
        return {"trained": True, "policy": _policy_from_sac_model(model, samples)}
    except Exception as exc:
        return {"trained": False, "policy": [], "warning": str(exc)[:120]}


def _policy_from_model(model: Any, samples: list[PositionSample]) -> list[dict[str, Any]]:
    buckets: dict[str, list[PositionSample]] = {}
    for row in samples:
        buckets.setdefault(f"{row.market_state}|{row.signal_state}", []).append(row)
    result: list[dict[str, Any]] = []
    for state, rows in sorted(buckets.items()):
        obs = sample_obs(rows[-1], max(int(len(rows) / 2), 0), len(rows))
        action, _ = model.predict(obs, deterministic=True)
        result.append(_row(state, rows, [0, 5, 10, 20][int(action)]))
    return result[:20]


def _policy_from_sac_model(model: Any, samples: list[PositionSample]) -> list[dict[str, Any]]:
    buckets: dict[str, list[PositionSample]] = {}
    for row in samples:
        buckets.setdefault(f"{row.market_state}|{row.signal_state}", []).append(row)
    result: list[dict[str, Any]] = []
    for state, rows in sorted(buckets.items()):
        action, _ = model.predict(sample_obs(rows[-1], max(int(len(rows) / 2), 0), len(rows)), deterministic=True)
        position_pct = round(float(np.asarray(action).reshape(-1)[0]) * 100)
        result.append(_row(state, rows, max(0, min(position_pct, 20))))
    return result[:20]


def _fallback_policy(samples: list[PositionSample]) -> list[dict[str, Any]]:
    buckets: dict[str, list[PositionSample]] = {}
    for row in samples:
        buckets.setdefault(f"{row.market_state}|{row.signal_state}", []).append(row)
    return [_row(state, rows, 0) for state, rows in sorted(buckets.items())][:20]


def _row(state: str, rows: list[PositionSample], position_pct: int) -> dict[str, Any]:
    values = [row.pnl_pct for row in rows]
    return {
        "state": state,
        "sample_count": len(values),
        "avg_return_pct": round(mean(values), 4),
        "win_rate_pct": round(sum(1 for value in values if value > 0) / max(len(values), 1) * 100, 2),
        "suggested_position_pct": position_pct,
    }
