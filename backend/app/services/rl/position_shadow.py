from __future__ import annotations

import os
from statistics import mean
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.services.rl.position_envs import PositionSample, make_continuous_env, make_discrete_env, sample_obs

_DEFAULT_PPO_TIMESTEP_CAP = 4096
_DEEP_RL_TIMESTEP_CAP = 50_000
_DEFAULT_SAC_TIMESTEP_CAP = 2048


def run_position_shadow(samples: list[PositionSample]) -> dict[str, Any]:
    if len(samples) < 30:
        return {
            "algorithm": "ppo_shadow_mode",
            "production_enabled": False,
            "trained": False,
            "convergence_status": "not_trained_sample_insufficient",
            "convergence_warning": "样本不足，未执行 PPO/SAC 训练。",
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
            "convergence_status": "training_failed",
            "convergence_warning": "PPO/SAC 训练失败，已降级为统计策略，不应解读为强化学习结论。",
            "summary": f"PPO shadow 训练失败，已降级统计策略：{str(exc)[:120]}",
            "sample_count": len(samples),
            "policy": _fallback_policy(samples),
        }


def _train_ppo_shadow(samples: list[PositionSample]) -> dict[str, Any]:
    from stable_baselines3 import PPO
    from stable_baselines3 import SAC

    ppo_timesteps = _ppo_timesteps(len(samples))
    env = make_discrete_env(samples)
    model = PPO("MlpPolicy", env, verbose=0, n_steps=min(64, max(8, len(samples))), batch_size=16)
    model.learn(total_timesteps=ppo_timesteps)
    sac_payload = _train_sac_shadow(samples, SAC)
    return {
        "algorithm": "ppo_sac_shadow_mode",
        "production_enabled": False,
        "trained": True,
        "sample_count": len(samples),
        "ppo_total_timesteps": ppo_timesteps,
        "deep_rl_training_enabled": _deep_rl_training_enabled(),
        "convergence_status": _convergence_status(ppo_timesteps),
        "convergence_warning": _convergence_warning(ppo_timesteps),
        "summary": "PPO/SAC shadow 已离线训练完成，仅用于影子对照和研究，不参与自动交易。",
        "policy": _policy_from_model(model, samples),
        "sac_policy": sac_payload.get("policy", []),
        "sac_trained": bool(sac_payload.get("trained")),
        "sac_total_timesteps": int(sac_payload.get("total_timesteps") or 0),
        "sac_warning": str(sac_payload.get("warning") or ""),
    }


def _train_sac_shadow(samples: list[PositionSample], sac_cls: Any) -> dict[str, Any]:
    try:
        sac_timesteps = _sac_timesteps(len(samples))
        env = make_continuous_env(samples)
        model = sac_cls("MlpPolicy", env, verbose=0, buffer_size=2048, batch_size=16, learning_starts=16)
        model.learn(total_timesteps=sac_timesteps)
        return {"trained": True, "policy": _policy_from_sac_model(model, samples), "total_timesteps": sac_timesteps}
    except Exception as exc:
        return {"trained": False, "policy": [], "total_timesteps": 0, "warning": str(exc)[:120]}


def _deep_rl_training_enabled() -> bool:
    try:
        settings = get_settings()
        return bool(settings.enable_deep_rl or settings.enable_deep_rl_training)
    except Exception:
        return (os.getenv("ENABLE_DEEP_RL_TRAINING") or "").strip().lower() in {"1", "true", "yes", "on"}


def _ppo_timesteps(sample_count: int) -> int:
    base = max(sample_count * 20, 512)
    if _deep_rl_training_enabled():
        return max(base, _DEEP_RL_TIMESTEP_CAP)
    return min(base, _DEFAULT_PPO_TIMESTEP_CAP)


def _sac_timesteps(sample_count: int) -> int:
    base = max(sample_count * 20, 512)
    if _deep_rl_training_enabled():
        return max(base, int(_DEEP_RL_TIMESTEP_CAP / 2))
    return min(base, _DEFAULT_SAC_TIMESTEP_CAP)


def _convergence_warning(total_timesteps: int) -> str:
    if total_timesteps >= _DEEP_RL_TIMESTEP_CAP:
        return ""
    return (
        f"训练步数 {total_timesteps} 不足以保证 PPO 策略收敛，结果仅供早期探索参考；"
        "如需离线深度训练，请在独立研究环境设置 ENABLE_DEEP_RL_TRAINING=true。"
    )


def _convergence_status(total_timesteps: int) -> str:
    if total_timesteps >= _DEEP_RL_TIMESTEP_CAP:
        return "sufficient_steps"
    return "insufficient_steps"


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
