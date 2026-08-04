from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ARTIFACTS = ROOT / "artifacts"
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
ARTIFACT_RUN_ID_ENV = "FEISHU_AGENT_ARTIFACT_RUN_ID"
_ARTIFACT_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
_WINDOWS_RESERVED_NAMES = {
    "AUX",
    "CON",
    "NUL",
    "PRN",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _resolve_artifact_run_id() -> str:
    configured = os.environ.get(ARTIFACT_RUN_ID_ENV)
    if configured is not None:
        windows_basename = configured.split(".", maxsplit=1)[0].upper()
        if (
            _ARTIFACT_RUN_ID_PATTERN.fullmatch(configured) is None
            or configured.endswith(".")
            or windows_basename in _WINDOWS_RESERVED_NAMES
        ):
            raise ValueError(
                f"{ARTIFACT_RUN_ID_ENV} must be a portable directory name containing only "
                "letters, numbers, '.', '_', '+', or '-'"
            )
        return configured
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")


ARTIFACT_RUN_ID = _resolve_artifact_run_id()


def generated_artifact_dir(category: str, artifact_root: Path = ARTIFACTS) -> Path:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", category) is None:
        raise ValueError(
            "artifact category must use lowercase letters, numbers, or hyphens"
        )
    return artifact_root / "generated" / ARTIFACT_RUN_ID / category


def artifact_run_environment() -> dict[str, str]:
    return {ARTIFACT_RUN_ID_ENV: ARTIFACT_RUN_ID}


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
