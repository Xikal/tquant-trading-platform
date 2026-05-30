from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导出 FastAPI OpenAPI schema")
    parser.add_argument("--output", default="docs/contracts/openapi.json")
    parser.add_argument("--hash-output", default="docs/contracts/openapi.hash")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from app.main import app

    schema = app.openapi()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
    output.write_text(payload + "\n", encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    hash_output = Path(args.hash_output)
    hash_output.parent.mkdir(parents=True, exist_ok=True)
    hash_output.write_text(digest + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
