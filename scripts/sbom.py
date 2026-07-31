from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._ops import ARTIFACTS, ROOT, run


IMAGES = [
    ("backend", "local://feishu-agent/backend:latest"),
    ("frontend", "local://feishu-agent/frontend:latest"),
    ("nginx", "local://feishu-agent/nginx:latest"),
]


def main() -> None:
    output_dir = ARTIFACTS / "sbom"
    output_dir.mkdir(parents=True, exist_ok=True)
    run(["docker", "compose", "build", "backend", "frontend", "nginx"], ROOT)

    for name, image in IMAGES:
        output = output_dir / f"{name}.sbom.json"
        run(
            [
                "docker",
                "scout",
                "sbom",
                "--format",
                "json",
                "--output",
                str(output),
                image,
            ],
            ROOT,
        )


if __name__ == "__main__":
    main()
