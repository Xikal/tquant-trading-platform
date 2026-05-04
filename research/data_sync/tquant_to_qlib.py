from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pandas as pd


DAILY_BAR_COLUMNS = ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"]


def qlib_status() -> dict[str, object]:
    """Return qlib availability without importing it at module load time."""

    if importlib.util.find_spec("qlib") is None:
        return {
            "available": False,
            "message": "qlib 未安装，已跳过 qlib 初始化；离线 CSV/Parquet 报告仍可生成。",
        }
    return {"available": True, "message": "qlib 可用，可按需初始化离线研究环境。"}


def read_offline_table(path: str | Path) -> pd.DataFrame:
    """Read an offline research table, returning an empty frame when absent."""

    source = Path(path)
    if not source.exists():
        return pd.DataFrame()
    if source.suffix == ".csv":
        return pd.read_csv(source)
    if source.suffix in {".json", ".jsonl"}:
        return pd.read_json(source, lines=source.suffix == ".jsonl")
    if source.suffix == ".parquet":
        try:
            return pd.read_parquet(source)
        except ImportError:
            csv_fallback = source.with_suffix(".csv")
            if csv_fallback.exists():
                return pd.read_csv(csv_fallback)
            raise RuntimeError("读取 parquet 需要 pyarrow/fastparquet；可改用 CSV 离线输入。")
    raise ValueError(f"Unsupported offline table format: {source.suffix}")


def _write_offline_table(frame: pd.DataFrame, output_dir: Path, stem: str) -> Path:
    """Prefer parquet, but degrade to CSV when optional engines are missing."""

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / f"{stem}.parquet"
    try:
        frame.to_parquet(parquet_path, index=False)
        return parquet_path
    except (ImportError, ValueError, ModuleNotFoundError):
        csv_path = output_dir / f"{stem}.csv"
        frame.to_csv(csv_path, index=False)
        return csv_path


def export_daily_bars(database_url: str, output_dir: Path) -> Path:
    """Export local daily bars to a columnar file for offline research."""

    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    frame = pd.read_sql_query(
        """
        SELECT symbol, trade_date, open, high, low, close, volume, amount
        FROM daily_bar_snapshots
        ORDER BY symbol, trade_date
        """,
        engine,
    )
    if frame.empty:
        frame = pd.DataFrame(columns=DAILY_BAR_COLUMNS)
    return _write_offline_table(frame, output_dir, "daily_bars")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export TQuant bars for offline research.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output-dir", default="research/reports/datasets")
    parser.add_argument("--check-qlib", action="store_true", help="Print optional qlib status before export.")
    args = parser.parse_args()
    if args.check_qlib:
        status = qlib_status()
        print(f"qlib_available={status['available']}: {status['message']}")
    path = export_daily_bars(args.database_url, Path(args.output_dir))
    print(f"exported: {path}")


if __name__ == "__main__":
    main()
