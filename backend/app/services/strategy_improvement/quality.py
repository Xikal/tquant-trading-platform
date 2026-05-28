from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy import func, select, text

from app.models.entities import DailyBarSnapshot


def data_quality_checks(db, *, start: str, end: str, daily: dict[str, Any], minute: dict[str, Any]) -> dict[str, Any]:
    duplicate_daily = db.execute(
        select(func.count()).select_from(
            select(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
            .where(DailyBarSnapshot.trade_date >= start, DailyBarSnapshot.trade_date <= end)
            .group_by(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
            .having(func.count(DailyBarSnapshot.id) > 1)
            .subquery()
        )
    ).scalar_one()
    invalid_ohlc = db.execute(
        select(func.count(DailyBarSnapshot.id)).where(
            DailyBarSnapshot.trade_date >= start,
            DailyBarSnapshot.trade_date <= end,
            (
                (DailyBarSnapshot.open_price <= 0)
                | (DailyBarSnapshot.close_price <= 0)
                | (DailyBarSnapshot.high_price < DailyBarSnapshot.low_price)
                | (DailyBarSnapshot.high_price < DailyBarSnapshot.open_price)
                | (DailyBarSnapshot.high_price < DailyBarSnapshot.close_price)
                | (DailyBarSnapshot.low_price > DailyBarSnapshot.open_price)
                | (DailyBarSnapshot.low_price > DailyBarSnapshot.close_price)
            ),
        )
    ).scalar_one()
    negative_volume = db.execute(
        select(func.count(DailyBarSnapshot.id)).where(
            DailyBarSnapshot.trade_date >= start,
            DailyBarSnapshot.trade_date <= end,
            ((DailyBarSnapshot.volume < 0) | (DailyBarSnapshot.amount < 0)),
        )
    ).scalar_one()
    gaps = lineage_field_gaps(db)
    metadata = metadata_coverage_checks(db, start=start, end=end)
    issues = _issues(
        duplicate_daily=int(duplicate_daily or 0),
        invalid_ohlc=int(invalid_ohlc or 0),
        negative_volume=int(negative_volume or 0),
        gaps=gaps,
    )
    return {
        "status": "pass" if not any(item["severity"] == "blocking" for item in issues) else "fail",
        "freshness_status": "fresh_enough_for_research" if daily.get("coverage_pct", 0) >= 20 else "insufficient",
        "duplicate_daily_symbol_date_count": int(duplicate_daily or 0),
        "invalid_daily_ohlc_count": int(invalid_ohlc or 0),
        "negative_volume_or_amount_count": int(negative_volume or 0),
        "lineage_field_gaps": gaps,
        "metadata_coverage": metadata,
        "issues": issues,
        "notes": [
            "涨跌停、停牌/ST/退市/上市日期、行业/概念历史、ETF 溢折价/流动性作为独立元数据门禁判断。",
            "停牌日不得伪造 K 线；当前脚本只读检查，不生成缺失交易日价格。",
            f"ETF 分钟线覆盖由独立门禁判断：{minute.get('status') or 'unknown'}。",
        ],
    }


def lineage_field_gaps(db) -> list[str]:
    required = [
        "daily_bar_snapshots.source",
        "daily_bar_snapshots.fetch_time",
        "daily_bar_snapshots.adjusted_mode",
        "daily_bar_snapshots.checksum",
        "daily_bar_snapshots.data_quality",
        "minute_bar_snapshots.source",
        "minute_bar_snapshots.fetch_time",
        "minute_bar_snapshots.checksum",
        "minute_bar_snapshots.data_quality",
    ]
    inspector = inspect(db.get_bind())
    existing_by_table = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("daily_bar_snapshots", "minute_bar_snapshots")
        if table in inspector.get_table_names()
    }
    return [item for item in required if item.split(".", 1)[1] not in existing_by_table.get(item.split(".", 1)[0], set())]


def metadata_coverage_checks(db, *, start: str, end: str) -> dict[str, Any]:
    inspector = inspect(db.get_bind())
    table_names = set(inspector.get_table_names())
    columns_by_table = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in table_names
    }
    schema_checks = _metadata_schema_checks(table_names, columns_by_table)
    data_checks = _metadata_data_checks(db, table_names=table_names, columns_by_table=columns_by_table, start=start, end=end)
    blocking_gaps = [
        gap
        for check in [*schema_checks, *data_checks]
        if check["status"] != "pass"
        for gap in check.get("missing", [])
    ]
    return {
        "status": "pass" if not blocking_gaps else "fail",
        "blocking_gap_count": len(blocking_gaps),
        "blocking_gaps": blocking_gaps,
        "schema_checks": schema_checks,
        "data_checks": data_checks,
        "notes": [
            "OHLCV 通过不代表可以正式验收；交易规则元数据缺失时只能 research_only。",
            "行业/概念必须有历史口径，不能用当前 sector_name 回填过去。",
            "ETF T0 必须保留 T+0 能力、流动性、滑点和折溢价数据来源。",
        ],
    }


