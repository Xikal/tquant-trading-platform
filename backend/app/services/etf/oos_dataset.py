from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.services.etf.t0_backtest import EtfT0MarketRegimeSegment


REGIME_LABELS = {
    "bull": "牛市",
    "range": "震荡",
    "bear": "熊市",
    "risk_off": "退潮",
    "strong_rebound": "强反弹",
}
REQUIRED_REGIMES = tuple(REGIME_LABELS)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OOS_DIR = PROJECT_ROOT / "backend" / "app" / "services" / "etf" / "oos_manifests"
LEGACY_OOS_DIR = PROJECT_ROOT / "data" / "oos" / "etf_t0"


class OOSDatasetError(ValueError):
    pass


def list_oos_datasets() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in _dataset_paths():
        try:
            manifest = load_oos_dataset(path.stem)
        except OOSDatasetError:
            continue
        key = str(manifest.get("dataset_key") or path.stem)
        if key in seen:
            continue
        seen.add(key)
        items.append(_dataset_summary(manifest))
    return items


def load_oos_dataset(dataset_key: str) -> dict[str, Any]:
    path = _resolve_dataset_path(dataset_key)
    if path is None:
        raise OOSDatasetError(f"OOS dataset 不存在: {dataset_key}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OOSDatasetError(f"OOS dataset 解析失败: {dataset_key}") from exc
    if not isinstance(value, dict):
        raise OOSDatasetError("OOS dataset manifest 必须是 JSON 对象")
    value["_path"] = str(path)
    validation = validate_oos_manifest(value)
    value["validation"] = validation
    return value


def validate_oos_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    dataset_key = str(manifest.get("dataset_key") or "")
    version = str(manifest.get("version") or "")
    if not dataset_key:
        issues.append({"severity": "error", "field": "dataset_key", "message": "dataset_key 不能为空。"})
    if not version:
        issues.append({"severity": "error", "field": "version", "message": "version 不能为空。"})
    checksum = str(manifest.get("checksum") or "")
    expected_checksum = manifest_checksum(manifest)
    if not checksum.startswith("sha256:"):
        issues.append({"severity": "error", "field": "checksum", "message": "checksum 必须使用 sha256: 前缀。"})
    elif checksum != expected_checksum:
        issues.append({"severity": "error", "field": "checksum", "message": "checksum 与 manifest 内容不一致。"})
    quality = manifest.get("quality") if isinstance(manifest.get("quality"), dict) else {}
    if _float(quality.get("missing_bar_ratio"), 1.0) > 0.03:
        issues.append({"severity": "error", "field": "quality.missing_bar_ratio", "message": "missing_bar_ratio 超过 3%。"})
    if _float(quality.get("symbol_coverage_ratio"), 0.0) < 0.90:
        issues.append({"severity": "error", "field": "quality.symbol_coverage_ratio", "message": "symbol_coverage_ratio 低于 90%。"})
    if _float(quality.get("bar_count"), 0.0) < 5000:
        issues.append({"severity": "warning", "field": "quality.bar_count", "message": "bar_count 低于建议 OOS 门槛 5000。"})
    segments = _segments(manifest)
    covered = sorted({item["regime"] for item in segments if item.get("regime") in REGIME_LABELS})
    missing = [item for item in REQUIRED_REGIMES if item not in covered]
    if len(covered) < 4:
        issues.append({"severity": "error", "field": "regime_segments", "message": "五类市场状态至少需覆盖 4 类。"})
    for segment in segments:
        if segment.get("regime") not in REGIME_LABELS:
            issues.append({"severity": "error", "field": "regime", "message": f"未知市场状态: {segment.get('regime')}"})
        if _float(segment.get("confidence"), 0.0) < 0.6:
            issues.append({"severity": "warning", "field": "confidence", "message": f"{segment.get('regime')} 标注置信度偏低。"})
    return {
        "ok": not any(item["severity"] == "error" for item in issues),
        "issues": issues,
        "covered_regimes": covered,
        "missing_regimes": missing,
        "coverage_count": len(covered),
        "required_regime_count": len(REQUIRED_REGIMES),
        "checksum_expected": expected_checksum,
    }


def manifest_checksum(manifest: dict[str, Any]) -> str:
    clone = deepcopy({key: value for key, value in manifest.items() if key not in {"checksum", "validation", "_path"}})
    raw = json.dumps(_stable(clone), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def oos_segments_for_backtest(manifest: dict[str, Any]) -> list[EtfT0MarketRegimeSegment]:
    return [
        EtfT0MarketRegimeSegment(
            regime=str(item.get("label") or REGIME_LABELS.get(str(item.get("regime") or ""), item.get("regime") or "")),
            start_time=str(item.get("start_time") or ""),
            end_time=str(item.get("end_time") or ""),
        )
        for item in _segments(manifest)
    ]


def regime_segments_out(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "regime": str(item.get("regime") or ""),
            "label": str(item.get("label") or REGIME_LABELS.get(str(item.get("regime") or ""), "")),
            "start_time": str(item.get("start_time") or ""),
            "end_time": str(item.get("end_time") or ""),
            "confidence": _float(item.get("confidence"), 0.0),
            "source": str(item.get("source") or ""),
            "source_version": str(item.get("source_version") or ""),
            "notes": str(item.get("notes") or ""),
        }
        for item in _segments(manifest)
    ]


def dataset_response(manifest: dict[str, Any]) -> dict[str, Any]:
    validation = manifest.get("validation") if isinstance(manifest.get("validation"), dict) else validate_oos_manifest(manifest)
    return {
        "dataset_key": str(manifest.get("dataset_key") or ""),
        "version": str(manifest.get("version") or ""),
        "created_at": str(manifest.get("created_at") or ""),
        "symbols": list(manifest.get("symbols") or []),
        "period": str(manifest.get("period") or "1m"),
        "start_time": str(manifest.get("start_time") or ""),
        "end_time": str(manifest.get("end_time") or ""),
        "checksum": str(manifest.get("checksum") or ""),
        "quality": dict(manifest.get("quality") or {}),
        "regime_segments": regime_segments_out(manifest),
        "covered_regimes": list(validation.get("covered_regimes") or []),
        "missing_regimes": list(validation.get("missing_regimes") or []),
        "validation_issues": list(validation.get("issues") or []),
        "quality_ok": bool(validation.get("ok")),
        "notes": list(manifest.get("notes") or []),
    }


def _dataset_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    response = dataset_response(manifest)
    return {
        **response,
        "regime_segments": response["regime_segments"][:5],
    }


def _segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("regime_segments") if isinstance(manifest, dict) else []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _resolve_dataset_path(dataset_key: str) -> Path | None:
    clean = str(dataset_key or "").strip()
    for path in _dataset_paths():
        if path.stem == clean:
            return path
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("dataset_key") == clean:
            return path
    return None


def _dataset_dir() -> Path:
    return Path(os.getenv("TQUANT_ETF_T0_OOS_DIR", str(DEFAULT_OOS_DIR))).expanduser()


def _dataset_paths() -> list[Path]:
    dirs = [_dataset_dir()]
    if "TQUANT_ETF_T0_OOS_DIR" not in os.environ and LEGACY_OOS_DIR != dirs[0]:
        dirs.append(LEGACY_OOS_DIR)
    paths: list[Path] = []
    seen: set[Path] = set()
    for directory in dirs:
        for path in sorted(directory.glob("*.json")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
