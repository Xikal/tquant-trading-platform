from __future__ import annotations

from dataclasses import dataclass


DAILY_BARS_SCHEMA_VERSION = "1.0.0"
DATASET_DAILY_BARS = "daily_bars"

DAILY_BARS_COLUMNS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "volume",
    "amount",
    "pct_chg",
    "adjusted",
    "source",
    "loaded_at",
    "data_quality",
]


@dataclass(frozen=True)
class AnalyticsDatasetSchema:
    dataset_key: str
    schema_version: str
    columns: list[str]


DAILY_BARS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_DAILY_BARS,
    schema_version=DAILY_BARS_SCHEMA_VERSION,
    columns=DAILY_BARS_COLUMNS,
)
