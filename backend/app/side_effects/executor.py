from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import canonical_json_hash
from app.db.models import (
    PublishPlan,
    ReportArtifact,
    ReportRun,
    ReportVersion,
    SideEffectAttempt,
    SideEffectOperation,
    new_id,
)
from app.providers.fake import FakeEffectProvider

SessionFactory = Callable[[], Session]
DEFAULT_OPERATION_LEASE_SECONDS = 300


@dataclass(slots=True)
class SideEffectExecutionOutcome:
    status: Literal["complete", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    operation_ref: str | None = None
    artifact_ref: str | None = None
    external_id: str | None = None
    external_url: str | None = None
    provider_request_id: str | None = None
    current_stage: str | None = None
    current_node: str | None = None
    side_effect_status: str | None = None
    next_operation_index: int | None = None


class SideEffectExecutor:
    def __init__(
        self,
        session_factory: SessionFactory,
        effect_provider: FakeEffectProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._effect_provider = effect_provider or FakeEffectProvider()

    def create_feishu_document(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approved_plan_hash: str,
    ) -> SideEffectExecutionOutcome:
        return self._execute_operation(
            run_id=run_id,
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
            sequence=1,
            expected_operation_type="create_feishu_document",
            artifact_type="feishu_document",
            handler_name="create_feishu_document",
            handler_argument_field="report_version_ref",
            next_operation_index=1,
            next_node="send_group_summary",
        )

    def send_group_summary(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approved_plan_hash: str,
    ) -> SideEffectExecutionOutcome:
        return self._execute_operation(
            run_id=run_id,
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
            sequence=2,
            expected_operation_type="send_group_summary",
            artifact_type="group_message",
            handler_name="send_group_summary",
            handler_argument_field="run_id",
            next_operation_index=2,
            next_node="archive_report_record",
        )

    def archive_report_record(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approved_plan_hash: str,
    ) -> SideEffectExecutionOutcome:
        return self._execute_operation(
            run_id=run_id,
            publish_plan_ref=publish_plan_ref,
            approved_plan_hash=approved_plan_hash,
            sequence=3,
            expected_operation_type="upsert_bitable_archive",
            artifact_type="bitable_archive",
            handler_name="upsert_bitable_archive",
            handler_argument_field="run_id",
            next_operation_index=3,
            next_node="verify_side_effects",
        )

    def verify_side_effects(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approved_plan_hash: str,
    ) -> SideEffectExecutionOutcome:
        with self._session_factory() as session:
            run, publish_plan = self._load_run_and_plan(session, run_id, publish_plan_ref)
            if approved_plan_hash != publish_plan.plan_hash:
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_HASH_MISMATCH",
                    error_summary="Approved plan hash does not match the persisted publish plan",
                )

            operations = session.scalars(
                select(SideEffectOperation)
                .where(SideEffectOperation.publish_plan_id == publish_plan.id)
                .order_by(SideEffectOperation.sequence)
            ).all()
            if len(operations) < 3:
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="SIDE_EFFECT_OPERATION_MISSING",
                    error_summary="Not all publish operations have been executed",
                )
            if any(operation.status != "succeeded" for operation in operations):
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="SIDE_EFFECT_OPERATION_INCOMPLETE",
                    error_summary="One or more publish operations are not yet successful",
                )

            artifacts = session.scalars(
                select(ReportArtifact).where(
                    ReportArtifact.operation_id.in_([operation.id for operation in operations])
                )
            ).all()
            if len(artifacts) < 3:
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="REPORT_ARTIFACT_MISSING",
                    error_summary="One or more artifacts are missing",
                )

            now = datetime.now(UTC)
            for operation in operations:
                operation.verification_status = "confirmed"
                operation.updated_at = now
            for artifact in artifacts:
                if artifact.verified_at is None:
                    artifact.verified_at = now
            session.commit()
            return SideEffectExecutionOutcome(
                status="complete",
                current_stage="publishing",
                current_node="complete_run",
                side_effect_status="verified",
                next_operation_index=3,
            )

    def _execute_operation(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approved_plan_hash: str,
        sequence: int,
        expected_operation_type: str,
        artifact_type: str,
        handler_name: str,
        handler_argument_field: str,
        next_operation_index: int,
        next_node: str,
    ) -> SideEffectExecutionOutcome:
        with self._session_factory() as session:
            run, publish_plan = self._load_run_and_plan(session, run_id, publish_plan_ref)
            if approved_plan_hash != publish_plan.plan_hash:
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_HASH_MISMATCH",
                    error_summary="Approved plan hash does not match the persisted publish plan",
                )
            now = datetime.now(UTC)
            dependency_issue = self._validate_operation_dependencies(
                session,
                publish_plan_id=publish_plan.id,
                sequence=sequence,
                current_node=handler_name,
                next_operation_index=sequence - 1,
            )
            if dependency_issue is not None:
                return dependency_issue
            operation_spec = self._operation_spec(publish_plan, sequence)
            if operation_spec["type"] != expected_operation_type:
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="PUBLISH_OPERATION_TYPE_MISMATCH",
                    error_summary="Publish plan operation type does not match the expected step",
                )

            operation_key = build_operation_key(
                publish_plan_id=publish_plan.id,
                sequence=sequence,
                operation_type=expected_operation_type,
                target_hash=canonical_json_hash(operation_spec["target"]),
                payload_hash=canonical_json_hash(operation_spec["payload"]),
            )
            existing_operation = session.scalar(
                select(SideEffectOperation).where(
                    SideEffectOperation.idempotency_key == operation_key
                )
            )
            if existing_operation is not None:
                if existing_operation.status == "succeeded":
                    artifact = session.scalar(
                        select(ReportArtifact).where(
                            ReportArtifact.operation_id == existing_operation.id
                        )
                    )
                    if artifact is None:
                        artifact = self._create_artifact(
                            session,
                            run=run,
                            publish_plan=publish_plan,
                            operation=existing_operation,
                            artifact_type=artifact_type,
                            operation_spec=operation_spec,
                        )
                        session.commit()
                    return SideEffectExecutionOutcome(
                        status="complete",
                        operation_ref=existing_operation.id,
                        artifact_ref=artifact.id if artifact is not None else None,
                        external_id=existing_operation.external_resource_id,
                        external_url=existing_operation.external_url,
                        provider_request_id=existing_operation.provider_request_id,
                        current_stage="publishing",
                        current_node=next_node,
                        side_effect_status="executing",
                        next_operation_index=next_operation_index,
                    )
                if existing_operation.status not in {"running", "claimed"}:
                    return SideEffectExecutionOutcome(
                        status="blocked",
                        error_code="SIDE_EFFECT_OPERATION_FAILED",
                        error_summary="Publish operation already failed",
                        operation_ref=existing_operation.id,
                        current_stage="blocked",
                        current_node=next_node,
                        side_effect_status="executing",
                        next_operation_index=next_operation_index,
                    )
                if not _operation_claim_is_expired(existing_operation, now):
                    return SideEffectExecutionOutcome(
                        status="blocked",
                        error_code="SIDE_EFFECT_OPERATION_IN_PROGRESS",
                        error_summary="Publish operation is already recorded but not successful",
                        operation_ref=existing_operation.id,
                        current_stage="publishing",
                        current_node=next_node,
                        side_effect_status="executing",
                        next_operation_index=next_operation_index,
                    )
                existing_operation.status = "running"
                existing_operation.attempt_count += 1
                existing_operation.started_at = now
                existing_operation.completed_at = None
                existing_operation.updated_at = now
                existing_operation.version += 1
                existing_operation.external_resource_id = None
                existing_operation.external_url = None
                existing_operation.provider_request_id = None
                existing_operation.verification_status = "not_checked"
                existing_operation.last_error_class = None
                existing_operation.last_error_summary = None
                operation = existing_operation
            else:
                operation = SideEffectOperation(
                    id=new_id(),
                    publish_plan_id=publish_plan.id,
                    run_id=run.id,
                    sequence=sequence,
                    operation_type=expected_operation_type,
                    target_ref=_stable_ref(operation_spec["target"]),
                    target_hash=canonical_json_hash(operation_spec["target"]),
                    payload_ref=_stable_ref(operation_spec["payload"]),
                    payload_hash=canonical_json_hash(operation_spec["payload"]),
                    idempotency_key=operation_key,
                    status="running",
                    attempt_count=1,
                    verification_status="not_checked",
                    started_at=now,
                    completed_at=None,
                )
                session.add(operation)
                session.flush()
            attempt_number = operation.attempt_count
            attempt = SideEffectAttempt(
                id=new_id(),
                operation_id=operation.id,
                attempt=attempt_number,
                status="started",
                request_summary={
                    "publish_plan_ref": publish_plan.id,
                    "run_id": run.id,
                    "sequence": sequence,
                    "operation_type": expected_operation_type,
                },
                provider_request_id=None,
                response_summary={},
                error_class=None,
                started_at=now,
                ended_at=None,
            )
            session.add(attempt)
            session.flush()
            session.commit()

            handler = getattr(self._effect_provider, handler_name)
            handler_arg = _operation_handler_argument(
                operation_spec, handler_argument_field, run.id
            )
            response = handler(handler_arg)
            response_status = str(response.get("status", "unknown"))
            response_summary = dict(response)
            attempt.response_summary = response_summary
            attempt.provider_request_id = cast(str | None, response.get("provider_request_id"))
            attempt.ended_at = datetime.now(UTC)

            if response_status != "success":
                error_class = cast(str | None, response.get("error_class")) or "provider_error"
                operation.status = "failed"
                operation.last_error_class = error_class
                operation.last_error_summary = response_status
                operation.completed_at = datetime.now(UTC)
                operation.updated_at = operation.completed_at
                attempt.status = "failed"
                attempt.error_class = error_class
                session.commit()
                return SideEffectExecutionOutcome(
                    status="blocked",
                    error_code="SIDE_EFFECT_OPERATION_FAILED",
                    error_summary="Publish operation failed in the fake provider",
                    operation_ref=operation.id,
                    current_stage="blocked",
                    current_node=next_node,
                    side_effect_status="executing",
                    next_operation_index=next_operation_index,
                )

            external_id = cast(str | None, response.get("external_id"))
            external_url = cast(str | None, response.get("url"))
            provider_request_id = cast(str | None, response.get("provider_request_id"))
            operation.status = "succeeded"
            operation.attempt_count = attempt_number
            operation.external_resource_id = external_id
            operation.external_url = external_url
            operation.provider_request_id = provider_request_id
            operation.verification_status = "not_checked"
            operation.completed_at = datetime.now(UTC)
            operation.updated_at = operation.completed_at
            attempt.status = "succeeded"

            artifact = self._create_artifact(
                session,
                run=run,
                publish_plan=publish_plan,
                operation=operation,
                artifact_type=artifact_type,
                operation_spec=operation_spec,
                external_id=external_id,
                external_url=external_url,
            )
            session.commit()
            return SideEffectExecutionOutcome(
                status="complete",
                operation_ref=operation.id,
                artifact_ref=artifact.id,
                external_id=external_id,
                external_url=external_url,
                provider_request_id=provider_request_id,
                current_stage="publishing",
                current_node=next_node,
                side_effect_status="executing",
                next_operation_index=next_operation_index,
            )

    def _load_run_and_plan(
        self,
        session: Session,
        run_id: str,
        publish_plan_ref: str,
    ) -> tuple[ReportRun, PublishPlan]:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        publish_plan = session.get(PublishPlan, publish_plan_ref)
        if publish_plan is None:
            raise ValueError(f"unknown publish_plan_ref: {publish_plan_ref}")
        if publish_plan.run_id != run_id:
            raise ValueError("publish plan does not belong to the current run")
        return run, publish_plan

    def _operation_spec(self, publish_plan: PublishPlan, sequence: int) -> Mapping[str, object]:
        operations = publish_plan.canonical_plan.get("operations")
        if not isinstance(operations, list):
            raise ValueError("publish plan operations are missing")
        index = sequence - 1
        if index < 0 or index >= len(operations):
            raise ValueError("publish plan operation sequence is out of range")
        operation = operations[index]
        if not isinstance(operation, Mapping):
            raise ValueError("publish plan operation is invalid")
        return operation

    def _validate_operation_dependencies(
        self,
        session: Session,
        *,
        publish_plan_id: str,
        sequence: int,
        current_node: str,
        next_operation_index: int,
    ) -> SideEffectExecutionOutcome | None:
        if sequence <= 1:
            return None
        operations = session.scalars(
            select(SideEffectOperation)
            .where(
                SideEffectOperation.publish_plan_id == publish_plan_id,
                SideEffectOperation.sequence < sequence,
            )
            .order_by(SideEffectOperation.sequence)
        ).all()
        if len(operations) < sequence - 1:
            return SideEffectExecutionOutcome(
                status="blocked",
                error_code="SIDE_EFFECT_DEPENDENCY_MISSING",
                error_summary="Prior publish operations are required before this step can run",
                current_stage="blocked",
                current_node=current_node,
                side_effect_status="waiting",
                next_operation_index=next_operation_index,
            )
        if any(operation.status != "succeeded" for operation in operations):
            return SideEffectExecutionOutcome(
                status="blocked",
                error_code="SIDE_EFFECT_DEPENDENCY_INCOMPLETE",
                error_summary="A prior publish operation has not succeeded yet",
                current_stage="blocked",
                current_node=current_node,
                side_effect_status="waiting",
                next_operation_index=next_operation_index,
            )
        return None

    def _create_artifact(
        self,
        session: Session,
        *,
        run: ReportRun,
        publish_plan: PublishPlan,
        operation: SideEffectOperation,
        artifact_type: str,
        operation_spec: Mapping[str, object],
        external_id: str | None = None,
        external_url: str | None = None,
    ) -> ReportArtifact:
        existing = session.scalar(
            select(ReportArtifact).where(ReportArtifact.operation_id == operation.id)
        )
        if existing is not None:
            return existing
        report_version = session.get(ReportVersion, publish_plan.report_version_id)
        if report_version is None:
            raise ValueError("report version not found for publish plan")
        artifact = ReportArtifact(
            id=new_id(),
            run_id=run.id,
            report_version_id=report_version.id,
            artifact_type=artifact_type,
            operation_id=operation.id,
            external_id=external_id or operation.external_resource_id,
            url=external_url or operation.external_url,
            target_ref=_stable_ref(operation_spec["target"]),
            content_hash=_artifact_content_hash(operation_spec),
            status="active",
            verified_at=None,
        )
        session.add(artifact)
        session.flush()
        return artifact


