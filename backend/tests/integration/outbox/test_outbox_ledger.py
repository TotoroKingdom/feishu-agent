from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, OutboxMessage
from app.messaging.ledger import OutboxMessageConflictError, TransactionalOutboxStore


def make_store() -> tuple[TransactionalOutboxStore, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    return TransactionalOutboxStore(factory), factory


def test_outbox_deduplicates_and_rejects_conflicting_payloads() -> None:
    store, factory = make_store()

    first = store.enqueue_message(
        topic="report.publish",
        aggregate_type="run",
        aggregate_id="run-1",
        payload={"run_id": "run-1", "version": 1},
        dedupe_key="run-1:publish",
    )
    second = store.enqueue_message(
        topic="report.publish",
        aggregate_type="run",
        aggregate_id="run-1",
        payload={"run_id": "run-1", "version": 1},
        dedupe_key="run-1:publish",
    )

    assert first.id == second.id
    assert first.status == "pending"

    with pytest.raises(OutboxMessageConflictError):
        store.enqueue_message(
            topic="report.publish",
            aggregate_type="run",
            aggregate_id="run-1",
            payload={"run_id": "run-1", "version": 2},
            dedupe_key="run-1:publish",
        )

    with factory() as session:
        message = session.scalar(
            select(OutboxMessage).where(OutboxMessage.dedupe_key == "run-1:publish")
        )
        assert message is not None


def test_outbox_claim_ack_retry_and_dead_letter_flow() -> None:
    store, _ = make_store()
    message = store.enqueue_message(
        topic="report.publish",
        aggregate_type="run",
        aggregate_id="run-2",
        payload={"run_id": "run-2", "version": 1},
        dedupe_key="run-2:publish",
        available_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )

    claimed = store.claim_next_message(
        worker_id="worker-1",
        lease_seconds=45,
        now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    assert claimed is not None
    assert claimed.id == message.id
    assert claimed.status == "claimed"
    assert claimed.attempt_count == 1
    assert claimed.created_at is not None

    acked = store.ack_message(
        message_id=claimed.id,
        provider_request_id="req-1",
        external_message_id="msg-1",
    )
    assert acked.status == "published"
    assert acked.published_at is not None
    assert acked.external_message_id == "msg-1"

    retry_message = store.enqueue_message(
        topic="report.publish",
        aggregate_type="run",
        aggregate_id="run-3",
        payload={"run_id": "run-3", "version": 1},
        dedupe_key="run-3:publish",
        available_at=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    claimed_retry = store.claim_next_message(
        worker_id="worker-2",
        now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    assert claimed_retry is not None
    assert claimed_retry.id == retry_message.id
    dead_lettered = store.retry_message(
        message_id=claimed_retry.id,
        error_class="provider_error",
        error_summary="temporary failure",
        max_attempts=1,
    )
    assert dead_lettered.status == "dead_lettered"
    assert dead_lettered.dead_lettered_at is not None
