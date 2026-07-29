from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, CallbackEvent, Project
from app.domain.runs import RunCreationService
from app.messaging.ledger import CallbackEventConflictError, CallbackInboxStore


def make_store() -> tuple[CallbackInboxStore, sessionmaker[Session], str]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Inbox", timezone="Asia/Shanghai")
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
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    return CallbackInboxStore(factory), factory, run_id


def test_callback_inbox_deduplicates_and_rejects_conflicting_payloads() -> None:
    store, factory, run_id = make_store()

    first = store.record_callback_event(
        provider="feishu",
        external_event_id="evt-1",
        event_type="card_action",
        payload={"action": "approve", "revision": 1},
        actor_id="ou-1",
        run_id=run_id,
    )
    second = store.record_callback_event(
        provider="feishu",
        external_event_id="evt-1",
        event_type="card_action",
        payload={"action": "approve", "revision": 1},
        actor_id="ou-1",
        run_id=run_id,
    )

    assert first.id == second.id
    assert first.status == "received"

    with pytest.raises(CallbackEventConflictError):
        store.record_callback_event(
            provider="feishu",
            external_event_id="evt-1",
            event_type="card_action",
            payload={"action": "reject", "revision": 1},
            actor_id="ou-1",
            run_id=run_id,
        )

    with factory() as session:
        event = session.scalar(select(CallbackEvent).where(CallbackEvent.provider == "feishu"))
        assert event is not None
        assert event.status == "received"


def test_callback_inbox_claim_ack_and_dead_letter_flow() -> None:
    store, _, run_id = make_store()
    event = store.record_callback_event(
        provider="feishu",
        external_event_id="evt-2",
        event_type="card_action",
        payload={"action": "approve", "revision": 2},
        actor_id="ou-2",
        run_id=run_id,
    )

    claimed = store.claim_next_callback_event(
        worker_id="worker-1",
        lease_seconds=30,
        now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    assert claimed is not None
    assert claimed.id == event.id
    assert claimed.status == "claimed"
    assert claimed.attempt_count == 1
    assert claimed.claimed_by == "worker-1"
    assert claimed.lease_expires_at == datetime(2026, 7, 29, 10, 0, 30)

    acked = store.ack_callback_event(event_id=claimed.id)
    assert acked.status == "processed"
    assert acked.processed_at is not None

    retry_event = store.record_callback_event(
        provider="feishu",
        external_event_id="evt-3",
        event_type="card_action",
        payload={"action": "approve", "revision": 3},
        actor_id="ou-3",
        run_id=run_id,
    )
    retried = store.claim_next_callback_event(
        worker_id="worker-2",
        now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    assert retried is not None
    assert retried.id == retry_event.id
    dead_lettered = store.retry_callback_event(
        event_id=retried.id,
        error_class="transient_timeout",
        error_summary="upstream timeout",
        max_attempts=1,
    )
    assert dead_lettered.status == "dead_lettered"
    assert dead_lettered.dead_lettered_at is not None
