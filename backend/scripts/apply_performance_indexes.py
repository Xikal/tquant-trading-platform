from __future__ import annotations

import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.core.schema_compat import ensure_schema_compatibility


def main() -> None:
    try:
        ensure_schema_compatibility(engine)
    except SQLAlchemyError as exc:
        print(f"performance indexes failed: database unavailable or rejected connection: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print("performance indexes verified")


if __name__ == "__main__":
    main()
