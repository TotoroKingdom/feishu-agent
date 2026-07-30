from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy.orm import Session

from app.db.models import SideEffectOperation
from app.providers.fake import FakeEffectProvider

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class SideEffectVerificationOutcome:
    status: Literal["confirmed", "not_found", "inconclusive"]
    operation_ref: str | None = None
    error_code: str | None = None
    error_summary: str | None = None
    external_id: str | None = None
    external_url: str | None = None
    provider_request_id: str | None = None


class SideEffectVerifier:
    def __init__(
        self,
        session_factory: SessionFactory,
        effect_provider: object | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._effect_provider = effect_provider or FakeEffectProvider()

    def verify(self, operation_id: str) -> SideEffectVerificationOutcome:
        with self._session_factory() as session:
            operation = session.get(SideEffectOperation, operation_id)
            if operation is None:
                raise ValueError(f"unknown operation_id: {operation_id}")

            if operation.verification_status == "confirmed" and operation.status == "succeeded":
                return SideEffectVerificationOutcome(
                    status="confirmed",
                    operation_ref=operation.id,
                    external_id=operation.external_resource_id,
                    external_url=operation.external_url,
                    provider_request_id=operation.provider_request_id,
                )

            query_handler = self._query_handler(operation.operation_type)
            if query_handler is None or operation.external_resource_id is None:
                return self._mark_inconclusive(
                    session,
                    operation=operation,
                    error_code="SIDE_EFFECT_VERIFICATION_UNSUPPORTED",
                    error_summary="No query capability is available for this side effect",
                )

            response = query_handler(operation.external_resource_id, operation.run_id)
            response_status = str(response.get("status", "unknown")).casefold()
            response_error_class = cast(str | None, response.get("error_class"))
            response_error_summary = cast(str | None, response.get("error_summary"))
            response_provider_request_id = cast(str | None, response.get("provider_request_id"))
            response_external_url = cast(str | None, response.get("url"))
            now = datetime.now(UTC)

            if response_status in {"confirmed", "success"}:
                operation.status = "succeeded"
                operation.verification_status = "confirmed"
                operation.last_error_class = None
                operation.last_error_summary = None
                operation.provider_request_id = (
                    response_provider_request_id or operation.provider_request_id
                )
                operation.external_url = response_external_url or operation.external_url
                operation.updated_at = now
                operation.version += 1
                session.commit()
                return SideEffectVerificationOutcome(
                    status="confirmed",
                    operation_ref=operation.id,
                    external_id=operation.external_resource_id,
                    external_url=operation.external_url,
                    provider_request_id=operation.provider_request_id,
                )

            if response_status in {"not_found", "missing"}:
                operation.status = "unknown"
                operation.verification_status = "not_found"
                operation.last_error_class = response_error_class or "resource_not_found"
                operation.last_error_summary = response_error_summary or "Side effect was not found"
                operation.provider_request_id = (
                    response_provider_request_id or operation.provider_request_id
                )
                operation.external_url = response_external_url or operation.external_url
                operation.updated_at = now
                operation.version += 1
                session.commit()
                return SideEffectVerificationOutcome(
                    status="not_found",
                    operation_ref=operation.id,
                    error_code=operation.last_error_class,
                    error_summary=operation.last_error_summary,
                    external_id=operation.external_resource_id,
                    external_url=operation.external_url,
                    provider_request_id=operation.provider_request_id,
                )

            operation.status = "unknown"
            operation.verification_status = "inconclusive"
            operation.last_error_class = response_error_class or "verification_timeout"
            operation.last_error_summary = response_error_summary or response_status
            operation.provider_request_id = (
                response_provider_request_id or operation.provider_request_id
            )
            operation.external_url = response_external_url or operation.external_url
            operation.updated_at = now
            operation.version += 1
            session.commit()
            return SideEffectVerificationOutcome(
                status="inconclusive",
                operation_ref=operation.id,
                error_code=operation.last_error_class,
                error_summary=operation.last_error_summary,
                external_id=operation.external_resource_id,
                external_url=operation.external_url,
                provider_request_id=operation.provider_request_id,
            )

    def _query_handler(
        self, operation_type: str
    ) -> Callable[[str, str], Mapping[str, object]] | None:
        handler_name = {
            "create_feishu_document": "query_feishu_document",
            "send_group_summary": "query_group_summary",
            "upsert_bitable_archive": "query_bitable_archive",
        }.get(operation_type)
        if handler_name is None:
            return None
        handler = getattr(self._effect_provider, handler_name, None)
        if not callable(handler):
            return None
        return cast(Callable[[str, str], Mapping[str, object]], handler)

    def _mark_inconclusive(
        self,
        session: Session,
        *,
        operation: SideEffectOperation,
        error_code: str,
        error_summary: str,
    ) -> SideEffectVerificationOutcome:
        now = datetime.now(UTC)
        operation.status = "unknown"
        operation.verification_status = "inconclusive"
        operation.last_error_class = error_code
        operation.last_error_summary = error_summary
        operation.updated_at = now
        operation.version += 1
        session.commit()
        return SideEffectVerificationOutcome(
            status="inconclusive",
            operation_ref=operation.id,
            error_code=error_code,
            error_summary=error_summary,
            external_id=operation.external_resource_id,
            external_url=operation.external_url,
            provider_request_id=operation.provider_request_id,
        )
