from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.models import Base, Project, ReportRun, ScheduleConfig
from app.scheduler.worker import SchedulerWorker


def test_scheduler_worker_creates_at_most_one_run_for_a_due_schedule() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        session.add(
            ScheduleConfig(
                project_id=project.id,
                cron_expression="0 9 * * 1",
                timezone="Asia/Shanghai",
                enabled=True,
                misfire_policy="fire_once",
                next_fire_at=datetime(2026, 7, 27, 1, 0, tzinfo=UTC),
                last_fire_at=None,
                revision=1,
            )
        )
        session.commit()
        schedule_id = session.scalar(select(ScheduleConfig.id))
        assert schedule_id is not None

    worker = SchedulerWorker(factory, settings=Settings(_env_file=None, app_profile="local-demo"))
    first = worker.tick(now=datetime(2026, 7, 27, 1, 5, tzinfo=UTC))
    second = worker.tick(now=datetime(2026, 7, 27, 1, 5, tzinfo=UTC))

    assert first.created_run_ids == [first.created_run_ids[0]]
    assert second.created_run_ids == []

    with factory() as session:
        run = session.scalar(select(ReportRun))
        schedule = session.scalar(select(ScheduleConfig))
        assert run is not None
        assert run.period_key == "2026-W30"
        assert run.period_start.isoformat() == "2026-07-20"
        assert run.period_end.isoformat() == "2026-07-27"
        assert schedule is not None
        assert schedule.last_fire_at is not None
        assert schedule.next_fire_at is not None


def test_scheduler_worker_skips_misfires_when_policy_requests_skip() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        session.add(
            ScheduleConfig(
                project_id=project.id,
                cron_expression="0 9 * * 1",
                timezone="Asia/Shanghai",
                enabled=True,
                misfire_policy="skip",
                next_fire_at=datetime(2026, 7, 20, 1, 0, tzinfo=UTC),
                last_fire_at=None,
                revision=1,
            )
        )
        session.commit()

    worker = SchedulerWorker(factory, settings=Settings(_env_file=None, app_profile="local-demo"))
    result = worker.tick(now=datetime(2026, 7, 27, 1, 5, tzinfo=UTC))

    assert result.created_run_ids == []
    with factory() as session:
        assert session.scalar(select(ReportRun)) is None
        schedule = session.scalar(select(ScheduleConfig))
        assert schedule is not None
        assert schedule.last_fire_at is None
        assert schedule.next_fire_at is not None
