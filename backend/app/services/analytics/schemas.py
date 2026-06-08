from __future__ import annotations

from dataclasses import dataclass


DAILY_BARS_SCHEMA_VERSION = "1.0.0"
STRATEGY_TRACKING_SNAPSHOTS_SCHEMA_VERSION = "1.0.0"
KEY_LEVEL_SNAPSHOTS_SCHEMA_VERSION = "1.0.0"
LOW_BUY_RESULT_SNAPSHOTS_SCHEMA_VERSION = "1.0.0"
BACKTEST_RUNS_SCHEMA_VERSION = "1.0.0"
BACKTEST_TRADES_SCHEMA_VERSION = "1.0.0"
BACKTEST_DAILY_SNAPSHOTS_SCHEMA_VERSION = "1.0.0"
ANALYSIS_LOGS_SCHEMA_VERSION = "1.0.0"
MARKET_REVIEW_REPORTS_SCHEMA_VERSION = "1.0.0"
PAPER_REVIEW_REPORTS_SCHEMA_VERSION = "1.0.0"
DATASET_DAILY_BARS = "daily_bars"
DATASET_STRATEGY_TRACKING_SNAPSHOTS = "strategy_tracking_snapshots"
DATASET_KEY_LEVEL_SNAPSHOTS = "key_level_snapshots"
DATASET_LOW_BUY_RESULT_SNAPSHOTS = "low_buy_result_snapshots"
DATASET_BACKTEST_RUNS = "backtest_runs"
DATASET_BACKTEST_TRADES = "backtest_trades"
DATASET_BACKTEST_DAILY_SNAPSHOTS = "backtest_daily_snapshots"
DATASET_ANALYSIS_LOGS = "analysis_logs"
DATASET_MARKET_REVIEW_REPORTS = "market_review_reports"
DATASET_PAPER_REVIEW_REPORTS = "paper_review_reports"

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

STRATEGY_TRACKING_SNAPSHOT_COLUMNS = [
    "id",
    "snapshot_key",
    "as_of_date",
    "range_days",
    "strategy_key",
    "strategy_family",
    "market_scope",
    "filter_hash",
    "data_version",
    "status",
    "generated_at",
    "source_data_cutoff",
    "payload_json",
    "metrics_json",
    "error_message",
    "created_at",
    "updated_at",
]

STRATEGY_TRACKING_SNAPSHOTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_STRATEGY_TRACKING_SNAPSHOTS,
    schema_version=STRATEGY_TRACKING_SNAPSHOTS_SCHEMA_VERSION,
    columns=STRATEGY_TRACKING_SNAPSHOT_COLUMNS,
)

KEY_LEVEL_SNAPSHOT_COLUMNS = [
    "id",
    "scope",
    "cache_key",
    "symbol",
    "trade_date",
    "engine_version",
    "data_quality",
    "payload_json",
    "created_at",
    "updated_at",
]

KEY_LEVEL_SNAPSHOTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_KEY_LEVEL_SNAPSHOTS,
    schema_version=KEY_LEVEL_SNAPSHOTS_SCHEMA_VERSION,
    columns=KEY_LEVEL_SNAPSHOT_COLUMNS,
)

LOW_BUY_RESULT_SNAPSHOT_COLUMNS = [
    "id",
    "latest_trade_date",
    "strategy_key",
    "symbol",
    "name",
    "score",
    "buy_signal_state",
    "payload_json",
    "created_at",
    "updated_at",
]

LOW_BUY_RESULT_SNAPSHOTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_LOW_BUY_RESULT_SNAPSHOTS,
    schema_version=LOW_BUY_RESULT_SNAPSHOTS_SCHEMA_VERSION,
    columns=LOW_BUY_RESULT_SNAPSHOT_COLUMNS,
)

BACKTEST_RUN_COLUMNS = [
    "id",
    "name",
    "params_json",
    "result_json",
    "owner_user_id",
    "status",
    "strategy_keys",
    "start_date",
    "end_date",
    "benchmark_symbol",
    "initial_cash",
    "final_equity",
    "progress_pct",
    "max_duration_seconds",
    "optimization_id",
    "validation_id",
    "dataset_manifest_id",
    "engine_version",
    "strategy_version",
    "data_version",
    "fee_model_version",
    "slippage_bps",
    "error_message",
    "started_at",
    "finished_at",
    "cancelled_at",
    "deleted_at",
    "created_at",
    "updated_at",
]

BACKTEST_RUNS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_BACKTEST_RUNS,
    schema_version=BACKTEST_RUNS_SCHEMA_VERSION,
    columns=BACKTEST_RUN_COLUMNS,
)

BACKTEST_TRADE_COLUMNS = [
    "id",
    "run_id",
    "order_id",
    "trade_date",
    "symbol",
    "name",
    "side",
    "strategy_key",
    "signal_state",
    "quantity",
    "price",
    "gross_amount",
    "fee_amount",
    "slippage_amount",
    "net_amount",
    "pnl_amount",
    "pnl_pct",
    "holding_days",
    "entry_reason",
    "exit_reason",
    "market_state",
    "sector",
    "sector_name",
    "payload_json",
    "created_at",
]

BACKTEST_TRADES_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_BACKTEST_TRADES,
    schema_version=BACKTEST_TRADES_SCHEMA_VERSION,
    columns=BACKTEST_TRADE_COLUMNS,
)

BACKTEST_DAILY_SNAPSHOT_COLUMNS = [
    "id",
    "run_id",
    "trade_date",
    "cash",
    "market_value",
    "equity",
    "daily_return_pct",
    "drawdown_pct",
    "exposure_pct",
    "positions_count",
    "turnover",
    "benchmark_symbol",
    "benchmark_close",
    "benchmark_return_pct",
    "market_state",
    "payload_json",
    "created_at",
]

BACKTEST_DAILY_SNAPSHOTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_BACKTEST_DAILY_SNAPSHOTS,
    schema_version=BACKTEST_DAILY_SNAPSHOTS_SCHEMA_VERSION,
    columns=BACKTEST_DAILY_SNAPSHOT_COLUMNS,
)

ANALYSIS_LOG_COLUMNS = [
    "id",
    "symbol",
    "action",
    "signal_score",
    "risk_level",
    "payload_json",
    "created_at",
]

ANALYSIS_LOGS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_ANALYSIS_LOGS,
    schema_version=ANALYSIS_LOGS_SCHEMA_VERSION,
    columns=ANALYSIS_LOG_COLUMNS,
)

MARKET_REVIEW_REPORT_COLUMNS = [
    "id",
    "report_date",
    "report_slot",
    "overall_summary",
    "strategy_highlights",
    "risk_alerts",
    "suggestion",
    "raw_metrics_snapshot",
    "generated_at",
    "llm_model",
]

MARKET_REVIEW_REPORTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_MARKET_REVIEW_REPORTS,
    schema_version=MARKET_REVIEW_REPORTS_SCHEMA_VERSION,
    columns=MARKET_REVIEW_REPORT_COLUMNS,
)

PAPER_REVIEW_REPORT_COLUMNS = [
    "id",
    "account_id",
    "report_date",
    "report_slot",
    "overall_summary",
    "strategy_highlights",
    "risk_alerts",
    "suggestion",
    "raw_metrics_snapshot",
    "generated_at",
    "llm_model",
]

PAPER_REVIEW_REPORTS_SCHEMA = AnalyticsDatasetSchema(
    dataset_key=DATASET_PAPER_REVIEW_REPORTS,
    schema_version=PAPER_REVIEW_REPORTS_SCHEMA_VERSION,
    columns=PAPER_REVIEW_REPORT_COLUMNS,
)
