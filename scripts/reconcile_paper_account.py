from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.services.paper.ledger_repair import PaperLedgerRepairService


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or repair a paper-trading account ledger.")
    parser.add_argument("--account-id", type=int, required=True, help="Paper account id to inspect or repair.")
    parser.add_argument("--apply", action="store_true", help="Apply the repair instead of previewing it.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = PaperLedgerRepairService(db)
        result = service.apply(args.account_id) if args.apply else service.preview(args.account_id)
        db.commit()
        print(
            json.dumps(
                {
                    "account_id": result.account_id,
                    "applied": result.applied,
                    "issue_count": result.issue_count,
                    "corrected_cash_available": float(result.corrected_cash_available),
                    "corrected_realized_pnl": float(result.corrected_realized_pnl),
                    "corrected_market_value": float(result.corrected_market_value),
                    "corrected_total_assets": float(result.corrected_total_assets),
                    "reconciliation_gap_before": float(result.reconciliation_gap_before),
                    "reconciliation_gap_after": float(result.reconciliation_gap_after),
                    "issues": result.issues,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