def _metadata_schema_checks(table_names: set[str], columns_by_table: dict[str, set[str]]) -> list[dict[str, Any]]:
    required_groups = [
        (
            "daily_limit_and_status_fields",
            [
                "daily_bar_snapshots.limit_up_price",
                "daily_bar_snapshots.limit_down_price",
                "daily_bar_snapshots.is_suspended",
                "daily_bar_snapshots.is_st",
                "daily_bar_snapshots.is_delisted",
            ],
            "日线回测需要涨跌停、停牌、ST、退市状态，避免生成不可交易成交。",
        ),
        (
            "instrument_lifecycle_fields",
            [
                "instruments.listing_date",
                "instruments.delisting_date",
                "instruments.is_st",
                "instruments.status",
            ],
            "全市场回测必须知道上市/退市/ST 状态，避免幸存者偏差。",
        ),
        (
            "etf_intraday_execution_fields",
            [
                "minute_bar_snapshots.bid_ask_spread",
                "minute_bar_snapshots.premium_discount_pct",
                "minute_bar_snapshots.tracking_index_symbol",
                "minute_bar_snapshots.liquidity_tier",
            ],
            "ETF T0 不能只靠分钟价格，需要盘口价差、折溢价、跟踪指数和流动性。",
        ),
        (
            "etf_rule_fields",
            [
                "instrument_rules.same_day_sell_allowed",
                "instrument_rules.supports_positive_t",
                "instrument_rules.supports_negative_t",
            ],
            "ETF/个股做T必须区分 T+0 与底仓做T能力。",
        ),
    ]
    checks = [_schema_group_status(key, fields, reason, columns_by_table) for key, fields, reason in required_groups]
    history_tables = {
        "industry_history": _has_any_table(table_names, ["industry_history_snapshots", "sector_history_snapshots", "instrument_industry_history"]),
        "concept_history": _has_any_table(table_names, ["concept_history_snapshots", "instrument_concept_history"]),
    }
    for key, table in history_tables.items():
        checks.append(
            {
                "key": key,
                "status": "pass" if table else "fail",
                "missing": [] if table else [f"{key}_table"],
                "evidence": {"matched_table": table or ""},
                "reason": "主线板块、概念轮动和历史归因必须使用当时历史口径。",
            }
        )
    return checks


