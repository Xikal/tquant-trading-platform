from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.schemas import KlineBar
from app.services.etf.oos_dataset import REQUIRED_REGIMES, dataset_response, load_oos_dataset, oos_segments_for_backtest
from app.services.etf.t0_backtest import run_etf_t0_research_report


DEFAULT_OOS_RUN_LOG = Path(__file__).resolve().parents[4] / "data" / "runtime" / "etf_t0_oos_validation_runs.jsonl"


def run_oos_validation(
    *,
    dataset_key: str,
    symbol: str,
    name: str,
    bars: list[KlineBar],
    quantity: int,
    min_signal_bars: int,
    max_trades_per_day: int,
    params: dict[str, Any] | None,
    vwap_deviation_values: list[float] | None,
    oversold_rsi_values: list[float] | None,
    persist: bool = True,
) -> dict[str, Any]:
    manifest = load_oos_dataset(dataset_key)
    dataset = dataset_response(manifest)
    segments = oos_segments_for_backtest(manifest)
    report = run_etf_t0_research_report(
        symbol=symbol,
        name=name,
        bars=bars,
        quantity=quantity,
        min_signal_bars=min_signal_bars,
        max_trades_per_day=max_trades_per_day,
        params=params,
        vwap_deviation_values=vwap_deviation_values,
        oversold_rsi_values=oversold_rsi_values,
        market_regime_segments=segments,
    )
    report_dict = report.to_dict()
    report_dict["regime_validations"] = _with_missing_regimes(report_dict.get("regime_validations", []), dataset.get("missing_regimes", []))
    gate = _oos_gate(dataset=dataset, report=report_dict, bars=bars)
    result = {
        "run_id": str(uuid4()),
        "dataset": dataset,
        "research_report": report_dict,
        "verdict": gate["verdict"],
        "stage": gate["stage"],
        "passed": gate["passed"],
        "gate_reasons": gate["gate_reasons"],
        "missing_regimes": dataset.get("missing_regimes", []),
        "notes": [
            "OOS 验证使用 manifest 中真实标注的 regime_segments，不使用自动等分。",
            "通过 OOS 也只生成阶段建议，不写生产策略、不改模拟盘账本、不绕过风控和人工确认。",
        ],
    }
    if persist:
        record_oos_validation_run(result)
    return result


def promote_check(
    *,
    dataset_key: str,
    symbol: str,
    name: str,
    bars: list[KlineBar],
    quantity: int,
    min_signal_bars: int,
    max_trades_per_day: int,
    params: dict[str, Any] | None,
    vwap_deviation_values: list[float] | None,
    oversold_rsi_values: list[float] | None,
) -> dict[str, Any]:
    validation = run_oos_validation(
        dataset_key=dataset_key,
        symbol=symbol,
        name=name,
        bars=bars,
        quantity=quantity,
        min_signal_bars=min_signal_bars,
        max_trades_per_day=max_trades_per_day,
        params=params,
        vwap_deviation_values=vwap_deviation_values,
        oversold_rsi_values=oversold_rsi_values,
        persist=False,
    )
    allowed = validation["stage"] in {"paper_small", "candidate_production"}
    return {
        "dataset_key": dataset_key,
        "symbol": symbol,
        "stage": validation["stage"],
        "allowed": allowed,
        "verdict": validation["verdict"],
        "gate_reasons": validation["gate_reasons"],
        "notes": ["promote-check 为只读检查，不修改生产状态。"],
    }


def record_oos_validation_run(result: dict[str, Any]) -> None:
    path = _run_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = latest_summary_from_validation(result)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def latest_oos_validation_summary() -> dict[str, Any]:
    path = _run_log_path()
    if not path.exists():
        return {
            "available": False,
            "stage": "research_only",
            "verdict": "needs_validation",
            "gate_reasons": ["尚未运行真实 OOS 验证。"],
        }
    last: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            last = value
    return last or {
        "available": False,
        "stage": "research_only",
        "verdict": "needs_validation",
        "gate_reasons": ["OOS 验证记录为空。"],
    }


