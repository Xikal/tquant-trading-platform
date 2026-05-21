from __future__ import annotations

from app.services.market_rules import T0_KEYWORDS


def test_t0_keywords_are_deduplicated() -> None:
    assert len(T0_KEYWORDS) == len(set(T0_KEYWORDS))
