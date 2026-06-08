from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.services.analytics.config import analytics_config
from app.services.analytics.duckdb_repository import DuckDBRepository
from app.services.analytics.manifest import load_manifest
from app.services.backtest.data_provider import DailyBar, DailyBarDataProvider

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SYMBOL_PATTERN = re.compile(r"^[0-9A-Za-z._-]{1,32}$")


class DailyBarParquetDataProvider(DailyBarDataProvider):
    """Daily-bar provider that reads archived bars from Parquet via DuckDB.

    Signals still come from the transactional DB through the base provider. This
    keeps production signal semantics unchanged while moving historical daily
    bar scans to the analysis layer when explicitly enabled.
    """

    def __init__(self, db: Session, *, manifest: str = "latest", output_root: str | Path | None = None) -> None:
        super().__init__(db)
        self.output_root = output_root
        self.manifest_ref = manifest or "latest"
        self.manifest = load_manifest(self.manifest_ref, output_root=output_root)
        self._config = analytics_config(output_root)
        self._parquet_glob = str(self._config.parquet_dir / "daily_bars" / "**" / "*.parquet")

    def fetch_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        start = _date_literal(start_date)
        end = _date_literal(end_date)
        repo = DuckDBRepository(output_root=self.output_root)
        try:
            rows = repo.query_all(
                f"""
                SELECT DISTINCT CAST(trade_date AS VARCHAR) AS trade_date
                FROM read_parquet('{self._parquet_glob}')
                WHERE CAST(trade_date AS DATE) >= CAST('{start}' AS DATE)
                    AND CAST(trade_date AS DATE) <= CAST('{end}' AS DATE)
                ORDER BY trade_date ASC
                """
            )
        finally:
            repo.close()
        return [str(row["trade_date"])[:10] for row in rows]

    def fetch_bars(
        self,
        symbols: Iterable[str],
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, list[DailyBar]]:
        unique_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not unique_symbols:
            return {}
        start = _date_literal(start_date)
        end = _date_literal(end_date)
        symbol_sql = ", ".join(f"'{_symbol_literal(symbol)}'" for symbol in unique_symbols)
        repo = DuckDBRepository(output_root=self.output_root)
        try:
            rows = repo.query_all(
                f"""
                SELECT
                    symbol,
                    CAST(trade_date AS VARCHAR) AS trade_date,
                    open,
                    close,
                    high,
                    low,
                    volume,
                    amount,
                    pct_chg,
                    pre_close
                FROM read_parquet('{self._parquet_glob}')
                WHERE symbol IN ({symbol_sql})
                    AND CAST(trade_date AS DATE) >= CAST('{start}' AS DATE)
                    AND CAST(trade_date AS DATE) <= CAST('{end}' AS DATE)
                ORDER BY symbol ASC, trade_date ASC
                """
            )
        finally:
            repo.close()
        grouped: dict[str, list[DailyBar]] = {}
        previous_close_by_symbol: dict[str, float] = {}
        for row in rows:
            bar = _bar_from_parquet_row(row, previous_close=previous_close_by_symbol.get(str(row["symbol"])))
            grouped.setdefault(bar.symbol, []).append(bar)
            if bar.close_price > 0:
                previous_close_by_symbol[bar.symbol] = bar.close_price
        return grouped

    def dataset_manifest(
        self,
        *,
        start_date: str,
        end_date: str,
        symbols: Iterable[str],
    ) -> dict[str, Any]:
        unique_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        payload = dict(self.manifest)
        return {
            "dataset_key": str(payload.get("dataset_key") or "daily_bars"),
            "source_table": str((payload.get("source") or {}).get("source_table") or "daily_bar_snapshots"),
            "source_hash": str(payload.get("manifest_id") or payload.get("dataset_version") or ""),
            "manifest_hash": str(payload.get("manifest_id") or payload.get("dataset_version") or ""),
            "manifest_id": str(payload.get("manifest_id") or ""),
            "dataset_version": str(payload.get("dataset_version") or ""),
            "manifest_path": str(payload.get("manifest_path") or ""),
            "data_version": str(payload.get("schema_version") or ""),
            "date_range_start": start_date,
            "date_range_end": end_date,
            "start_date": start_date,
            "end_date": end_date,
            "instrument_count": len(unique_symbols),
            "record_count": int(payload.get("row_count") or 0),
            "bar_count": int(payload.get("row_count") or 0),
            "adjustment_method": "forward",
            "quality_tag": str(payload.get("quality_status") or payload.get("status") or "unknown"),
            "storage": "parquet",
        }


def _bar_from_parquet_row(row: dict[str, Any], *, previous_close: float | None = None) -> DailyBar:
    close_price = _safe_float(row.get("close"))
    pct_chg = _safe_float(row.get("pct_chg"))
    pre_close = _safe_float(row.get("pre_close"))
    if pre_close <= 0:
        denominator = 1 + pct_chg / 100
        if close_price > 0 and denominator > 0:
            pre_close = close_price / denominator
        elif previous_close and previous_close > 0:
            pre_close = float(previous_close)
        else:
            pre_close = close_price
    return DailyBar(
        symbol=str(row.get("symbol") or ""),
        trade_date=str(row.get("trade_date") or "")[:10],
        open_price=_safe_float(row.get("open")),
        close_price=close_price,
        high_price=_safe_float(row.get("high")),
        low_price=_safe_float(row.get("low")),
        volume=_safe_float(row.get("volume")),
        amount=_safe_float(row.get("amount")),
        pct_chg=pct_chg,
        pre_close=pre_close,
        instrument_type="stock",
        market="CN",
    )


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _date_literal(value: str) -> str:
    raw = str(value or "")[:10]
    if not _DATE_PATTERN.fullmatch(raw):
        raise ValueError(f"invalid backtest date for parquet provider: {value}")
    return raw


def _symbol_literal(value: str) -> str:
    raw = str(value or "").strip()
    if not _SYMBOL_PATTERN.fullmatch(raw):
        raise ValueError(f"invalid symbol for parquet provider: {value}")
    return raw.replace("'", "''")
