#!/usr/bin/env python
"""Task runner for the ingestion subsystem — the `make` equivalent for this repo.

`make` is not installed on the Windows development machine and the repo has no
Makefile, so tasks run through the same interpreter that runs the app:

    python tasks.py test     # pytest, ingestion suite, excludes @live
    python tasks.py lint     # ruff check
    python tasks.py fmt      # ruff format
    python tasks.py check    # lint + test

From the backend directory, using the project venv:

    .venv/Scripts/python.exe tasks.py check      # Windows
    .venv/bin/python tasks.py check              # POSIX

mypy is deliberately absent: type checking is deferred and the codebase is not
annotated. The per-phase checklist covers tests and lint only.
"""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).parent
PY = sys.executable

TASKS = {
    "test":  [PY, "-m", "pytest"],
    "lint":  [PY, "-m", "ruff", "check", "."],
    "fmt":   [PY, "-m", "ruff", "format", "."],
    "live":  [PY, "-m", "pytest", "-m", "live"],
}


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd[1:])}", flush=True)
    return subprocess.call(cmd, cwd=BACKEND)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("tasks:", ", ".join([*TASKS, "check"]))
        return 2

    name = sys.argv[1]
    if name == "check":
        return run(TASKS["lint"]) or run(TASKS["test"])
    if name not in TASKS:
        print(f"unknown task {name!r}; available: {', '.join([*TASKS, 'check'])}")
        return 2
    return run(TASKS[name])


if __name__ == "__main__":
    raise SystemExit(main())
