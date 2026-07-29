from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import CallbackEvent, OutboxMessage, new_id
from app.domain.source import canonical_json_hash

SessionFactory = Callable[[], Session]

DEFAULT_LEASE_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3


class CallbackEventConflictError(ValueError):
    pass


class OutboxMessageConflictError(ValueError):
    pass


class CallbackInboxStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def record_callback_event(
        self,
        *,
        provider: str,
        external_event_id: str,
        event_type: str,
        payload: Mapping[str, object],
        actor_id: str,
        run_id: str | None = None,
    ) -> CallbackEvent:
        payload_hash = canonical_json_hash(payload)
        with self._session_factory() as session:
            existing = session.scalar(
                select(CallbackEvent).where(
                    CallbackEvent.provider == provider,
                    CallbackEvent.external_event_id == external_event_id,
                )
            )
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    raise CallbackEventConflictError(
                        "callback event payload hash mismatch for existing inbox record"
                    )
                return existing

            event = CallbackEvent(
                provider=provider,
                external_event_id=external_event_id,
                event_type=event_type,
                payload_hash=payload_hash,
                actor_id=actor_id,
                run_id=run_id,
                status="received",
                attempt_count=0,
                received_at=datetime.now(UTC),
                claimed_at=None,
                claimed_by=None,
                lease_expires_at=None,
                next_attempt_at=None,
                processed_at=None,
                dead_lettered_at=None,
                last_error_class=None,
                last_error_summary=None,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def claim_next_callback_event(
        self,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> CallbackEvent | None:
        current_time = _normalize_datetime(now)
        lease_expires_at = current_time + timedelta(seconds=lease_seconds)
        with self._session_factory() as session:
            event = session.scalar(
                select(CallbackEvent)
                .where(
                    or_(
                        CallbackEvent.status.in_(("received", "retry_pending")),
                        (
                            (CallbackEvent.status == "claimed")
                            & (
                                CallbackEvent.lease_expires_at.is_(None)
                                | (CallbackEvent.lease_expires_at <= current_time)
                            )
                        ),
                    ),
                    or_(
                        CallbackEvent.next_attempt_at.is_(None),
                        CallbackEvent.next_attempt_at <= current_time,
                    ),
                )
                .order_by(CallbackEvent.received_at, CallbackEvent.id)
                .limit(1)
            )
            if event is None:
                return None
            event.status = "claimed"
            event.attempt_count += 1
            event.claimed_at = current_time
            event.claimed_by = worker_id
            event.lease_expires_at = lease_expires_at
            event.next_attempt_at = None
            session.commit()
            session.refresh(event)
            return event

    def ack_callback_event(self, event_id: int) -> CallbackEvent:
        return self.mark_callback_event_processed(event_id)

    def mark_callback_event_processed(
        self, event_id: int, *, processed_at: datetime | None = None
    ) -> CallbackEvent:
        with self._session_factory() as session:
            event = session.get(CallbackEvent, event_id)
            if event is None:
                raise ValueError(f"unknown callback event id: {event_id}")
            event.status = "processed"
            event.processed_at = processed_at or datetime.now(UTC)
            event.lease_expires_at = None
            event.claimed_at = None
            event.claimed_by = None
            session.commit()
            session.refresh(event)
            return event

    def mark_callback_event_failed(
        self,
        event_id: int,
        *,
        error_class: str,
        error_summary: str,
        dead_letter: bool = False,
    ) -> CallbackEvent:
        with self._session_factory() as session:
            event = session.get(CallbackEvent, event_id)
            if event is None:
                raise ValueError(f"unknown callback event id: {event_id}")
            event.last_error_class = error_class
            event.last_error_summary = error_summary
            event.claimed_at = None
            event.claimed_by = None
            event.lease_expires_at = None
            if dead_letter:
                event.status = "dead_lettered"
                event.dead_lettered_at = datetime.now(UTC)
            else:
                event.status = "failed"
            session.commit()
            session.refresh(event)
            return event

    def retry_callback_event(
        self,
        *,
        event_id: int,
        error_class: str,
        error_summary: str,
        delay_seconds: int = 0,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> CallbackEvent:
        with self._session_factory() as session:
            event = session.get(CallbackEvent, event_id)
            if event is None:
                raise ValueError(f"unknown callback event id: {event_id}")
            if event.status not in {"claimed", "received", "retry_pending"}:
                raise ValueError("callback event cannot be retried from its current status")
            event.last_error_class = error_class
            event.last_error_summary = error_summary
            event.claimed_at = None
            event.claimed_by = None
            event.lease_expires_at = None
            if event.attempt_count >= max_attempts:
                event.status = "dead_lettered"
                event.dead_lettered_at = datetime.now(UTC)
                event.next_attempt_at = None
            else:
                event.status = "retry_pending"
                event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            session.commit()
            session.refresh(event)
            return event

    def dead_letter_callback_event(
        self,
        *,
        event_id: int,
        error_class: str,
        error_summary: str,
    ) -> CallbackEvent:
        with self._session_factory() as session:
            event = session.get(CallbackEvent, event_id)
            if event is None:
                raise ValueError(f"unknown callback event id: {event_id}")
            event.status = "dead_lettered"
            event.dead_lettered_at = datetime.now(UTC)
            event.last_error_class = error_class
            event.last_error_summary = error_summary
            event.claimed_at = None
            event.claimed_by = None
            event.lease_expires_at = None
            event.next_attempt_at = None
            session.commit()
            session.refresh(event)
            return event


class TransactionalOutboxStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def enqueue_message(
        self,
        *,
        topic: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Mapping[str, object],
        dedupe_key: str,
        available_at: datetime | None = None,
    ) -> OutboxMessage:
        normalized_payload = dict(payload)
        payload_hash = canonical_json_hash(normalized_payload)
        with self._session_factory() as session:
            existing = session.scalar(
                select(OutboxMessage).where(OutboxMessage.dedupe_key == dedupe_key)
            )
            if existing is not None:
                if canonical_json_hash(existing.payload) != payload_hash:
                    raise OutboxMessageConflictError(
                        "outbox message payload hash mismatch for existing dedupe key"
                    )
                return existing

            message = OutboxMessage(
                id=new_id(),
                topic=topic,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=normalized_payload,
                dedupe_key=dedupe_key,
                status="pending",
                attempt_count=0,
                available_at=available_at or datetime.now(UTC),
                claimed_at=None,
                claimed_by=None,
                lease_expires_at=None,
                provider_request_id=None,
                external_message_id=None,
                published_at=None,
                dead_lettered_at=None,
                last_error_class=None,
                last_error_summary=None,
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def claim_next_message(
        self,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> OutboxMessage | None:
        current_time = _normalize_datetime(now)
        lease_expires_at = current_time + timedelta(seconds=lease_seconds)
        with self._session_factory() as session:
            message = session.scalar(
                select(OutboxMessage)
                .where(
                    or_(
                        OutboxMessage.status == "pending",
                        (
                            (OutboxMessage.status == "claimed")
                            & (
                                OutboxMessage.lease_expires_at.is_(None)
                                | (OutboxMessage.lease_expires_at <= current_time)
                            )
                        ),
                        OutboxMessage.status == "retry_pending",
                    ),
                    OutboxMessage.available_at <= current_time,
                )
                .order_by(OutboxMessage.available_at, OutboxMessage.created_at, OutboxMessage.id)
                .limit(1)
            )
            if message is None:
                return None
            message.status = "claimed"
            message.attempt_count += 1
            message.claimed_at = current_time
            message.claimed_by = worker_id
            message.lease_expires_at = lease_expires_at
            session.commit()
            session.refresh(message)
            return message

    def ack_message(
        self,
        *,
        message_id: str,
        provider_request_id: str | None = None,
        external_message_id: str | None = None,
    ) -> OutboxMessage:
        with self._session_factory() as session:
            message = session.get(OutboxMessage, message_id)
            if message is None:
                raise ValueError(f"unknown outbox message id: {message_id}")
            if message.status != "claimed":
                raise ValueError("outbox message must be claimed before ack")
            message.status = "published"
            message.published_at = datetime.now(UTC)
            message.provider_request_id = provider_request_id
            message.external_message_id = external_message_id
            message.claimed_at = None
            message.claimed_by = None
            message.lease_expires_at = None
            session.commit()
            session.refresh(message)
            return message

    def retry_message(
        self,
        *,
        message_id: str,
        error_class: str,
        error_summary: str,
        delay_seconds: int = 0,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> OutboxMessage:
        with self._session_factory() as session:
            message = session.get(OutboxMessage, message_id)
            if message is None:
                raise ValueError(f"unknown outbox message id: {message_id}")
            if message.status not in {"claimed", "pending", "retry_pending"}:
                raise ValueError("outbox message cannot be retried from its current status")
            message.last_error_class = error_class
            message.last_error_summary = error_summary
            message.claimed_at = None
            message.claimed_by = None
            message.lease_expires_at = None
            if message.attempt_count >= max_attempts:
                message.status = "dead_lettered"
                message.dead_lettered_at = datetime.now(UTC)
                message.available_at = datetime.now(UTC)
            else:
                message.status = "retry_pending"
                message.available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            session.commit()
            session.refresh(message)
            return message

    def dead_letter_message(
        self,
        *,
        message_id: str,
        error_class: str,
        error_summary: str,
    ) -> OutboxMessage:
        with self._session_factory() as session:
            message = session.get(OutboxMessage, message_id)
            if message is None:
                raise ValueError(f"unknown outbox message id: {message_id}")
            message.status = "dead_lettered"
            message.dead_lettered_at = datetime.now(UTC)
            message.last_error_class = error_class
            message.last_error_summary = error_summary
            message.claimed_at = None
            message.claimed_by = None
            message.lease_expires_at = None
            session.commit()
            session.refresh(message)
            return message


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
