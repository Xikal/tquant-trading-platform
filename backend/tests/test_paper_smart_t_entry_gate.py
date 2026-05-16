from __future__ import annotations

from app.services.paper.smart_exit_context import PaperExitContext
from app.services.paper.smart_t_entry_gate import evaluate_smart_t_entry_gate


def _context(**overrides) -> PaperExitContext:
    values = {
        "intraday_usable": True,
        "reclaimed_vwap": True,
        "low_rising": True,
        "volume_release_ratio": 0.35,
        "volume_usable": True,
        "vwap": 10.0,
        "reason": "缩量回踩后重新站回分时均价线。",
    }
    values.update(overrides)
    return PaperExitContext(**values)


def test_smart_t_entry_gate_requires_vwap_discount_and_volume_release() -> None:
    result = evaluate_smart_t_entry_gate(
        quote_price=9.94,
        context=_context(),
        params={"smart_t_add_vwap_discount_pct": 0.3, "smart_t_add_volume_release_ratio_max": 0.4},
    )

    assert result.allowed is True
    assert result.vwap_discount_pct >= 0.3


def test_smart_t_entry_gate_blocks_when_price_not_discounted_enough() -> None:
    result = evaluate_smart_t_entry_gate(
        quote_price=9.99,
        context=_context(),
        params={"smart_t_add_vwap_discount_pct": 0.3},
    )

    assert result.allowed is False
    assert "折价区间" in result.reason


def test_smart_t_entry_gate_blocks_when_volume_release_too_large() -> None:
    result = evaluate_smart_t_entry_gate(
        quote_price=9.94,
        context=_context(volume_release_ratio=0.62),
        params={"smart_t_add_volume_release_ratio_max": 0.4},
    )

    assert result.allowed is False
    assert "量能释放" in result.reason
