#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detach a process and print its pid.")
    parser.add_argument("--cwd", default=".", help="Working directory")
    parser.add_argument("--log", required=True, help="Combined stdout/stderr log file")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing command to execute")

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            command,
            cwd=args.cwd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
