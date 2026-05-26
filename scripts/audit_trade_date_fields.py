#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_VENV_PYTHON = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"


def _reexec_with_backend_python() -> None:
    if os.environ.get("TQUANT_AUDIT_TRADE_DATE_NO_REEXEC") == "1":
        return
    if not BACKEND_VENV_PYTHON.exists():
        return
    try:
        current = Path(sys.executable).resolve()
        backend_python = BACKEND_VENV_PYTHON.resolve()
    except OSError:
        return
    if current == backend_python:
        return
    env = os.environ.copy()
    env["TQUANT_AUDIT_TRADE_DATE_NO_REEXEC"] = "1"
    pythonpath = str(PROJECT_ROOT / "backend")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = pythonpath if not existing else f"{pythonpath}{os.pathsep}{existing}"
    python_path = str(BACKEND_VENV_PYTHON)
    os.execve(python_path, [python_path, str(Path(__file__).resolve()), *sys.argv[1:]], env)


_reexec_with_backend_python()

from sqlalchemy import String


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from app.models.base import Base
    import app.models.entities  # noqa: F401
    import app.models.market_entities  # noqa: F401
    import app.models.backtest_entities  # noqa: F401
    import app.models.low_buy_entities  # noqa: F401
    import app.models.phase4_entities  # noqa: F401

    items = []
    for table in sorted(Base.metadata.sorted_tables, key=lambda item: item.name):
        for column in table.columns:
            if column.name in {"trade_date", "latest_trade_date", "signal_trade_date", "entry_trade_date", "exit_trade_date"} and isinstance(column.type, String):
                items.append(
                    {
                        "table": table.name,
                        "column": column.name,
                        "type": str(column.type),
                        "nullable": bool(column.nullable),
                        "indexed": bool(column.index),
                        "unique_constraints": [
                            constraint.name
                            for constraint in table.constraints
                            if column.name in [item.name for item in getattr(constraint, "columns", [])]
                        ],
                    }
                )
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2))
    return 1 if "--strict-empty" in sys.argv and items else 0


if __name__ == "__main__":
    raise SystemExit(main())
