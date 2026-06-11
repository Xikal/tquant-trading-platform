from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: int = 120) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return CommandResult(" ".join(command), 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            " ".join(command),
            124,
            exc.stdout or "",
            exc.stderr or "command timed out",
        )
    return CommandResult(
        " ".join(command),
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
