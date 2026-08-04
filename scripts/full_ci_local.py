from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._ops import (
    ARTIFACTS,
    BACKEND,
    FRONTEND,
    NPM,
    ROOT,
    artifact_run_environment,
    generated_artifact_dir,
    python_command,
    run,
)


FRONTEND_TEST_TARGETS = [
    "dashboard",
    "runs",
    "run-detail",
    "repository-config",
    "feishu-resource-mapping",
    "credentials",
    "config-confirmation",
]


def main() -> None:
    output_dir = generated_artifact_dir("full-ci", ARTIFACTS)
    output_dir.mkdir(parents=True, exist_ok=True)

    run(python_command("-m", "ruff", "check", "scripts"), ROOT)
    run(python_command("-m", "ruff", "format", "--check", "scripts"), ROOT)
    run(python_command("-m", "pytest", "tests/test_smoke.py", "-q"), BACKEND)
    for layer in ("unit", "contract", "integration", "scenarios", "e2e"):
        run(python_command("-m", "pytest", f"tests/{layer}", "-q"), BACKEND)

    alembic_sql = output_dir / "alembic.sql"
    with alembic_sql.open("w", encoding="utf-8", newline="\n") as stream:
        run(
            python_command("-m", "alembic", "upgrade", "head", "--sql"),
            BACKEND,
            stdout=stream,
        )

    run([NPM, "run", "test", "--", *FRONTEND_TEST_TARGETS], FRONTEND)
    run([NPM, "run", "lint"], FRONTEND)
    run([NPM, "run", "typecheck"], FRONTEND)
    run([NPM, "run", "build"], FRONTEND)

    artifact_environment = artifact_run_environment()
    run(
        python_command(str(ROOT / "scripts" / "dependency_scan.py")),
        ROOT,
        env=artifact_environment,
    )
    run(
        python_command(str(ROOT / "scripts" / "secret_scan.py")),
        ROOT,
        env=artifact_environment,
    )
    run(["docker", "compose", "config"], ROOT)


if __name__ == "__main__":
    main()
