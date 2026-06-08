#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TRANSIENT_REMOTE_ERRORS = (
    "RemoteProtocolError",
    "Server disconnected without sending a response",
    "Timeout reading from socket",
    "TimeoutError",
    "timed out",
    "Connection reset by peer",
)


def main() -> int:
    args = parse_args()
    report = run_remote_measurement_with_retry(args)
    report_path = ROOT / "docs" / "reports" / f"gupiao-cloud-performance-{time.strftime('%Y-%m-%d-%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if report.get("ok") else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure deployed Go/Rust production path performance.")
    parser.add_argument("--host", default="43.143.243.97")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default="/Users/j/Downloads/gupiao.pem")
    parser.add_argument("--base-url", default="http://127.0.0.1:18090")
    parser.add_argument("--project-dir", default="/home/ubuntu/gupiao-upload")
    parser.add_argument("--samples", type=int, default=8)
    return parser.parse_args()


def run_remote_measurement_with_retry(args: argparse.Namespace) -> dict[str, Any]:
    first = run_remote_measurement(args)
    if first.get("ok") or not _measurement_retry_enabled():
        return first
    stderr = str(first.get("stderr") or "")
    if not _is_transient_remote_measurement_error(stderr):
        return first
    print("retrying transient online measurement", flush=True)
    second = run_remote_measurement(args)
    retry_errors = list(first.get("retry_errors") or [])
    retry_errors.append(
        {
            "error": first.get("error"),
            "stdout": str(first.get("stdout") or "")[-1000:],
            "stderr": stderr[-2000:],
        }
    )
    if isinstance(second, dict):
        second["retry_errors"] = retry_errors
    return second


