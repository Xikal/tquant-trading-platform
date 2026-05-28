from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Gate:
    key: str
    status: str
    severity: str
    message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


MIN_DAILY_COVERAGE_PCT = 95.0
MIN_STOCK_SYMBOLS = 4500
MIN_ETF_MINUTE_COVERAGE_PCT = 85.0
MIN_WF_TRADE_DAYS = 360