def latest_summary_from_validation(result: dict[str, Any]) -> dict[str, Any]:
    dataset = result.get("dataset") if isinstance(result.get("dataset"), dict) else {}
    report = result.get("research_report") if isinstance(result.get("research_report"), dict) else {}
    return {
        "available": True,
        "run_id": result.get("run_id", ""),
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "dataset_key": dataset.get("dataset_key", ""),
        "dataset_version": dataset.get("version", ""),
        "checksum": dataset.get("checksum", ""),
        "symbol": report.get("symbol", ""),
        "name": report.get("name", ""),
        "stage": result.get("stage", "research_only"),
        "verdict": result.get("verdict", "blocked"),
        "passed": bool(result.get("passed")),
        "gate_reasons": list(result.get("gate_reasons") or []),
        "missing_regimes": list(result.get("missing_regimes") or []),
        "quality": dataset.get("quality", {}),
    }


def _oos_gate(*, dataset: dict[str, Any], report: dict[str, Any], bars: list[KlineBar]) -> dict[str, Any]:
    reasons: list[str] = []
    if not dataset.get("quality_ok"):
        reasons.extend([item.get("message", "dataset quality failed") for item in dataset.get("validation_issues", []) if item.get("severity") == "error"])
    if len(dataset.get("covered_regimes", [])) < 4:
        reasons.append("真实 OOS 覆盖市场状态少于 4 类。")
    if len(bars) < 500:
        reasons.append("本次请求分钟线样本少于 500 根，只能研究观察。")
    validations = list(report.get("regime_validations") or [])
    fail_count = sum(1 for item in validations if item.get("verdict") == "fail")
    pass_count = sum(1 for item in validations if item.get("verdict") == "pass")
    risk_off = [item for item in validations if item.get("regime") in {"退潮", "risk_off"}]
    if any(float(item.get("net_pnl") or 0) < 0 and int(item.get("trade_count") or 0) > 0 for item in risk_off):
        reasons.append("退潮期 OOS 出现亏损交易，不能升档。")
    heatmap_pass_count = sum(1 for item in report.get("heatmap", []) if item.get("pass_gate"))
    if heatmap_pass_count < 2:
        reasons.append("参数热力图通过点少于 2 个，稳定性证据不足。")
    if fail_count:
        reasons.append(f"OOS 市场状态验证存在 {fail_count} 个 fail。")
    if reasons:
        return {"passed": False, "verdict": "blocked", "stage": "research_only", "gate_reasons": reasons}
    if pass_count >= 4 and set(dataset.get("covered_regimes", [])) == set(REQUIRED_REGIMES) and heatmap_pass_count >= 4:
        return {"passed": True, "verdict": "pass", "stage": "candidate_production", "gate_reasons": ["OOS 五类覆盖和参数稳定性满足候选生产建议。"]}
    if pass_count >= 3:
        return {"passed": True, "verdict": "pass", "stage": "paper_small", "gate_reasons": ["OOS 通过基础门槛，仅建议进入小仓模拟盘观察。"]}
    return {"passed": False, "verdict": "observe", "stage": "research_only", "gate_reasons": ["OOS 无硬失败，但 pass 市场状态少于 3 类。"]}


def _with_missing_regimes(validations: list[dict[str, Any]], missing: list[str]) -> list[dict[str, Any]]:
    result = list(validations)
    labels = {
        "bull": "牛市",
        "range": "震荡",
        "bear": "熊市",
        "risk_off": "退潮",
        "strong_rebound": "强反弹",
    }
    for regime in missing:
        result.append(
            {
                "regime": labels.get(regime, regime),
                "start_time": "",
                "end_time": "",
                "bar_count": 0,
                "trade_count": 0,
                "win_rate_pct": 0.0,
                "net_pnl": 0.0,
                "profit_factor": None,
                "max_drawdown_pct": 0.0,
                "baseline_hold_return_pct": 0.0,
                "verdict": "needs_data",
                "notes": ["OOS manifest 缺少该市场状态，不能作为升档证据。"],
            }
        )
    return result


def _run_log_path() -> Path:
    return Path(os.getenv("TQUANT_ETF_T0_OOS_RUN_LOG", str(DEFAULT_OOS_RUN_LOG))).expanduser()
