from __future__ import annotations

import json
from argparse import Namespace
from types import SimpleNamespace

from backend.scripts import daily_history_backfill_runner as runner


def test_runner_builds_batches_with_stable_report_paths(tmp_path) -> None:
    batches = runner.build_batches(symbols=["000001", "000002", "600000"], batch_size=2, run_dir=tmp_path)

    assert [item.batch_id for item in batches] == ["batch-0001", "batch-0002"]
    assert batches[0].symbols == ["000001", "000002"]
    assert batches[1].symbols == ["600000"]
    assert batches[0].report_path.endswith("batch-0001.json")


def test_runner_resolves_symbols_from_scope_with_limit(monkeypatch) -> None:
    def fake_load_symbols(*, scope: str, raw_symbols: str):
        assert scope == "pool"
        assert raw_symbols == ""
        return [SimpleNamespace(symbol="000001"), SimpleNamespace(symbol="600000")]

    monkeypatch.setattr(runner.backfill_daily_history, "_load_symbols", fake_load_symbols)
    args = Namespace(scope="pool", symbols="", limit=1)

    assert runner.resolve_symbols(args) == ["000001"]


def test_runner_requires_symbols_for_symbol_scope() -> None:
    args = Namespace(scope="symbols", symbols="", limit=0)

    try:
        runner.resolve_symbols(args)
    except SystemExit as exc:
        assert "必须提供 --symbols" in str(exc)
    else:
        raise AssertionError("resolve_symbols should reject empty symbol scope")


def test_runner_manifest_summarizes_batches(tmp_path) -> None:
    args = Namespace(
        scope="symbols",
        limit=0,
        start_date="2024-05-28",
        end_date="2024-06-07",
        batch_size=2,
        workers=1,
        resume=True,
        force=False,
    )
    batches = runner.build_batches(symbols=["000001", "600000"], batch_size=1, run_dir=tmp_path)
    results = [
        {"batch_id": "batch-0001", "status": "completed", "totals": {"ok": 1, "empty": 0, "error": 0, "skip": 0}},
        {"batch_id": "batch-0002", "status": "completed", "totals": {"ok": 0, "empty": 1, "error": 0, "skip": 0}},
    ]

    path = runner.write_manifest(tmp_path, run_id="test-run", args=args, batches=batches, results=results)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["status"] == "completed"
    assert payload["completed_batch_count"] == 2
    assert payload["totals"] == {"ok": 1, "skip": 0, "empty": 1, "error": 0}


def test_runner_resume_detects_completed_batch_report(tmp_path) -> None:
    report = tmp_path / "batch-0001.json"
    report.write_text(json.dumps({"status": "completed", "totals": {"ok": 1}}, ensure_ascii=False), encoding="utf-8")
    batch = runner.BatchSpec("batch-0001", ["000001"], str(report))

    summary = runner._load_batch_summary(batch, skipped=True)

    assert runner._batch_completed(str(report)) is True
    assert summary["resume_skipped"] is True
    assert summary["status"] == "completed"
    assert summary["totals"] == {"ok": 1}
