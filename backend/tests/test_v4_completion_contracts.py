from __future__ import annotations

from types import SimpleNamespace

from app.core.role_permissions import has_permission
from app.services.rl_position_research import _position_from_edge
from app.services.strategy_portfolio_optimizer import _normalize


def test_rbac_paper_trade_permission_uses_whitelist() -> None:
    user = SimpleNamespace(is_admin=False, roles="", is_active=True, can_paper_trade=True)
    blocked = SimpleNamespace(is_admin=False, roles="", is_active=True, can_paper_trade=False)

    assert has_permission(user, "paper_trade") is True
    assert has_permission(blocked, "paper_trade") is False


def test_portfolio_optimizer_weights_sum_to_one() -> None:
    weights = _normalize({"first_board": 2.0, "volume_shrink": 1.0})

    assert round(sum(weights.values()), 6) == 1.0
    assert weights["first_board"] > weights["volume_shrink"]


def test_rl_research_does_not_allocate_low_sample_states() -> None:
    assert _position_from_edge(avg=2.0, win_rate=0.8, sample_count=10) == 0
    assert _position_from_edge(avg=1.2, win_rate=0.65, sample_count=50) == 15
