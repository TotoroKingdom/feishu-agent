from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._ops import ARTIFACTS, NPM, ROOT, run


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    run(["docker", "compose", "build", "backend", "frontend", "nginx"], ROOT)
    output_dir = ARTIFACTS / "dependency-scan"
    output_dir.mkdir(exist_ok=True)
    backend_check = output_dir / "backend.pip-check.txt"
    with backend_check.open("w", encoding="utf-8", newline="\n") as stream:
        run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "backend",
                "python",
                "-m",
                "pip",
                "check",
            ],
            ROOT,
            stdout=stream,
        )

    frontend_tree = output_dir / "frontend.npm-ls.txt"
    with frontend_tree.open("w", encoding="utf-8", newline="\n") as stream:
        run([NPM, "ls", "--omit=dev", "--depth=0"], ROOT / "frontend", stdout=stream)


if __name__ == "__main__":
    main()
