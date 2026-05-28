from __future__ import annotations

import json
from pathlib import Path

from app.services.etf.oos_dataset import dataset_response, list_oos_datasets, load_oos_dataset, manifest_checksum, validate_oos_manifest


def test_builtin_etf_t0_oos_manifest_has_checksum_and_five_regimes() -> None:
    items = list_oos_datasets()

    assert any(item["dataset_key"] == "etf_t0_oos_2026q2_v1" for item in items)
    manifest = load_oos_dataset("etf_t0_oos_2026q2_v1")
    response = dataset_response(manifest)
    assert response["checksum"].startswith("sha256:")
    assert response["quality_ok"] is True
    assert set(response["covered_regimes"]) == {"bull", "range", "bear", "risk_off", "strong_rebound"}
    assert response["missing_regimes"] == []


def test_oos_manifest_validator_blocks_bad_quality_and_missing_regimes() -> None:
    manifest = {
        "dataset_key": "bad",
        "version": "v1",
        "symbols": ["510300"],
        "period": "1m",
        "quality": {"bar_count": 100, "missing_bar_ratio": 0.08, "symbol_coverage_ratio": 0.50},
        "regime_segments": [
            {"regime": "range", "label": "震荡", "start_time": "2026-05-01 09:30", "end_time": "2026-05-01 15:00", "confidence": 0.9}
        ],
    }
    manifest["checksum"] = manifest_checksum(manifest)

    validation = validate_oos_manifest(manifest)

    assert validation["ok"] is False
    assert len(validation["missing_regimes"]) == 4
    messages = {item["field"] for item in validation["issues"]}
    assert {"quality.missing_bar_ratio", "quality.symbol_coverage_ratio", "regime_segments"} <= messages


def test_oos_dataset_loader_uses_manifest_dataset_key(tmp_path: Path, monkeypatch) -> None:
    manifest = {
        "dataset_key": "custom_dataset",
        "version": "custom-v1",
        "symbols": ["510300"],
        "period": "1m",
        "quality": {"bar_count": 6000, "missing_bar_ratio": 0.01, "symbol_coverage_ratio": 0.91},
        "regime_segments": [
            {"regime": "bull", "label": "牛市", "start_time": "a", "end_time": "b", "confidence": 0.9},
            {"regime": "range", "label": "震荡", "start_time": "b", "end_time": "c", "confidence": 0.9},
            {"regime": "bear", "label": "熊市", "start_time": "c", "end_time": "d", "confidence": 0.9},
            {"regime": "risk_off", "label": "退潮", "start_time": "d", "end_time": "e", "confidence": 0.9},
        ],
    }
    manifest["checksum"] = manifest_checksum(manifest)
    (tmp_path / "manifest-custom.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("TQUANT_ETF_T0_OOS_DIR", str(tmp_path))

    loaded = load_oos_dataset("custom_dataset")

    assert loaded["dataset_key"] == "custom_dataset"
    assert loaded["validation"]["ok"] is True
    assert loaded["validation"]["missing_regimes"] == ["strong_rebound"]