def _metadata_data_checks(db, *, table_names: set[str], columns_by_table: dict[str, set[str]], start: str, end: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    instrument_columns = columns_by_table.get("instruments", set())
    if "instruments" not in table_names or "sector_name" not in instrument_columns:
        checks.append(
            {
                "key": "static_sector_coverage",
                "status": "fail",
                "missing": ["instruments.sector_name"],
                "evidence": {},
                "reason": "当前行业字段都不存在，无法校验板块过滤。",
            }
        )
    else:
        total = _scalar_int(db, "select count(*) from instruments where instrument_type = 'stock'")
        filled = _scalar_int(db, "select count(*) from instruments where instrument_type = 'stock' and coalesce(sector_name, '') <> ''")
        coverage = round((filled / total * 100.0), 2) if total else 0.0
        checks.append(
            {
                "key": "static_sector_coverage",
                "status": "pass" if total > 0 and coverage >= 95.0 else "fail",
                "missing": [] if total > 0 and coverage >= 95.0 else ["instruments.sector_name_coverage_lt_95pct"],
                "evidence": {"stock_count": total, "sector_filled_count": filled, "coverage_pct": coverage},
                "reason": "静态行业字段是最低可读性要求；正式历史回测仍需要行业历史表。",
            }
        )
    if "instrument_rules" in table_names and "same_day_sell_allowed" in columns_by_table.get("instrument_rules", set()):
        t0_count = _scalar_int(db, "select count(*) from instrument_rules where same_day_sell_allowed = 1")
        checks.append(
            {
                "key": "persisted_t0_rule_coverage",
                "status": "pass" if t0_count > 0 else "fail",
                "missing": [] if t0_count > 0 else ["instrument_rules.same_day_sell_allowed_rows"],
                "evidence": {"same_day_sell_allowed_count": t0_count},
                "reason": "ETF T0 白名单需要可审计的持久化规则；只靠运行时代码表不足以完成回测验收。",
            }
        )
    if "daily_bar_snapshots" in table_names:
        daily_columns = columns_by_table.get("daily_bar_snapshots", set())
        if {"limit_up_price", "limit_down_price", "is_suspended", "is_st", "is_delisted"}.issubset(daily_columns):
            total_rows = _scalar_int(
                db,
                "select count(*) from daily_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'stock'",
                {"start": start, "end": end},
            )
            limit_rows = _scalar_int(
                db,
                "select count(*) from daily_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'stock' and limit_up_price > 0 and limit_down_price > 0",
                {"start": start, "end": end},
            )
            coverage = round((limit_rows / total_rows * 100.0), 2) if total_rows else 0.0
            checks.append(
                {
                    "key": "daily_limit_price_coverage",
                    "status": "pass" if total_rows > 0 and coverage >= 95.0 else "fail",
                    "missing": [] if total_rows > 0 and coverage >= 95.0 else ["daily_bar_snapshots.limit_price_coverage_lt_95pct"],
                    "evidence": {"daily_rows": total_rows, "limit_price_rows": limit_rows, "coverage_pct": coverage},
                    "reason": "涨跌停价格必须有真实覆盖，否则无法判断涨跌停附近成交与不可交易状态。",
                }
            )
    if "instruments" in table_names:
        lifecycle_columns = columns_by_table.get("instruments", set())
        if {"listing_date", "delisting_date", "is_st", "status"}.issubset(lifecycle_columns):
            total = _scalar_int(db, "select count(*) from instruments where instrument_type = 'stock' and coalesce(name, '') <> '' and coalesce(status, 'active') <> 'historical_metadata_only'")
            listed = _scalar_int(
                db,
                "select count(*) from instruments where instrument_type = 'stock' and coalesce(name, '') <> '' and coalesce(status, 'active') <> 'historical_metadata_only' and listing_date is not null",
            )
            active = _scalar_int(
                db,
                "select count(*) from instruments where instrument_type = 'stock' and coalesce(name, '') <> '' and coalesce(status, 'active') <> 'historical_metadata_only' and coalesce(status, '') <> ''",
            )
            listed_coverage = round((listed / total * 100.0), 2) if total else 0.0
            checks.append(
                {
                    "key": "instrument_lifecycle_coverage",
                    "status": "pass" if total > 0 and listed_coverage >= 95.0 and active >= total else "fail",
                    "missing": [] if total > 0 and listed_coverage >= 95.0 and active >= total else ["instruments.lifecycle_coverage_lt_95pct"],
                    "evidence": {"stock_count": total, "listing_date_count": listed, "status_count": active, "listing_date_coverage_pct": listed_coverage},
                    "reason": "上市/退市/ST 状态需要真实覆盖，避免幸存者偏差和不可交易标的进入回测。",
                }
            )
    daily_columns = columns_by_table.get("daily_bar_snapshots", set())
    if "daily_bar_snapshots" in table_names and {"source", "data_quality"}.issubset(daily_columns):
        fresh_count = _scalar_int(
            db,
            "select count(*) from daily_bar_snapshots where trade_date >= :start and trade_date <= :end and coalesce(data_quality, '') in ('fresh', 'verified')",
            {"start": start, "end": end},
        )
        checks.append(
            {
                "key": "daily_quality_lineage_rows",
                "status": "pass" if fresh_count > 0 else "fail",
                "missing": [] if fresh_count > 0 else ["daily_bar_snapshots.data_quality_fresh_rows"],
                "evidence": {"fresh_or_verified_rows": fresh_count},
                "reason": "正式数据需要明确 fresh/verified 来源；unknown 只能用于研究探针。",
            }
        )
    minute_columns = columns_by_table.get("minute_bar_snapshots", set())
    required_minute_exec = {"bid_ask_spread", "premium_discount_pct", "tracking_index_symbol", "liquidity_tier", "data_quality"}
    if "minute_bar_snapshots" in table_names and required_minute_exec.issubset(minute_columns):
        total_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf'",
            {"start": start, "end": end},
        )
        spread_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf' and bid_ask_spread > 0",
            {"start": start, "end": end},
        )
        premium_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf' and premium_discount_pct is not null",
            {"start": start, "end": end},
        )
        tracking_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf' and coalesce(tracking_index_symbol, '') <> ''",
            {"start": start, "end": end},
        )
        liquidity_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf' and coalesce(liquidity_tier, '') not in ('', 'unknown')",
            {"start": start, "end": end},
        )
        fresh_rows = _scalar_int(
            db,
            "select count(*) from minute_bar_snapshots where trade_date >= :start and trade_date <= :end and instrument_type = 'etf' and coalesce(data_quality, '') in ('fresh', 'verified')",
            {"start": start, "end": end},
        )
        evidence = {
            "etf_minute_rows": total_rows,
            "bid_ask_spread_positive_pct": _coverage_pct(spread_rows, total_rows),
            "premium_discount_pct": _coverage_pct(premium_rows, total_rows),
            "tracking_index_symbol_pct": _coverage_pct(tracking_rows, total_rows),
            "liquidity_tier_pct": _coverage_pct(liquidity_rows, total_rows),
            "fresh_or_verified_pct": _coverage_pct(fresh_rows, total_rows),
        }
        missing = [
            key
            for key, pct in [
                ("minute_bar_snapshots.bid_ask_spread_positive_coverage_lt_95pct", evidence["bid_ask_spread_positive_pct"]),
                ("minute_bar_snapshots.premium_discount_coverage_lt_95pct", evidence["premium_discount_pct"]),
                ("minute_bar_snapshots.tracking_index_coverage_lt_95pct", evidence["tracking_index_symbol_pct"]),
                ("minute_bar_snapshots.liquidity_tier_coverage_lt_95pct", evidence["liquidity_tier_pct"]),
                ("minute_bar_snapshots.data_quality_fresh_coverage_lt_95pct", evidence["fresh_or_verified_pct"]),
            ]
            if pct < 95.0
        ]
        if total_rows <= 0:
            missing.append("minute_bar_snapshots.etf_execution_metadata_rows")
        checks.append(
            {
                "key": "etf_intraday_execution_metadata_coverage",
                "status": "pass" if total_rows > 0 and not missing else "fail",
                "missing": missing,
                "evidence": evidence,
                "reason": "ETF T0 需要真实盘口价差、折溢价、跟踪指数、流动性和 fresh/verified 分钟执行元数据；默认 0 或 partial_metadata 不能正式验收。",
            }
        )
    return checks


