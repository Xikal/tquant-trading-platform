from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import requests
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Instrument, MarketEventCache, MinuteBarSnapshot
from app.models.schemas import (
    InstrumentOut,
    KlineBar,
    MarketEventOut,
    MicrostructureSnapshot,
    QuoteSnapshot,
    SectorSnapshot,
)
from app.services.market_rules import MarketRuleService

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    ak = None


class DataSourceError(RuntimeError):
    pass


def guess_instrument_type(symbol: str, name: str = "") -> str:
    if MarketRuleService.looks_like_etf(symbol, name):
        return "etf"
    return "stock"


def guess_market(symbol: str) -> str:
    if symbol.startswith(("60", "68", "50", "51", "56", "58", "88", "90")):
        return "SH"
    if symbol.startswith(("00", "30", "15", "16", "20")):
        return "SZ"
    if symbol.startswith(("4", "8")):
        return "BJ"
    return "CN"


def to_secid(symbol: str) -> str:
    market_id = "1" if guess_market(symbol) == "SH" else "0"
    return f"{market_id}.{symbol}"


def _safe_float(value: Any, scale: float = 1.0) -> float:
    try:
        if value in (None, "", "-", "--"):
            return 0.0
        return round(float(value) / scale, 4)
    except (TypeError, ValueError):
        return 0.0


def _safe_str(value: Any) -> str:
    return "" if value is None else str(value)
