from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ANALYTICS_ROOT = PROJECT_ROOT / "backend" / "data" / "analytics"


@dataclass(frozen=True)
class AnalyticsConfig:
    root: Path
    enabled: bool
    duckdb_threads: int

    @property
    def parquet_dir(self) -> Path:
        return self.root / "parquet"

    @property
    def manifest_dir(self) -> Path:
        return self.root / "manifests"

    @property
    def report_dir(self) -> Path:
        return self.root / "reports"

    def ensure_dirs(self) -> None:
        for path in (self.parquet_dir, self.manifest_dir, self.report_dir):
            path.mkdir(parents=True, exist_ok=True)


def analytics_config(output_root: str | Path | None = None) -> AnalyticsConfig:
    raw_root = output_root or os.getenv("TQUANT_ANALYTICS_ROOT") or DEFAULT_ANALYTICS_ROOT
    root = Path(raw_root).expanduser()
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return AnalyticsConfig(
        root=root,
        enabled=_truthy(os.getenv("TQUANT_ANALYTICS_ENABLED", "false")),
        duckdb_threads=max(int(os.getenv("TQUANT_DUCKDB_THREADS", "4") or 4), 1),
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
