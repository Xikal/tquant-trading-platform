from __future__ import annotations

from pathlib import Path

from app.services.low_buy.oos_validation_manifest import build_freeze_manifest, validate_freeze_manifest


def test_freeze_manifest_counts_only_post_freeze_trade_days(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text("{}", encoding="utf-8")

    manifest = build_freeze_manifest(
        freeze_date="2026-05-30",
        source_report_json=str(source),
        trade_dates=["2026-05-29", "2026-06-01", "2026-06-02"],
        git_commit="abc",
    )

    assert manifest["formal_oos_start"] == "2026-06-01"
    assert manifest["oos_window_trade_days"] == 2
    assert manifest["status"] == "insufficient_oos_window"


def test_validate_manifest_rejects_oos_start_on_or_before_freeze(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text("{}", encoding="utf-8")
    manifest = {
        "freeze_date": "2026-05-30",
        "formal_oos_start": "2026-05-30",
        "source_report_json": str(source),
        "scoring_config_version": "v",
        "random_split_allowed": False,
        "production_sort_replaced": False,
    }

    result = validate_freeze_manifest(manifest)

    assert not result.passed
    assert "oos_start_not_after_freeze" in result.blockers


def test_validate_manifest_rejects_random_split_and_production_replacement(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text("{}", encoding="utf-8")
    manifest = {
        "freeze_date": "2026-05-30",
        "formal_oos_start": "2026-06-01",
        "source_report_json": str(source),
        "scoring_config_version": "v",
        "random_split_allowed": True,
        "production_sort_replaced": True,
    }

    result = validate_freeze_manifest(manifest)

    assert "random_split_forbidden" in result.blockers
    assert "production_sort_replacement_forbidden" in result.blockers
