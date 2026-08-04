from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._ops import ARTIFACTS, ROOT, generated_artifact_dir


OUTPUT_DIR = generated_artifact_dir("recovery-drill", ARTIFACTS)
BACKUP_PATH = OUTPUT_DIR / "postgres-backup.sql"
SEED_PATH = OUTPUT_DIR / "seed-state.json"


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    stdin: object | None = None,
    stdout: object | None = None,
) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True, stdin=stdin, stdout=stdout)


def run_capture(
    command: list[str], *, cwd: Path = ROOT, stdin: object | None = None
) -> str:
    print(f"$ {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def wait_for_backend() -> None:
    probe = [
        "docker",
        "compose",
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read().decode())",
    ]
    deadline = time.monotonic() + 120
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            output = run_capture(probe)
            if '"ok"' in output or "ok" in output:
                return
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(3)
    raise SystemExit(f"backend did not become healthy: {last_error}")


def wait_for_postgres() -> None:
    probe = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "pg_isready",
        "-U",
        "feishu_agent",
        "-d",
        "feishu_agent",
    ]
    deadline = time.monotonic() + 120
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            run_capture(probe)
            return
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(3)
    raise SystemExit(f"postgres did not become ready: {last_error}")


def seed_demo_state() -> dict[str, str]:
    code = r"""
import json
from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Project
from app.domain.runs import RunCreationService

settings = Settings()
engine = create_engine(settings.database_url)
factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
with factory() as session:
    project = session.scalar(select(Project).where(Project.name == "Recovery Drill"))
    if project is None:
        project = Project(name="Recovery Drill", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
    run = RunCreationService(session).create_run(
        project.id,
        "2026-W31",
        date(2026, 7, 27),
        date(2026, 8, 3),
    )
    session.commit()
    print(json.dumps({"project_id": project.id, "run_id": run.id, "period_key": run.period_key}))
"""
    output = run_capture(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", code]
    )
    payload = json.loads(output.strip().splitlines()[-1])
    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def backup_database() -> None:
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BACKUP_PATH.open("w", encoding="utf-8", newline="\n") as stream:
        run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "feishu_agent",
                "-d",
                "feishu_agent",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
            ],
            stdout=stream,
        )


def restore_database() -> None:
    with BACKUP_PATH.open("r", encoding="utf-8") as stream:
        run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "feishu_agent",
                "-d",
                "feishu_agent",
            ],
            stdin=stream,
        )


def verify_restored_state(expected_run_id: str) -> None:
    code = rf"""
import json
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Project, ReportRun

settings = Settings()
engine = create_engine(settings.database_url)
factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
with factory() as session:
    project = session.scalar(select(Project).where(Project.name == "Recovery Drill"))
    run = session.scalar(select(ReportRun).where(ReportRun.id == {expected_run_id!r}))
    assert project is not None
    assert run is not None
    print(json.dumps({{"project_id": project.id, "run_id": run.id, "status": run.status}}))
"""
    output = run_capture(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", code]
    )
    payload = json.loads(output.strip().splitlines()[-1])
    assert payload["run_id"] == expected_run_id


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--build",
            "postgres",
            "redis",
            "backend",
            "frontend",
            "nginx",
        ]
    )
    wait_for_postgres()
    wait_for_backend()
    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "backend",
            "python",
            "-m",
            "alembic",
            "upgrade",
            "head",
        ]
    )
    seed = seed_demo_state()
    backup_database()

    run(["docker", "compose", "down", "-v"])
    run(["docker", "compose", "up", "-d", "--build", "postgres", "redis"])
    wait_for_postgres()
    restore_database()
    run(["docker", "compose", "up", "-d", "--build", "backend", "frontend", "nginx"])
    wait_for_postgres()
    wait_for_backend()
    verify_restored_state(seed["run_id"])


if __name__ == "__main__":
    main()
