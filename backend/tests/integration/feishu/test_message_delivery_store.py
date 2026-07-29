from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, FeishuMessageDelivery
from app.providers.feishu import FeishuMessageDeliveryConflictError, FeishuMessageDeliveryStore


def _factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False)


def test_message_delivery_store_deduplicates_and_updates_status() -> None:
    factory = _factory()
    store = FeishuMessageDeliveryStore(factory)

    first = store.record_delivery(
        run_id="run-001",
        onboarding_session_id=None,
        purpose="generation_approval",
        revision=1,
        recipient_type="user",
        recipient_id="ou_123",
        content_hash="hash-001",
        idempotency_key="key-001",
    )
    second = store.record_delivery(
        run_id="run-001",
        onboarding_session_id=None,
        purpose="generation_approval",
        revision=1,
        recipient_type="user",
        recipient_id="ou_123",
        content_hash="hash-001",
        idempotency_key="key-001",
    )

    assert first.id == second.id

    with factory() as session:
        row = session.scalar(
            select(FeishuMessageDelivery).where(FeishuMessageDelivery.id == first.id)
        )
        assert row is not None
        assert row.status == "pending"

    sent = store.mark_sent(first.id, external_message_id="msg-123")
    failed = store.mark_failed(first.id, error_summary="temporary platform error")

    assert sent.status == "sent"
    assert sent.external_message_id == "msg-123"
    assert failed.status == "failed"
    assert failed.attempt_count == 1


def test_message_delivery_store_rejects_conflicting_payloads_for_same_key() -> None:
    store = FeishuMessageDeliveryStore(_factory())

    store.record_delivery(
        run_id="run-001",
        onboarding_session_id=None,
        purpose="publish_approval",
        revision=2,
        recipient_type="chat",
        recipient_id="chat-001",
        content_hash="hash-a",
        idempotency_key="key-002",
    )

    try:
        store.record_delivery(
            run_id="run-001",
            onboarding_session_id=None,
            purpose="publish_approval",
            revision=2,
            recipient_type="chat",
            recipient_id="chat-001",
            content_hash="hash-b",
            idempotency_key="key-002",
        )
    except FeishuMessageDeliveryConflictError as error:
        assert "payload hash mismatch" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected conflicting payload to be rejected")