def _measurement_retry_enabled() -> bool:
    return os.getenv("PERFORMANCE_MEASUREMENT_RETRY_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


def _is_transient_remote_measurement_error(stderr: str) -> bool:
    return any(token in str(stderr or "") for token in TRANSIENT_REMOTE_ERRORS)


def run_remote_measurement(args: argparse.Namespace) -> dict[str, Any]:
    script = textwrap.dedent(
        r"""
        import json, os, statistics, subprocess, time, urllib.error, urllib.request

        BASE_URL = os.environ["BASE_URL"].rstrip("/")
        PROJECT_DIR = os.environ.get("PROJECT_DIR", "/home/ubuntu/gupiao-upload")
        SAMPLES = int(os.environ.get("SAMPLES", "8"))

        def fetch(path, token="", timeout=10):
            req = urllib.request.Request(BASE_URL + path)
            if token:
                req.add_header("Authorization", "Bearer " + token)
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    body = response.read()
                return (time.perf_counter() - started) * 1000, response.status, body
            except urllib.error.HTTPError as exc:
                body = exc.read()
                return (time.perf_counter() - started) * 1000, exc.code, body
            except Exception as exc:
                body = str(exc).encode()
                return (time.perf_counter() - started) * 1000, "error:" + type(exc).__name__, body

        def login():
            username = "perf_gate_" + time.strftime("%Y%m%d%H%M%S")
            password = "PerfGate12345!"
            payload = json.dumps({"username": username, "password": password, "display_name": "perf gate"}).encode()
            req = urllib.request.Request(BASE_URL + "/api/auth/register", data=payload, headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=10).read()
            except Exception:
                pass
            payload = json.dumps({"username": username, "password": password}).encode()
            req = urllib.request.Request(BASE_URL + "/api/auth/login", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            return data["access_token"]

        def measure(name, path, token="", timeout=12, capture_payload=False):
            samples = []
            statuses = []
            sample_details = []
            payload_summary = {}
            for _ in range(SAMPLES):
                elapsed, status, body = fetch(path, token=token, timeout=timeout)
                samples.append(elapsed)
                statuses.append(status)
                detail = {
                    "status": status,
                    "elapsed_ms": round(elapsed, 3),
                }
                if status != 200:
                    detail["body"] = body.decode(errors="replace")[:500]
                sample_details.append(detail)
                if capture_payload and status == 200:
                    payload_summary = summarize_payload(name, body)
                time.sleep(0.08)
            ordered = sorted(samples)
            p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
            result = {
                "name": name,
                "path": path,
                "statuses": sorted(set(statuses), key=lambda item: str(item)),
                "p50_ms": round(statistics.median(samples), 3),
                "p95_ms": round(ordered[p95_index], 3),
                "samples": sample_details,
            }
            if payload_summary:
                result["payload_summary"] = payload_summary
            return result

        def prewarm_endpoint(path, token="", timeout=12):
            elapsed, status, body = fetch(path, token=token, timeout=timeout)
            detail = {
                "path": path,
                "status": status,
                "elapsed_ms": round(elapsed, 3),
            }
            if status != 200:
                detail["body"] = body.decode(errors="replace")[:500]
            return detail

        def prewarm_api_paths(token):
            paths = [
                "/readyz",
                "/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4",
                "/api/market/pulse",
                "/api/screeners/low-buy/priority-board?limit=12&refresh=cache",
                "/api/watchlist/signals",
            ]
            return [prewarm_endpoint(path, token=token if path.startswith("/api/") else "") for path in paths]

        def summarize_payload(name, body):
            try:
                payload = json.loads(body.decode(errors="replace"))
            except Exception as exc:
                return {"error": "payload_parse_failed", "detail": str(exc)[:200]}
            if name == "monitor_bff":
                snapshot = payload.get("monitor_snapshot") if isinstance(payload, dict) else {}
                board = snapshot.get("priority_board") if isinstance(snapshot, dict) else {}
                return {
                    "source_timings": payload.get("source_timings") or [],
                    "partial_errors": payload.get("partial_errors") or [],
                    "priority_items": len(board.get("items") or []) if isinstance(board, dict) else 0,
                    "generated_at": payload.get("generated_at") if isinstance(payload, dict) else "",
                }
            if name == "priority_board":
                return {
                    "items": len(payload.get("items") or []) if isinstance(payload, dict) else 0,
                    "read_path": payload.get("read_path") if isinstance(payload, dict) else "",
                    "stale": bool(payload.get("stale")) if isinstance(payload, dict) else False,
                    "stale_reason": payload.get("stale_reason") if isinstance(payload, dict) else "",
                    "refresh_queued": bool(payload.get("refresh_queued")) if isinstance(payload, dict) else False,
                    "data_quality": payload.get("data_quality") if isinstance(payload, dict) else "",
                    "data_quality_tags": payload.get("data_quality_tags") if isinstance(payload, dict) else [],
                }
            return {}

        def metrics(container, port):
            try:
                out = subprocess.check_output(["sudo", "docker", "exec", container, "wget", "-qO-", f"http://127.0.0.1:{port}/metrics"], text=True, timeout=10)
            except Exception as exc:
                return {"error": str(exc)}
            parsed = {}
            for line in out.splitlines():
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) == 2:
                    try:
                        parsed[parts[0]] = float(parts[1])
                    except ValueError:
                        pass
            return parsed

        def metric_delta(after, before):
            if not isinstance(after, dict) or not isinstance(before, dict):
                return {}
            result = {}
            for key, value in after.items():
                if key == "error":
                    continue
                try:
                    result[key] = max(0.0, float(value) - float(before.get(key, 0) or 0))
                except Exception:
                    pass
            return result

        def metric_value(metrics_map, name):
            try:
                return float(metrics_map.get(name) or 0)
            except Exception:
                return 0.0

        def partial_errors_by_source(metrics_map):
            result = {}
            prefix = "tquant_bff_gateway_partial_source_failures_total{source=\""
            for key, value in (metrics_map or {}).items():
                if not key.startswith(prefix):
                    continue
                try:
                    source_part = key.split('source="', 1)[1]
                    source = source_part.split('"', 1)[0]
                    reason_part = key.split('reason="', 1)[1]
                    reason = reason_part.split('"', 1)[0]
                except Exception:
                    continue
                result.setdefault(source, {})[reason] = value
            return result

        def observability_assessment(go_bff_metrics, go_market_metrics, quote_cache_coverage):
            bff_total = metric_value(go_bff_metrics, "tquant_bff_gateway_partial_source_failures_total")
            bff_timeout = metric_value(go_bff_metrics, 'tquant_bff_gateway_partial_source_failures_total{reason="timeout"}')
            bff_status = metric_value(go_bff_metrics, 'tquant_bff_gateway_partial_source_failures_total{reason="status"}')
            bff_decode = metric_value(go_bff_metrics, 'tquant_bff_gateway_partial_source_failures_total{reason="decode"}')
            bff_other = metric_value(go_bff_metrics, 'tquant_bff_gateway_partial_source_failures_total{reason="other"}')
            bff_classified = bff_timeout + bff_status + bff_decode + bff_other
            bff_cache_hit_rate = metric_value(go_bff_metrics, "tquant_bff_gateway_cache_hit_rate")
            market_misses = metric_value(go_market_metrics, "tquant_market_read_cache_miss_total")
            market_mysql = metric_value(go_market_metrics, "tquant_market_read_mysql_fallbacks_total")
            market_unresolved = metric_value(go_market_metrics, "tquant_market_read_unresolved_misses_total")
            market_partials = metric_value(go_market_metrics, "tquant_market_read_partials_total")
            market_fallbacks = metric_value(go_market_metrics, "tquant_market_read_fallbacks_total")
            warmup = quote_cache_coverage.get("warmup") if isinstance(quote_cache_coverage, dict) else {}
            warmup_coverage = warmup.get("coverage") if isinstance(warmup, dict) else {}
            quote_missing = int(quote_cache_coverage.get("missing_count") or 0) if isinstance(quote_cache_coverage, dict) else 0
            coverage_bps = int(warmup_coverage.get("coverage_ratio_bps") or 10000) if isinstance(warmup_coverage, dict) else 10000
            coverage_below_target = bool(warmup_coverage.get("coverage_below_target")) if isinstance(warmup_coverage, dict) else False
            alerts = []
            if bff_total > 0 and bff_classified < bff_total:
                alerts.append({
                    "severity": "warning",
                    "code": "bff_partial_unclassified",
                    "message": "BFF partial source failures are not fully classified by reason.",
                    "value": bff_total,
                    "classified": bff_classified,
                })
            if bff_timeout > 0:
                alerts.append({
                    "severity": "warning",
                    "code": "bff_partial_timeout",
                    "message": "BFF source timeouts occurred; inspect slow Python source endpoints.",
                    "value": bff_timeout,
                })
            if bff_status > 0 or bff_decode > 0:
                alerts.append({
                    "severity": "warning",
                    "code": "bff_partial_source_error",
                    "message": "BFF source returned non-2xx or invalid JSON; inspect partial_errors by source.",
                    "status_failures": bff_status,
                    "decode_failures": bff_decode,
                })
            if market_unresolved > 0 or quote_missing > 0 or coverage_below_target:
                alerts.append({
                    "severity": "critical" if quote_missing > 0 or coverage_below_target else "warning",
                    "code": "market_read_unresolved_miss",
                    "message": "Quote cache or Go market-read has symbols missing after warmup/fallback.",
                    "unresolved_misses": market_unresolved,
                    "quote_missing": quote_missing,
                    "quote_cache_coverage_bps": coverage_bps,
                })
            elif market_misses > 0 and market_mysql > 0:
                alerts.append({
                    "severity": "info",
                    "code": "market_read_mysql_fallback",
                    "message": "Redis misses were served by MySQL fallback; monitor cache warmup but do not page.",
                    "cache_misses": market_misses,
                    "mysql_fallbacks": market_mysql,
                })
            if market_fallbacks > 0 or market_partials > 0:
                alerts.append({
                    "severity": "warning" if market_fallbacks > 0 else "info",
                    "code": "market_read_partial_response",
                    "message": "Market-read returned partial or unavailable responses during the measurement window.",
                    "partials": market_partials,
                    "fallbacks": market_fallbacks,
                })
            severity_order = {"critical": 3, "warning": 2, "info": 1}
            max_severity = "none"
            for alert in alerts:
                severity = str(alert.get("severity") or "info")
                if severity_order.get(severity, 0) > severity_order.get(max_severity, 0):
                    max_severity = severity
            return {
                "ok": not any(item.get("severity") == "critical" for item in alerts),
                "max_severity": max_severity,
                "alerts": alerts,
                "bff_partial": {
                    "total": bff_total,
                    "classified": bff_classified,
                    "timeout": bff_timeout,
                    "status": bff_status,
                    "decode": bff_decode,
                    "other": bff_other,
                    "partial_errors_by_source": partial_errors_by_source(go_bff_metrics),
                },
                "go_bff_cache_hit_rate": bff_cache_hit_rate,
                "market_read": {
                    "cache_misses": market_misses,
                    "mysql_fallbacks": market_mysql,
                    "unresolved_misses": market_unresolved,
                    "partials": market_partials,
                    "fallbacks": market_fallbacks,
                    "quote_missing": quote_missing,
                    "quote_cache_coverage_bps": coverage_bps,
                },
            }

        def read_internal_token():
            env_path = os.path.join(PROJECT_DIR, ".env")
            try:
                with open(env_path, encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if line.startswith("TQUANT_INTERNAL_SERVICE_TOKEN="):
                            return line.split("=", 1)[1].strip().strip('"').strip("'")
            except OSError:
                return ""
            return ""

        def measure_scan_accept():
            token = read_internal_token()
            if not token:
                return {
                    "name": "scan_worker_accept",
                    "path": "/api/scan-worker/v1/run",
                    "statuses": ["missing_internal_token"],
                    "p50_ms": 999999,
                    "p95_ms": 999999,
                }
            samples = []
            statuses = []
            notes = []
            url = "http://127.0.0.1:8093/api/scan-worker/v1/run?strategies=first_board&scan_limit=12&limit=5&reason=perf_gate"
            for _ in range(SAMPLES):
                started = time.perf_counter()
                try:
                    out = subprocess.check_output([
                        "sudo", "docker", "exec", "tquant-go-scan-worker", "wget", "-qO-",
                        "--header", "X-Internal-Service-Token: " + token,
                        url,
                    ], stderr=subprocess.STDOUT, text=True, timeout=10)
                    payload = json.loads(out)
                    status, note = scan_accept_status(payload, 202 if payload.get("accepted") else 200)
                    statuses.append(status)
                    if note:
                        notes.append(note)
                except subprocess.CalledProcessError as exc:
                    payload = parse_scan_worker_payload(exc.output)
                    status, note = scan_accept_status(payload, 500)
                    statuses.append(status)
                    if note:
                        notes.append(note)
                except Exception as exc:
                    statuses.append("failed")
                    notes.append({"state": "failed", "detail": str(exc)})
                samples.append((time.perf_counter() - started) * 1000)
            ordered = sorted(samples)
            p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
            return {
                "name": "scan_worker_accept",
                "path": "/api/scan-worker/v1/run",
                "statuses": sorted(set(statuses), key=lambda item: str(item)),
                "p50_ms": round(statistics.median(samples), 3),
                "p95_ms": round(ordered[p95_index], 3),
                "notes": notes[-20:],
            }

        def parse_scan_worker_payload(raw):
            if not raw:
                return {}
            text = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            for line in reversed(text.splitlines()):
                candidate = line.strip()
                if not candidate or not candidate.startswith("{"):
                    continue
                try:
                    return json.loads(candidate)
                except Exception:
                    continue
            return {"status": "failed", "detail": text[-500:]}

        def scan_accept_status(payload, http_status):
            state = str(payload.get("status") or "").strip().lower()
            if payload.get("accepted") is True:
                state = "accepted"
            if not state and payload.get("fallback_available") is True and not payload.get("ok"):
                state = "fallback_available"
            non_fatal = {"accepted", "queued", "busy", "duplicate", "fallback_available"}
            if state in non_fatal:
                return 202, {"state": state, "http_status": http_status, "detail": payload.get("detail") or payload.get("fallback_reason") or ""}
            if payload.get("ok") is True:
                return 200, {"state": state or "ok", "http_status": http_status}
            return "failed", {"state": state or "failed", "http_status": http_status, "detail": payload.get("detail") or payload.get("fallback_reason") or ""}

        def rust_smoke():
            code = (
                "import json\n"
                "import tquant_rs\n"
                "from app.services.finance.rust_math import rust_available, rust_atr_wilder, rust_max_drawdown, rust_rank_ic, rust_rolling_mean, rust_rsi_wilder, rust_vwap, rust_math_metrics_snapshot\n"
                "payload = {\n"
                "    'module': tquant_rs.__name__,\n"
                "    'available': rust_available(),\n"
                "    'max_drawdown': rust_max_drawdown([100, 110, 90, 120]),\n"
                "    'rolling_mean': rust_rolling_mean([1, 2, 3, 4], 2),\n"
                "    'atr_wilder': rust_atr_wilder([10, 11, 12], [9, 9.5, 10], [9.5, 10.5, 11], 2),\n"
                "    'rsi_wilder': rust_rsi_wilder([1, 2, 3, 2, 4, 5], 3),\n"
                "    'vwap': rust_vwap([10, 11, 12], [100, 200, 300]),\n"
                "    'rank_ic': rust_rank_ic([3, 1, 2], [0.3, 0.1, 0.2]),\n"
                "    'metrics': rust_math_metrics_snapshot(),\n"
                "}\n"
                "print(json.dumps(payload))\n"
            )
            try:
                out = subprocess.check_output(
                    ["sudo", "docker", "exec", "-i", "tquant-app-mysql", "python", "-"],
                    input=code,
                    text=True,
                    timeout=20,
                )
                return json.loads(out.strip().splitlines()[-1])
            except Exception as exc:
                return {"available": False, "error": str(exc)}

        def quote_cache_snapshot():
            token = read_internal_token()
            warm = quote_cache_warmup()
            if not isinstance(warm, dict):
                warm = {
                    "ok": False,
                    "error": "quote_cache_warmup_returned_non_object",
                    "raw": repr(warm)[:200],
                }
            warm_symbols = []
            warm_symbols = [str(item).strip() for item in warm.get("symbols") or [] if len(str(item).strip()) == 6]
            warmup_coverage = warm.get("coverage") if isinstance(warm, dict) else {}
            warmup_missing = int(warmup_coverage.get("demand_miss_count") or warm.get("missing_count") or 0)
            try:
                redis_raw = subprocess.check_output(
                    ["sudo", "docker", "exec", "tquant-redis", "redis-cli", "--scan", "--pattern", "tquant:market:quote:*"],
                    text=True,
                    timeout=20,
                )
                redis_count = len([line for line in redis_raw.splitlines() if line.strip()])
            except Exception:
                redis_count = -1
            symbols = warm_symbols[:20]
            if not symbols:
                try:
                    code = (
                        "from sqlalchemy import select\n"
                        "from app.core.database import SessionLocal\n"
                        "from app.models.entities import DailyBarSnapshot\n"
                        "with SessionLocal() as db:\n"
                        "    latest = db.execute(select(DailyBarSnapshot.trade_date).order_by(DailyBarSnapshot.trade_date.desc()).limit(1)).scalar()\n"
                        "    rows = db.execute(select(DailyBarSnapshot.symbol).where(DailyBarSnapshot.trade_date == latest).order_by(DailyBarSnapshot.amount.desc()).limit(20)).scalars().all() if latest else []\n"
                        "print(','.join(str(item) for item in rows if item))\n"
                    )
                    out = subprocess.check_output(
                        ["sudo", "docker", "exec", "-i", "tquant-app-mysql", "python", "-"],
                        input=code,
                        text=True,
                        timeout=20,
                    )
                    symbols = [item.strip() for item in out.strip().split(",") if item.strip()]
                except Exception:
                    symbols = []
            if not symbols or not token:
                return {
                    "warmup": warm,
                    "redis_quote_keys": redis_count,
                    "symbols_checked": len(symbols),
                    "warmup_missing_count": warmup_missing,
                    "missing_count": warmup_missing,
                    "data_quality": "unavailable",
                }
            try:
                out = subprocess.check_output(
                    [
                        "sudo", "docker", "exec", "tquant-go-market-read-service", "wget", "-qO-",
                        "--header", "X-Internal-Service-Token: " + token,
                        "http://127.0.0.1:8092/api/market-read/v1/intraday-latest-batch?symbols=" + ",".join(symbols),
                    ],
                    text=True,
                    timeout=20,
                )
                payload = json.loads(out)
                if not isinstance(payload, dict):
                    return {
                        "warmup": warm,
                        "redis_quote_keys": redis_count,
                        "symbols_checked": len(symbols),
                        "warmup_missing_count": warmup_missing,
                        "missing_count": warmup_missing,
                        "data_quality": "unavailable",
                        "error": "market_read_batch_returned_non_object",
                        "raw": repr(payload)[:200],
                    }
                items = payload.get("items") or []
                batch_missing = len(payload.get("missing") or [])
                return {
                    "warmup": warm,
                    "redis_quote_keys": redis_count,
                    "symbols_checked": len(symbols),
                    "items_returned": len(items),
                    "warmup_missing_count": warmup_missing,
                    "batch_missing_count": batch_missing,
                    "missing_count": max(warmup_missing, batch_missing),
                    "data_quality": payload.get("data_quality"),
                }
            except Exception as exc:
                return {
                    "warmup": warm,
                    "redis_quote_keys": redis_count,
                    "symbols_checked": len(symbols),
                    "warmup_missing_count": warmup_missing,
                    "missing_count": warmup_missing,
                    "data_quality": "unavailable",
                    "error": str(exc),
                }

        def quote_cache_warmup():
            code = (
                "import json\n"
                "from app.core.database import SessionLocal\n"
                "from app.services.market_quote_cache_refresh import DEFAULT_LIMIT, MarketQuoteCacheRefreshService\n"
                "with SessionLocal() as db:\n"
                "    result = MarketQuoteCacheRefreshService(db).refresh(limit=DEFAULT_LIMIT)\n"
                "print(json.dumps(result, ensure_ascii=False, default=str))\n"
            )
            try:
                out = subprocess.check_output(
                    ["sudo", "docker", "exec", "-i", "tquant-app-mysql", "python", "-"],
                    input=code,
                    text=True,
                    timeout=90,
                )
                payload = json.loads(out.strip().splitlines()[-1])
                if isinstance(payload, dict):
                    return payload
                return {
                    "ok": False,
                    "error": "quote_cache_warmup_returned_non_object",
                    "raw": repr(payload)[:200],
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        token = login()
        quote_cache = quote_cache_snapshot()
        api_prewarm = prewarm_api_paths(token)
        time.sleep(2.0)
        go_bff_metrics_before = metrics("tquant-go-bff-gateway", 8091)
        go_market_metrics_before = metrics("tquant-go-market-read-service", 8092)
        api = [
            measure("readyz", "/readyz"),
            measure("monitor_bff", "/api/bff/v1/workspace/monitor?priority_limit=12&sector_limit=8&per_sector_limit=8&hedge_limit=4", token, capture_payload=True),
            measure("market_pulse", "/api/market/pulse", token),
            measure("priority_board", "/api/screeners/low-buy/priority-board?limit=12&refresh=cache", token, capture_payload=True),
            measure("watchlist_signals", "/api/watchlist/signals", token),
        ]
        go_scan = []
        scan_accept = measure_scan_accept()
        rust = rust_smoke()
        try:
            out = subprocess.check_output([
                "sudo", "docker", "exec", "tquant-go-scan-worker", "wget", "-qO-",
                "--header", "X-Internal-Service-Token: " + read_internal_token(),
                "http://127.0.0.1:8093/api/scan-worker/v1/status",
            ], text=True, timeout=10)
            go_scan.append({"status": json.loads(out)})
        except Exception as exc:
            go_scan.append({"error": str(exc)})

        thresholds = {
            "readyz": 100,
            "monitor_bff": 500,
            "market_pulse": 500,
            "priority_board": 500,
            "watchlist_signals": 600,
            "scan_worker_accept": 500,
        }
        failures = [
            {
                "name": item["name"],
                "p95_ms": item["p95_ms"],
                "threshold_ms": thresholds[item["name"]],
                "statuses": item["statuses"],
                "samples": item.get("samples") or [],
            }
            for item in api
            if item["p95_ms"] > thresholds[item["name"]] or item["statuses"] != [200]
        ]
        scan_statuses = set(scan_accept["statuses"])
        scan_has_real_failure = "failed" in scan_statuses
        scan_has_unexpected_status = bool(scan_statuses - {200, 202})
        if scan_accept["p95_ms"] > thresholds["scan_worker_accept"] or scan_has_real_failure or scan_has_unexpected_status:
            failures.append({
                "name": scan_accept["name"],
                "p95_ms": scan_accept["p95_ms"],
                "threshold_ms": thresholds["scan_worker_accept"],
                "statuses": scan_accept["statuses"],
                "notes": scan_accept.get("notes") or [],
            })
        if not rust.get("available") or int(rust.get("metrics", {}).get("hits") or 0) < 6:
            failures.append({
                "name": "rust_finance_math",
                "detail": rust.get("error") or "rust smoke did not hit all migrated functions",
            })
        warmup = quote_cache.get("warmup") if isinstance(quote_cache, dict) else {}
        warmup_coverage = warmup.get("coverage") if isinstance(warmup, dict) else {}
        if isinstance(warmup_coverage, dict) and warmup_coverage.get("coverage_below_target"):
            failures.append({"name": "quote_cache_warmup_coverage", "detail": quote_cache})
        if quote_cache.get("missing_count"):
            failures.append({"name": "quote_cache_batch_coverage", "detail": quote_cache})
        if quote_cache.get("symbols_checked") and quote_cache.get("data_quality") == "unavailable":
            failures.append({"name": "quote_cache_coverage", "detail": quote_cache})
        go_bff_metrics = metrics("tquant-go-bff-gateway", 8091)
        go_market_metrics = metrics("tquant-go-market-read-service", 8092)
        go_bff_metrics_delta = metric_delta(go_bff_metrics, go_bff_metrics_before)
        go_market_metrics_delta = metric_delta(go_market_metrics, go_market_metrics_before)
        observability = observability_assessment(go_bff_metrics_delta, go_market_metrics_delta, quote_cache)
        if not observability.get("ok"):
            failures.append({"name": "observability_alerts", "detail": observability})
        api_by_name = {item["name"]: item for item in api}
        monitor_payload_summary = api_by_name.get("monitor_bff", {}).get("payload_summary") or {}
        priority_payload_summary = api_by_name.get("priority_board", {}).get("payload_summary") or {}
        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "api_prewarm": api_prewarm,
            "api": api,
            "monitor_bff_sources": monitor_payload_summary.get("source_timings") or [],
            "priority_board_breakdown": priority_payload_summary,
            "go_bff_cache_hit_rate": observability.get("go_bff_cache_hit_rate"),
            "go_bff_partial_errors_by_source": observability.get("bff_partial", {}).get("partial_errors_by_source") or {},
            "go_scan_accept": scan_accept,
            "rust_finance_math": rust,
            "quote_cache_coverage": quote_cache,
            "go_bff_metrics_before": go_bff_metrics_before,
            "go_bff_metrics": go_bff_metrics,
            "go_bff_metrics_delta": go_bff_metrics_delta,
            "go_market_metrics_before": go_market_metrics_before,
            "go_market_metrics": go_market_metrics,
            "go_market_metrics_delta": go_market_metrics_delta,
            "observability": observability,
            "go_scan": go_scan,
            "app_metrics": fetch("/metrics")[2].decode(errors="replace")[-4000:],
            "failures": failures,
            "ok": not failures,
        }
        print(json.dumps(report, ensure_ascii=False))
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(script)
        remote_script = handle.name
    command = [
        "ssh",
        "-i",
        args.key,
        "-o",
        "StrictHostKeyChecking=no",
        f"{args.user}@{args.host}",
        f"BASE_URL={args.base_url!r} PROJECT_DIR={args.project_dir!r} SAMPLES={int(args.samples)} python3 -",
    ]
    completed = subprocess.run(
        command,
        input=Path(remote_script).read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": "remote measurement failed",
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    return json.loads(completed.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    raise SystemExit(main())
