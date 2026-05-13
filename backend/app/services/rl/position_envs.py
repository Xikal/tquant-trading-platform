from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PositionSample:
    market_state: str
    signal_state: str
    pnl_pct: float


def sample_obs(row: PositionSample, index: int, total: int) -> np.ndarray:
    return np.asarray(
        [
            stable_code(row.market_state) / 10.0,
            stable_code(row.signal_state) / 10.0,
            max(min(row.pnl_pct / 10.0, 5.0), -5.0),
            index / max(total, 1),
        ],
        dtype=np.float32,
    )


def stable_code(value: str) -> int:
    digest = hashlib.sha1((value or "").encode("utf-8")).hexdigest()
    return int(digest[:6], 16) % 20


def make_discrete_env(samples: list[PositionSample]):
    import gymnasium as gym
    from gymnasium import spaces

    class DiscretePositionEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self, rows: list[PositionSample]) -> None:
            super().__init__()
            self.rows = rows
            self.index = 0
            self.drawdown = 0.0
            self.action_space = spaces.Discrete(4)
            self.observation_space = spaces.Box(low=-5.0, high=5.0, shape=(4,), dtype=np.float32)

        def reset(self, *, seed: int | None = None, options: dict | None = None):  # type: ignore[override]
            super().reset(seed=seed)
            self.index = 0
            self.drawdown = 0.0
            return self._obs(), {}

        def step(self, action: int):  # type: ignore[override]
            position = [0.0, 0.05, 0.10, 0.20][int(action)]
            return _step(self, position)

        def _obs(self) -> np.ndarray:
            return sample_obs(self.rows[min(self.index, len(self.rows) - 1)], self.index, len(self.rows))

    return DiscretePositionEnv(samples)


def make_continuous_env(samples: list[PositionSample]):
    import gymnasium as gym
    from gymnasium import spaces

    class ContinuousPositionEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self, rows: list[PositionSample]) -> None:
            super().__init__()
            self.rows = rows
            self.index = 0
            self.drawdown = 0.0
            self.action_space = spaces.Box(low=np.asarray([0.0]), high=np.asarray([0.2]), dtype=np.float32)
            self.observation_space = spaces.Box(low=-5.0, high=5.0, shape=(4,), dtype=np.float32)

        def reset(self, *, seed: int | None = None, options: dict | None = None):  # type: ignore[override]
            super().reset(seed=seed)
            self.index = 0
            self.drawdown = 0.0
            return self._obs(), {}

        def step(self, action: Any):  # type: ignore[override]
            position = float(np.asarray(action).reshape(-1)[0])
            return _step(self, max(0.0, min(position, 0.2)))

        def _obs(self) -> np.ndarray:
            return sample_obs(self.rows[min(self.index, len(self.rows) - 1)], self.index, len(self.rows))

    return ContinuousPositionEnv(samples)


def _step(env: Any, position: float):
    row = env.rows[env.index]
    pnl = position * row.pnl_pct / 100.0
    env.drawdown = min(env.drawdown + pnl, 0.0)
    reward = float(pnl - abs(env.drawdown) * 0.08)
    env.index += 1
    terminated = env.index >= len(env.rows)
    return env._obs(), reward, terminated, False, {}