def _schema_group_status(key: str, fields: list[str], reason: str, columns_by_table: dict[str, set[str]]) -> dict[str, Any]:
    missing = [field for field in fields if field.split(".", 1)[1] not in columns_by_table.get(field.split(".", 1)[0], set())]
    return {
        "key": key,
        "status": "pass" if not missing else "fail",
        "missing": missing,
        "evidence": {"required": fields},
        "reason": reason,
    }


def _has_any_table(table_names: set[str], candidates: list[str]) -> str:
    for table in candidates:
        if table in table_names:
            return table
    return ""


def _scalar_int(db, statement: str, params: dict[str, Any] | None = None) -> int:
    return int(db.execute(text(statement), params or {}).scalar_one() or 0)


def _coverage_pct(count: int, total: int) -> float:
    return round(float(count) / float(total) * 100.0, 2) if total else 0.0


def _issues(*, duplicate_daily: int, invalid_ohlc: int, negative_volume: int, gaps: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if duplicate_daily:
        issues.append({"severity": "blocking", "type": "duplicate_daily_bar", "count": duplicate_daily})
    if invalid_ohlc:
        issues.append({"severity": "blocking", "type": "invalid_ohlc", "count": invalid_ohlc})
    if negative_volume:
        issues.append({"severity": "blocking", "type": "negative_volume_or_amount", "count": negative_volume})
    if gaps:
        issues.append({"severity": "warning", "type": "lineage_fields_missing", "fields": gaps})
    return issues
