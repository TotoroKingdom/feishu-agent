from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import (
    APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
    GENERATION_APPROVAL_TYPE,
    HUMAN_INPUT_APPROVAL_TYPE,
    GenerationApprovalStore,
    PublishApprovalStore,
)
from app.core.config import Settings
from app.messaging.ledger import CallbackEventConflictError, CallbackInboxStore
from app.db.models import HumanApproval
from app.providers.feishu.auth import (
    FeishuAuthError,
    FeishuIdentityResolver,
)
from app.providers.feishu.models import (
    FeishuCardActionRequest,
    FeishuEventRequest,
    FeishuResolvedActor,
)
from app.providers.feishu.resume import (
    FeishuResumeError,
    build_resume_payload,
    normalize_callback_action,
)

if TYPE_CHECKING:
    from app.agent.runtime import WorkflowExecutionResult, WorkflowRuntime


SessionFactory = Callable[[], Session]
RuntimeFactory = Callable[[], "WorkflowRuntime"]


class FeishuCallbackError(ValueError):
    pass


class FeishuCallbackValidationError(FeishuCallbackError):
    pass


class FeishuCallbackConflictError(FeishuCallbackError):
    pass


class FeishuCallbackService:
    def __init__(
        self,
        session_factory: SessionFactory,
        settings: Settings,
        *,
        runtime_factory: RuntimeFactory | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._identity = FeishuIdentityResolver(settings)
        self._verification_token = (
            settings.feishu_verification_token.get_secret_value()
            if settings.feishu_verification_token is not None
            else None
        )
        self._inbox = CallbackInboxStore(session_factory)
        self._generation_approvals = GenerationApprovalStore(session_factory)
        self._publish_approvals = PublishApprovalStore(session_factory)
        self._runtime_factory = runtime_factory
        self._now_factory = now_factory or (lambda: datetime.now(UTC))
        self._max_skew = self._identity.callback_max_skew

    def handle_event(
        self, request: FeishuEventRequest, *, verification_token: str | None = None
    ) -> dict[str, object]:
        self._validate_verification_token(verification_token or request.token)
        if request.challenge:
            return {"challenge": request.challenge}
        if request.external_event_id is None:
            raise FeishuCallbackValidationError("external_event_id is required")
        if request.actor is not None and request.event_type is not None:
            resolved_actor = self._identity.resolve_actor(request.actor)
            self._record_event(
                external_event_id=request.external_event_id,
                event_type=request.event_type,
                payload=request.model_dump(mode="python"),
                actor_id=resolved_actor.actor_ref,
                run_id=None,
            )
        return {"data": {"status": "accepted"}}

    def handle_card_action(
        self, request: FeishuCardActionRequest, *, verification_token: str | None = None
    ) -> dict[str, object]:
        self._validate_verification_token(verification_token)
        self._validate_time_window(request.occurred_at)
        normalized_action = normalize_callback_action(request.action.action_type)
        approval = self._load_approval_by_challenge(request.action.challenge_id)
        if approval.status != "pending":
            return self._accepted_response(duplicate=True, run_id=request.action.run_id)
        requested_from = list(approval.requested_from or [])
        resolved_actor = self._identity.resolve_actor(request.actor, requested_from=requested_from)
        if (
            approval.approval_type == HUMAN_INPUT_APPROVAL_TYPE
            and normalized_action == APPROVAL_ACTION_SUBMIT_HUMAN_INPUT
        ):
            self._validate_human_input_submission(request, approval)
        payload = request.model_dump(mode="python")

        event = self._record_event(
            external_event_id=request.external_event_id,
            event_type=normalized_action,
            payload=payload,
            actor_id=resolved_actor.actor_ref,
            run_id=request.action.run_id,
        )
        if event.status == "processed":
            return self._accepted_response(duplicate=True, run_id=request.action.run_id)

        try:
            result = self._resume_runtime(request, resolved_actor)
        except FeishuAuthError as error:
            self._inbox.mark_callback_event_failed(
                event.id,
                error_class=type(error).__name__,
                error_summary=str(error),
                dead_letter=False,
            )
            raise
        except (FeishuResumeError, ValueError) as error:
            self._inbox.mark_callback_event_failed(
                event.id,
                error_class=type(error).__name__,
                error_summary=str(error),
                dead_letter=False,
            )
            raise FeishuCallbackValidationError(str(error)) from error
        except Exception as error:
            self._inbox.mark_callback_event_failed(
                event.id,
                error_class=type(error).__name__,
                error_summary=str(error),
                dead_letter=False,
            )
            raise

        self._inbox.mark_callback_event_processed(event.id)
        return self._accepted_response(
            duplicate=False,
            run_id=request.action.run_id,
            approval_revision=request.action.approval_revision,
            workflow_status=getattr(result, "status", None),
        )

    def _resume_runtime(
        self, request: FeishuCardActionRequest, resolved_actor: FeishuResolvedActor
    ) -> WorkflowExecutionResult:
        runtime = self._runtime_factory() if self._runtime_factory is not None else None
        if runtime is None:
            raise FeishuCallbackValidationError("workflow runtime is not configured")
        resume_payload = build_resume_payload(
            action=request.action,
            actor=resolved_actor,
        )
        return runtime.resume(request.action.run_id, resume_payload)

    def _record_event(
        self,
        *,
        external_event_id: str,
        event_type: str,
        payload: Mapping[str, object],
        actor_id: str,
        run_id: str | None,
    ):
        try:
            return self._inbox.record_callback_event(
                provider="feishu",
                external_event_id=external_event_id,
                event_type=event_type,
                payload=payload,
                actor_id=actor_id,
                run_id=run_id,
            )
        except CallbackEventConflictError as error:
            raise FeishuCallbackConflictError(str(error)) from error

    def _load_approval_by_challenge(self, challenge_id: str) -> HumanApproval:
        approval = self._generation_approvals.load_approval_by_challenge(challenge_id)
        if approval is None:
            approval = self._publish_approvals.load_approval_by_challenge(challenge_id)
        if approval is None:
            approval = self._load_human_input_approval_by_challenge(challenge_id)
        if approval is None:
            raise FeishuCallbackValidationError(f"unknown approval challenge_id: {challenge_id}")
        return approval

    def _load_human_input_approval_by_challenge(self, challenge_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )

    def _validate_human_input_submission(
        self, request: FeishuCardActionRequest, approval: HumanApproval
    ) -> None:
        runtime = self._runtime_factory() if self._runtime_factory is not None else None
        if runtime is None:
            raise FeishuCallbackValidationError("workflow runtime is not configured")
        snapshot = runtime.inspect(request.action.run_id)
        if snapshot is None:
            raise FeishuCallbackValidationError("run snapshot is unavailable")
        diagnosis = snapshot.values.get("diagnosis")
        if not isinstance(diagnosis, Mapping):
            raise FeishuCallbackValidationError("human input diagnosis is unavailable")
        requested_fields = diagnosis.get("required_fields")
        if not isinstance(requested_fields, list):
            raise FeishuCallbackValidationError("human input schema is unavailable")
        payload = request.action.payload
        unknown_keys = set(payload) - {
            str(field.get("name"))
            for field in requested_fields
            if isinstance(field, Mapping) and isinstance(field.get("name"), str)
        }
        if unknown_keys:
            raise FeishuCallbackValidationError(
                f"unsupported supplement fields: {sorted(str(key) for key in unknown_keys)}"
            )
        for field in requested_fields:
            if not isinstance(field, Mapping):
                raise FeishuCallbackValidationError("human input schema is invalid")
            name = field.get("name")
            field_type = field.get("type")
            required = field.get("required", True)
            if not isinstance(name, str) or not name:
                raise FeishuCallbackValidationError("human input schema is invalid")
            if required and name not in payload:
                raise FeishuCallbackValidationError(f"supplement.{name} is required")
            if name not in payload:
                continue
            value = payload[name]
            if field_type == "string" and (not isinstance(value, str) or not value.strip()):
                raise FeishuCallbackValidationError(f"supplement.{name} must be a non-empty string")
            if field_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                raise FeishuCallbackValidationError(f"supplement.{name} must be a number")
            if field_type == "boolean" and not isinstance(value, bool):
                raise FeishuCallbackValidationError(f"supplement.{name} must be a boolean")
            if field_type == "object" and not isinstance(value, Mapping):
                raise FeishuCallbackValidationError(f"supplement.{name} must be a mapping")
            if field_type == "array" and (
                not isinstance(value, list) or isinstance(value, (str, bytes, bytearray))
            ):
                raise FeishuCallbackValidationError(f"supplement.{name} must be a list")

    def _validate_time_window(self, occurred_at: datetime) -> None:
        now = self._now_factory()
        candidate = (
            occurred_at
            if occurred_at.tzinfo is not None
            else occurred_at.replace(tzinfo=UTC)
        )
        delta = abs(now - candidate.astimezone(UTC))
        if delta > self._max_skew:
            raise FeishuCallbackValidationError(
                "callback event is outside the accepted time window"
            )

    def _validate_verification_token(self, token: str | None) -> None:
        if self._verification_token is None:
            return
        if token != self._verification_token:
            raise FeishuCallbackValidationError("callback verification token mismatch")

    def _accepted_response(
        self,
        *,
        duplicate: bool,
        run_id: str,
        approval_revision: int | None = None,
        workflow_status: str | None = None,
    ) -> dict[str, object]:
        data: dict[str, object] = {
            "status": "accepted",
            "duplicate": duplicate,
            "run_id": run_id,
        }
        if approval_revision is not None:
            data["approval_revision"] = approval_revision
        if workflow_status is not None:
            data["workflow_status"] = workflow_status
        return {"data": data}
