from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ARTIFACTS = ROOT / "artifacts"
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"


def run(
    command: list[str],
    cwd: Path = ROOT,
    *,
    env: Mapping[str, str] | None = None,
    stdout: object | None = None,
    stdin: object | None = None,
) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    merged_env = os.environ.copy()
    if env is not None:
        merged_env.update(env)
    subprocess.run(
        command, cwd=cwd, env=merged_env, check=True, stdout=stdout, stdin=stdin
    )


def python_command(*parts: str) -> list[str]:
    return [sys.executable, *parts]
