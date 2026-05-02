from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Vercel's `/api` function path already contributes the external `/api` prefix,
# so we remove the internal prefix here to avoid `/api/api/*`.
os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/t_quant.db")

from app.main import app
