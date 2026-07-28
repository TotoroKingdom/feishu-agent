"""Run the repository checks that mirror the base CI workflow."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"


def run(command: list[str], cwd: Path) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    backend_python = [sys.executable]
    run([*backend_python, "-m", "ruff", "check", "."], BACKEND)
    run([*backend_python, "-m", "ruff", "format", "--check", "."], BACKEND)
    run([*backend_python, "-m", "mypy", "app"], BACKEND)
    run([*backend_python, "-m", "pytest", "tests", "-q"], BACKEND)
    run([*backend_python, "-m", "alembic", "upgrade", "head", "--sql"], BACKEND)

    run([NPM, "run", "lint"], FRONTEND)
    run([NPM, "run", "typecheck"], FRONTEND)
    run([NPM, "run", "build"], FRONTEND)

    run(["docker", "compose", "config"], ROOT)


if __name__ == "__main__":
    main()
