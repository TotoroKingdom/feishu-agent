from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.approvals import PublishApprovalStore
from app.db.models import Base, Project
from app.domain.runs import RunCreationService


def test_publish_approval_store_loads_approval_by_challenge() -> None:
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
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )

    store = PublishApprovalStore(factory)
    created = store.ensure_pending_publish_approval(
        run_id=run.id,
        revision=1,
        plan_hash="plan-hash",
        challenge_id="publish-challenge",
    )

    loaded = store.load_approval_by_challenge("publish-challenge")

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.approval_type == "publish"
