#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.cloud_resource_gate_observation.cli import main  # noqa: E402
from scripts.cloud_resource_gate_observation.parsers import (  # noqa: E402,F401
    parse_compose_ps,
    parse_docker_stats,
    parse_http,
    parse_mysql_rows,
)


if __name__ == "__main__":
    raise SystemExit(main())
