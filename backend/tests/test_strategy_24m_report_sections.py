from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, MinuteBarSnapshot
from scripts.strategy_24m_report_sections import etf_t0_section, production_conclusion
from scripts.strategy_24m_report_metrics import strategy_family_summary


def test_etf_t0_section_rejects_short_near_end_minute_window() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.add(_minute("510300", "2026-04-28"))
    db.commit()

    section = etf_t0_section(db, start="2026-04-27", end="2026-04-28")
    profile = next(item for item in section["reports"] if item["symbol"] == "510300")
    conclusion = production_conclusion(
        strategies=[],
        etf_t0=section,
        sector_etf_t0={"status": "shadow_observation_completed"},
        smart_t={"status": "daily_proxy_completed"},
        coverage={"status": "complete"},
    )

    assert section["status"] == "partial_minute_coverage"
    assert section["expected_trade_day_count"] == 2
    assert section["accepted_symbol_count"] == 0
    assert profile["status"] == "insufficient_window_minute_coverage"
    assert profile["trade_day_coverage_pct"] == 50.0
    assert conclusion["etf_t0_acceptance"] is False


def test_etf_t0_section_does_not_use_30m_bars_for_5m_acceptance() -> None:
    db = _session()
    db.add(_daily("2026-04-27", "000001"))
    db.add(_daily("2026-04-28", "000001"))
    db.add(
        MinuteBarSnapshot(
            symbol="510300",
            market="SH",
            instrument_type="etf",
            bar_period="30m",
            trade_date="2026-04-28",
            bar_timestamp="2026-04-28 10:00",
            close_price=4.0,
            source="sina.kline",
            data_quality="partial_metadata",
        )
    )
    db.commit()

    section = etf_t0_section(db, start="2026-04-27", end="2026-04-28")
    profile = next(item for item in section["reports"] if item["symbol"] == "510300")

    assert section["bar_period"] == "5m"
    assert profile["sample_count"] == 0
    assert profile["status"] == "no_minute_data"


def test_strategy_family_summary_is_research_only_and_contains_parameter_changes() -> None:
    strategies = [
        {
            "strategy_key": "ma_channel_band",
            "strategy_title": "均线通道支撑",
            "strategy_family": "trend_support_band",
            "strategy_family_text": "均线通道支撑",
            "sample_count": 12,
            "filled_count": 10,
            "win_rate_pct": 55.0,
            "profit_factor": 1.2,
            "avg_trade_return_pct": 0.4,
            "total_return_pct": 4.0,
            "annualized_return_pct": 2.0,
            "max_drawdown_pct": -6.0,
            "sharpe_ratio": 0.8,
            "stop_loss_rate_pct": 10.0,
            "avg_holding_days": 2.0,
            "quarter_breakdown": [
                {"key": "2025Q4", "sample_count": 4, "filled_count": 3, "win_rate_pct": 50.0, "profit_factor": 1.1, "total_return_pct": 1.0, "max_drawdown_pct": -2.0},
                {"key": "2026Q1", "sample_count": 4, "filled_count": 3, "win_rate_pct": 66.67, "profit_factor": 1.3, "total_return_pct": 2.0, "max_drawdown_pct": -3.0},
                {"key": "2026Q2", "sample_count": 4, "filled_count": 4, "win_rate_pct": 50.0, "profit_factor": 1.2, "total_return_pct": 1.0, "max_drawdown_pct": -1.5},
            ],
        },
        {
            "strategy_key": "leader_pullback_band",
            "strategy_title": "龙头回踩波段",
            "strategy_family": "leader_pullback_band",
            "strategy_family_text": "龙头回踩波段",
            "sample_count": 18,
            "filled_count": 0,
            "quarter_breakdown": [
                {"key": "2025Q4", "sample_count": 6, "filled_count": 0},
                {"key": "2026Q1", "sample_count": 6, "filled_count": 0},
                {"key": "2026Q2", "sample_count": 6, "filled_count": 0},
            ],
        },
    ]
    family_rows = []
    changes = [
        {
            "strategy_key": "ma_channel_band",
            "strategy_title": "均线通道支撑",
            "parameter_combinations_for_second_backtest": [{"name": "收紧入场过滤"}],
        }
    ]

    summary = strategy_family_summary(strategies, family_rows, changes)
    by_key = {item["key"]: item for item in summary["families"]}

    assert summary["status"] == "research_only"
    assert summary["production_parameter_change_allowed"] is False
    assert summary["sorting_effect"] == "none"
    assert by_key["trend_support_band"]["parameter_change_count"] == 1
    assert by_key["trend_support_band"]["metric_basis"] == "strategy_metric_weighted_proxy"
    assert by_key["trend_support_band"]["win_rate_pct"] == 55.0
    assert by_key["trend_support_band"]["profit_factor"] == 1.2
    assert by_key["trend_support_band"]["shadow_only"] is True
    assert by_key["trend_support_band"]["anti_overfit_policy"]["random_split_allowed"] is False
    assert summary["time_series_splits"]["status"] == "time_ordered_quarter_proxy"
    assert summary["time_series_splits"]["train_quarters"] == ["2025Q4"]
    assert summary["time_series_splits"]["validation_quarters"] == ["2026Q1"]
    assert summary["time_series_splits"]["out_of_sample_quarters"] == ["2026Q2"]
    assert summary["time_series_splits"]["production_ready"] is False
    assert summary["time_series_splits"]["random_split_allowed"] is False
    assert summary["time_series_splits"]["future_data_allowed_in_signal"] is False
    assert by_key["trend_support_band"]["time_series_splits"]["roles"]["out_of_sample"]["filled_count"] == 4
    assert by_key["leader_pullback_band"]["title"] == "龙头回踩波段"


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _daily(trade_date: str, symbol: str) -> DailyBarSnapshot:
    return DailyBarSnapshot(
        symbol=symbol,
        market="CN",
        instrument_type="stock",
        trade_date=trade_date,
        open_price=10,
        close_price=10.2,
        high_price=10.5,
        low_price=9.8,
        volume=1000,
        amount=10000,
        pct_chg=2,
    )


def _minute(symbol: str, trade_date: str) -> MinuteBarSnapshot:
    return MinuteBarSnapshot(
        symbol=symbol,
        market="SH",
        instrument_type="etf",
        bar_period="5m",
        trade_date=trade_date,
        bar_timestamp=f"{trade_date} 09:35",
        open_price=4.0,
        high_price=4.02,
        low_price=3.98,
        close_price=4.01,
        volume=1000,
        amount=4000,
        source="sina.kline",
        data_quality="fresh",
    )
