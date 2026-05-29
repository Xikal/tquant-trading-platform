from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import init_db
from app.core.config import get_settings
from app.services.low_buy_materialization import warm_main_force_shadow_observations
from app.services.low_buy.main_force_model_shadow import summarize_main_force_shadow
from app.core.database import SessionLocal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="主力模型 Shadow 观测预热")
    parser.add_argument(
        "--strategies",
        default=get_settings().main_force_model_allowed_strategies,
        help="逗号分隔策略列表，默认使用 MAIN_FORCE_MODEL_ALLOWED_STRATEGIES。",
    )
    parser.add_argument("--limit", type=int, default=80, help="每个策略最多记录候选数，上限 80。")
    parser.add_argument("--scan-limit", type=int, default=480, help="回退实时扫描上限，上限 480。")
    parser.add_argument("--lookback-days", type=int, default=365, help="输出摘要回看天数。")
    parser.add_argument("--json-output", default="", help="可选 JSON 报告输出路径。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    init_db()
    strategies = [item.strip() for item in str(args.strategies or "").split(",") if item.strip()]
    warmup = warm_main_force_shadow_observations(
        strategies=strategies,
        limit=args.limit,
        scan_limit=args.scan_limit,
        reason="main_force_shadow_cli_warmup",
    )
    with SessionLocal() as db:
        summary = summarize_main_force_shadow(db, lookback_days=args.lookback_days)
        db.commit()
    payload = {
        "ok": bool(warmup.get("ok")),
        "warmup": warmup,
        "summary": summary,
        "production_effect": "readonly_shadow",
        "production_parameter_change": False,
    }
    if args.json_output:
        path = Path(args.json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
