from scripts.late_session_board_backtest import (
    COHORTS,
    build_parser,
    cohort_summary,
    render_late_session_backtest_report,
)


def test_parser_accepts_late_session_backtest_options():
    args = build_parser().parse_args(
        [
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-06-12",
            "--limit",
            "12",
            "--source-limit",
            "30",
        ]
    )

    assert args.start_date == "2026-06-01"
    assert args.end_date == "2026-06-12"
    assert args.limit == 12
    assert args.source_limit == 30


def test_cohort_summary_keeps_required_comparison_groups():
    rows = [
        {"cohort": "priority_top_n", "next_day_return": 0.01, "hit": True},
        {"cohort": "late_confirmed", "next_day_return": 0.03, "hit": True},
        {"cohort": "late_watch", "next_day_return": -0.01, "hit": False},
        {"cohort": "late_rejected", "next_day_return": -0.02, "hit": False},
    ]

    summary = cohort_summary(rows)

    assert list(summary) == COHORTS
    assert summary["late_confirmed"]["sample_count"] == 1
    assert summary["late_confirmed"]["avg_next_day_return"] == 0.03
    assert summary["late_watch"]["hit_rate"] == 0.0


def test_report_documents_research_boundaries():
    report = render_late_session_backtest_report(
        start_date="2026-06-01",
        end_date="2026-06-12",
        limit=12,
        source_limit=30,
        summary=cohort_summary([]),
    )

    assert "priority board top N" in report
    assert "late_confirmed" in report
    assert "late_watch" in report
    assert "late_rejected" in report
    assert "max_gain" in report
    assert "不能作为可交易收益" in report