def build_operation_key(
    *,
    publish_plan_id: str,
    sequence: int,
    operation_type: str,
    target_hash: str,
    payload_hash: str,
) -> str:
    return canonical_json_hash(
        {
            "publish_plan_id": publish_plan_id,
            "sequence": sequence,
            "operation_type": operation_type,
            "target_hash": target_hash,
            "payload_hash": payload_hash,
        }
    )


def _operation_handler_argument(
    operation_spec: Mapping[str, object],
    field_name: str,
    run_id: str,
) -> str:
    target = operation_spec.get("target")
    payload = operation_spec.get("payload")
    if field_name == "report_version_ref" and isinstance(payload, Mapping):
        value = payload.get("rendered_report_ref") or payload.get("report_version_ref")
        if isinstance(value, str) and value:
            return value
    if field_name == "run_id":
        return run_id
    if isinstance(target, Mapping):
        candidate = target.get(field_name)
        if isinstance(candidate, str) and candidate:
            return candidate
    if isinstance(payload, Mapping):
        candidate = payload.get(field_name)
        if isinstance(candidate, str) and candidate:
            return candidate
    return run_id


def _stable_ref(value: object) -> str:
    if isinstance(value, Mapping):
        return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, list):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _artifact_content_hash(operation_spec: Mapping[str, object]) -> str:
    payload = operation_spec.get("payload")
    if isinstance(payload, Mapping):
        if isinstance(payload.get("rendered_content_hash"), str):
            return cast(str, payload["rendered_content_hash"])
        if isinstance(payload.get("content_hash"), str):
            return cast(str, payload["content_hash"])
        return canonical_json_hash(payload)
    return canonical_json_hash(operation_spec)


def _operation_claim_is_expired(
    operation: SideEffectOperation,
    now: datetime,
    *,
    lease_seconds: int = DEFAULT_OPERATION_LEASE_SECONDS,
) -> bool:
    started_at = operation.started_at
    if started_at is None:
        return True
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    else:
        started_at = started_at.astimezone(UTC)
    current_time = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return current_time - started_at >= timedelta(seconds=lease_seconds)
