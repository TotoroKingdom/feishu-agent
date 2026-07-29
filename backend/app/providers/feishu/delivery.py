from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeishuMessageDelivery, new_id

SessionFactory = Callable[[], Session]


class FeishuMessageDeliveryConflictError(ValueError):
    pass


class FeishuMessageDeliveryStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def record_delivery(
        self,
        *,
        run_id: str | None,
        onboarding_session_id: str | None,
        purpose: str,
        revision: int,
        recipient_type: str,
        recipient_id: str,
        content_hash: str,
        idempotency_key: str,
        status: str = "pending",
        external_message_id: str | None = None,
    ) -> FeishuMessageDelivery:
        with self._session_factory() as session:
            existing = session.scalar(
                select(FeishuMessageDelivery).where(
                    FeishuMessageDelivery.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.content_hash != content_hash:
                    raise FeishuMessageDeliveryConflictError(
                        "feishu message delivery payload hash mismatch"
                    )
                return existing

            delivery = FeishuMessageDelivery(
                id=new_id(),
                run_id=run_id,
                onboarding_session_id=onboarding_session_id,
                purpose=purpose,
                revision=revision,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                content_hash=content_hash,
                idempotency_key=idempotency_key,
                status=status,
                external_message_id=external_message_id,
                attempt_count=0,
                last_error_summary=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(delivery)
            session.commit()
            session.refresh(delivery)
            return delivery

    def mark_sent(
        self, delivery_id: str, *, external_message_id: str | None = None
    ) -> FeishuMessageDelivery:
        return self._update_delivery(
            delivery_id,
            status="sent",
            external_message_id=external_message_id,
            last_error_summary=None,
        )

    def mark_updated(
        self, delivery_id: str, *, external_message_id: str | None = None
    ) -> FeishuMessageDelivery:
        return self._update_delivery(
            delivery_id,
            status="updated",
            external_message_id=external_message_id,
            last_error_summary=None,
        )

    def mark_failed(self, delivery_id: str, *, error_summary: str) -> FeishuMessageDelivery:
        return self._update_delivery(
            delivery_id,
            status="failed",
            external_message_id=None,
            last_error_summary=error_summary,
            increment_attempts=True,
        )

    def _update_delivery(
        self,
        delivery_id: str,
        *,
        status: str,
        external_message_id: str | None = None,
        last_error_summary: str | None,
        increment_attempts: bool = False,
    ) -> FeishuMessageDelivery:
        with self._session_factory() as session:
            delivery = session.get(FeishuMessageDelivery, delivery_id)
            if delivery is None:
                raise ValueError(f"unknown feishu message delivery id: {delivery_id}")
            delivery.status = status
            if external_message_id is not None:
                delivery.external_message_id = external_message_id
            delivery.last_error_summary = last_error_summary
            if increment_attempts:
                delivery.attempt_count += 1
            delivery.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(delivery)
            return delivery
