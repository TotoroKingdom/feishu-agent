from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.agent.checkpoint import open_postgres_checkpointer
from app.agent.runtime import WorkflowRuntime, WorkflowWorker
from app.agent.state import thread_id_for_run
from app.core.config import Settings
from app.db.models import HumanApproval, MetricSnapshot, Project, ReportRun, RunStatusHistory
from app.domain.runs import RunCreationService


def test_postgres_checkpoint_round_trip_and_worker_restart() -> None:
    root_env = Path(__file__).resolve().parents[4] / ".env"
    settings = Settings(_env_file=root_env)
    backend_root = Path(__file__).resolve().parents[3]
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"postgres unavailable: {exc}")

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_root,
        check=True,
    )

    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with open_postgres_checkpointer(settings.database_url) as saver:
        saver.setup()
        runtime = WorkflowRuntime(factory, saver)
        worker = WorkflowWorker(factory, saver)

        with factory() as session:
            project = Project(name="Demo PG", timezone="Asia/Shanghai")
            session.add(project)
            session.flush()
            run = RunCreationService(session).create_run(
                project.id,
                "2026-W30",
                date(2026, 7, 20),
                date(2026, 7, 27),
            )
            session.commit()
            run_id = run.id
            thread_id = thread_id_for_run(run_id)

        try:
            started = runtime.start(run_id)
            assert started.status == "waiting"
            assert started.thread_id == thread_id
            assert worker.recover_waiting_runs() == [run_id]

            restarted_worker = WorkflowWorker(factory, saver)
            assert restarted_worker.recover_waiting_runs() == [run_id]

            resumed = restarted_worker.resume(
                run_id,
                {
                    "action": "approve_generation",
                    "challenge_id": started.snapshot.values["approval"]["challenge_id"],
                    "approval_revision": started.snapshot.values["approval"]["approval_revision"],
                    "presented_hash": started.snapshot.values["scope"]["scope_hash"],
                    "actor_id": "local-demo",
                },
            )
            publish_resumed = restarted_worker.resume(
                run_id,
                {
                    "action": "approve_publish",
                    "challenge_id": resumed.snapshot.values["approval"]["challenge_id"],
                    "approval_revision": resumed.snapshot.values["approval"]["approval_revision"],
                    "presented_hash": resumed.snapshot.values["publish"]["plan_hash"],
                    "actor_id": "local-demo",
                },
            )
            assert resumed.status == "waiting"
            assert publish_resumed.status == "completed"

            snapshot = restarted_worker.inspect(run_id)
            assert snapshot is not None
            assert snapshot.values["current_stage"] == "publish_approved"
            assert snapshot.values["current_node"] == "complete_run"
            assert isinstance(snapshot.values["source_batch_refs"], list)
            assert len(snapshot.values["source_batch_refs"]) == 2
            assert snapshot.values["normalized_snapshot_ref"]
            assert snapshot.values["validation_result_ref"]
            assert snapshot.values["metrics_ref"]

            with factory() as session:
                run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
                metric_row = session.scalar(select(MetricSnapshot).where(MetricSnapshot.run_id == run_id))
                history_rows = session.scalars(
                    select(RunStatusHistory)
                    .where(RunStatusHistory.run_id == run_id)
                    .order_by(RunStatusHistory.id)
                ).all()
                assert run_row is not None
                assert run_row.thread_id == thread_id
                assert run_row.status == "completed"
                assert run_row.current_stage == "publish_approved"
                assert run_row.scope_revision == 1
                assert [row.to_status for row in history_rows] == ["waiting", "waiting", "completed"]
                assert metric_row is not None
        finally:
            saver.delete_thread(thread_id)
            with factory() as session:
                session.query(HumanApproval).filter(HumanApproval.run_id == run_id).delete()
                session.query(RunStatusHistory).filter(RunStatusHistory.run_id == run_id).delete()
                session.query(ReportRun).filter(ReportRun.id == run_id).delete()
                session.query(Project).filter(Project.id == project.id).delete()
                session.commit()
