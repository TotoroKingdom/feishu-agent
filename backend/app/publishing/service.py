from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.approvals import (
    APPROVAL_ACTION_APPROVE_PUBLISH,
    APPROVAL_ACTION_CANCEL_PUBLISH,
    APPROVAL_ACTION_REGENERATE_REPORT,
    APPROVAL_ACTION_UPDATE_SUPPLEMENT,
    PUBLISH_APPROVAL_TYPE,
    canonical_json_hash,
)
from app.db.models import HumanApproval, Project, PublishPlan, ReportRun, ReportVersion, ToolExecution, new_id
from app.publishing.generation import build_publish_plan_hash, build_publish_plan_payload

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class PublishPlanOutcome:
    status: Literal["complete", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    publish_plan_ref: str | None = None
    approval_ref: str | None = None
    challenge_id: str | None = None
    plan_hash: str | None = None
    publish_plan_version: int | None = None
    approval_revision: int | None = None


@dataclass(slots=True)
class PublishResumeOutcome:
    status: Literal["complete", "blocked"]
    error_code: str | None = None
    error_summary: str | None = None
    publish_plan_ref: str | None = None
    approval_ref: str | None = None
    challenge_id: str | None = None
    approval_revision: int | None = None
    plan_hash: str | None = None
    current_stage: str | None = None
    current_node: str | None = None


class PublishingService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def build_publish_plan(self, run_id: str, report_version_id: str) -> PublishPlanOutcome:
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            project = self._load_project(session, run.project_id)
            report_version = session.get(ReportVersion, report_version_id)
            if report_version is None:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="REPORT_VERSION_MISSING",
                    error_summary="Report version not found",
                )
            if report_version.run_id != run_id:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="REPORT_VERSION_MISMATCH",
                    error_summary="Report version does not belong to the current run",
                    publish_plan_ref=report_version.id,
                )
            if report_version.status != "verified":
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="REPORT_NOT_VERIFIED",
                    error_summary="Report version must be verified before publishing",
                    publish_plan_ref=report_version.id,
                )

            content_hash = _maybe_string(report_version.content_hash)
            if content_hash is None:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="REPORT_CONTENT_HASH_MISSING",
                    error_summary="Rendered report hash is missing",
                    publish_plan_ref=report_version.id,
                )
            plan_payload = build_publish_plan_payload(
                run_id=run.id,
                report_version_ref=report_version.id,
                report_version=report_version.version,
                report_period={
                    "start_at": run.period_start,
                    "end_at": run.period_end,
                    "timezone": project.timezone,
                },
                content_hash=content_hash,
                expected_publish_group_ref=_expected_publish_group_ref(run),
                archive_resource_ref=_archive_resource_ref(session, run.project_id),
                content_version=1,
            )
            plan_hash = build_publish_plan_hash(plan_payload)
            existing = session.scalar(
                select(PublishPlan).where(
                    PublishPlan.run_id == run_id,
                    PublishPlan.plan_hash == plan_hash,
                )
            )
            if existing is None:
                next_version = session.scalar(
                    select(func.coalesce(func.max(PublishPlan.version), 0)).where(
                        PublishPlan.run_id == run_id
                    )
                )
                publish_plan = PublishPlan(
                    id=new_id(),
                    run_id=run_id,
                    report_version_id=report_version.id,
                    version=int(next_version or 0) + 1,
                    status="draft",
                    canonical_plan=plan_payload,
                    plan_hash=plan_hash,
                    content_version=1,
                    approved_at=None,
                    invalidated_at=None,
                )
                session.add(publish_plan)
                session.flush()
            else:
                publish_plan = existing
            self._record_tool_execution(
                session,
                run_id=run_id,
                node_execution_id="build_publish_plan",
                tool_name="publishing.build_publish_plan",
                request_summary={"report_version_id": report_version_id},
                result_summary={
                    "content_hash": plan_hash,
                    "operation_count": len(plan_payload["operations"]),
                    "publish_plan_version": publish_plan.version,
                },
                data_ref=publish_plan.id,
                status="success",
                retryable=False,
            )
            session.commit()
            return PublishPlanOutcome(
                status="complete",
                publish_plan_ref=publish_plan.id,
                plan_hash=publish_plan.plan_hash,
                publish_plan_version=publish_plan.version,
            )

    def request_publish_confirmation(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        requested_from: Sequence[str] | None = None,
        card_message_id: str | None = None,
        challenge_id: str | None = None,
    ) -> PublishPlanOutcome:
        allowed_from = list(requested_from or ("local-demo",))
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            publish_plan = session.get(PublishPlan, publish_plan_ref)
            if publish_plan is None:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_MISSING",
                    error_summary="Publish plan not found",
                )
            if publish_plan.run_id != run_id:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_MISMATCH",
                    error_summary="Publish plan does not belong to the current run",
                    publish_plan_ref=publish_plan.id,
                )
            if publish_plan.status not in {"draft", "pending_approval"}:
                return PublishPlanOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_INVALID_STATE",
                    error_summary="Publish plan is not waiting for approval",
                    publish_plan_ref=publish_plan.id,
                )

            revision = publish_plan.version
            existing = session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == PUBLISH_APPROVAL_TYPE,
                    HumanApproval.revision == revision,
                )
            )
            if existing is not None:
                if existing.request_payload_hash != publish_plan.plan_hash:
                    raise ValueError("publish approval revision hash mismatch")
                publish_plan.status = "pending_approval"
                session.commit()
                return PublishPlanOutcome(
                    status="complete",
                    publish_plan_ref=publish_plan.id,
                    plan_hash=publish_plan.plan_hash,
                    approval_ref=existing.id,
                    challenge_id=existing.challenge_id,
                    approval_revision=existing.revision,
                    publish_plan_version=publish_plan.version,
                )

            approval = HumanApproval(
                id=new_id(),
                run_id=run_id,
                approval_type=PUBLISH_APPROVAL_TYPE,
                revision=revision,
                status="pending",
                challenge_id=challenge_id or new_id(),
                card_message_id=card_message_id,
                requested_from=allowed_from,
                request_payload_hash=publish_plan.plan_hash,
                plan_hash=publish_plan.plan_hash,
                actor_id=None,
                actor_type=None,
                decision=None,
                supplement=None,
                decided_at=None,
                expires_at=None,
            )
            publish_plan.status = "pending_approval"
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return PublishPlanOutcome(
                status="complete",
                publish_plan_ref=publish_plan.id,
                plan_hash=publish_plan.plan_hash,
                approval_ref=approval.id,
                challenge_id=approval.challenge_id,
                approval_revision=approval.revision,
                publish_plan_version=publish_plan.version,
            )

    def resume_publish_confirmation(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approval_ref: str,
        challenge_id: str,
        approval_revision: int,
        presented_hash: str,
        action: str,
        actor_id: str,
        requested_from: Sequence[str] | None = None,
        supplement: Mapping[str, object] | None = None,
    ) -> PublishResumeOutcome:
        allowed_from = list(requested_from or ("local-demo",))
        normalized_action = action.strip().casefold()
        with self._session_factory() as session:
            run = self._load_run(session, run_id)
            publish_plan = session.get(PublishPlan, publish_plan_ref)
            if publish_plan is None:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_MISSING",
                    error_summary="Publish plan not found",
                )
            if publish_plan.run_id != run_id:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_MISMATCH",
                    error_summary="Publish plan does not belong to the current run",
                    publish_plan_ref=publish_plan.id,
                )
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if approval is None:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_APPROVAL_MISSING",
                    error_summary="Publish approval not found",
                    publish_plan_ref=publish_plan.id,
                )
            if approval.id != approval_ref:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_APPROVAL_MISMATCH",
                    error_summary="Publish approval does not match the current challenge",
                    publish_plan_ref=publish_plan.id,
                )
            if approval.approval_type != PUBLISH_APPROVAL_TYPE:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="APPROVAL_TYPE_MISMATCH",
                    error_summary="Approval is not a publish approval",
                    publish_plan_ref=publish_plan.id,
                )
            if approval.status != "pending":
                return PublishResumeOutcome(
                    status="complete",
                    publish_plan_ref=publish_plan.id,
                    plan_hash=publish_plan.plan_hash,
                    approval_ref=approval.id,
                    challenge_id=approval.challenge_id,
                    approval_revision=approval.revision,
                    current_stage="waiting_publish_approval",
                    current_node="wait_publish_confirmation",
                )
            if approval.revision != approval_revision:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_APPROVAL_REVISION_MISMATCH",
                    error_summary="Publish approval revision does not match",
                    publish_plan_ref=publish_plan.id,
                )
            if actor_id not in set(approval.requested_from or allowed_from):
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_APPROVAL_ACTOR_MISMATCH",
                    error_summary="Actor is not authorized for this approval",
                    publish_plan_ref=publish_plan.id,
                )
            recomputed_hash = build_publish_plan_hash(publish_plan.canonical_plan)
            if recomputed_hash != publish_plan.plan_hash:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_HASH_CORRUPTED",
                    error_summary="Persisted publish plan hash does not match canonical plan",
                    publish_plan_ref=publish_plan.id,
                )

            if normalized_action == APPROVAL_ACTION_APPROVE_PUBLISH:
                if presented_hash != recomputed_hash:
                    approval = self._mark_superseded_and_reissue(
                        session,
                        approval=approval,
                        publish_plan=publish_plan,
                        actor_id=actor_id,
                    )
                    session.commit()
                    session.refresh(approval)
                    return PublishResumeOutcome(
                        status="complete",
                        publish_plan_ref=publish_plan.id,
                        plan_hash=publish_plan.plan_hash,
                        approval_ref=approval.id,
                        approval_revision=approval.revision,
                        current_stage="waiting_publish_approval",
                        current_node="wait_publish_confirmation",
                    )

                approval.actor_id = actor_id
                approval.actor_type = "feishu_user"
                approval.decision = APPROVAL_ACTION_APPROVE_PUBLISH
                approval.decided_at = datetime.now(timezone.utc)
                approval.status = "approved"
                publish_plan.status = "approved"
                publish_plan.approved_at = datetime.now(timezone.utc)
                run.approved_publish_plan_id = publish_plan.id
                session.commit()
                return PublishResumeOutcome(
                    status="complete",
                    publish_plan_ref=publish_plan.id,
                    plan_hash=publish_plan.plan_hash,
                    approval_ref=approval.id,
                    challenge_id=approval.challenge_id,
                    approval_revision=approval.revision,
                    current_stage="publish_approved",
                    current_node="complete_run",
                )

            if normalized_action in {
                APPROVAL_ACTION_REGENERATE_REPORT,
                APPROVAL_ACTION_UPDATE_SUPPLEMENT,
            }:
                approval.actor_id = actor_id
                approval.actor_type = "feishu_user"
                approval.decision = normalized_action
                approval.decided_at = datetime.now(timezone.utc)
                if supplement is not None:
                    approval.supplement = dict(supplement)
                approval.status = "superseded"
                publish_plan.status = "invalidated"
                publish_plan.invalidated_at = datetime.now(timezone.utc)
                run.approved_publish_plan_id = None
                session.commit()
                return PublishResumeOutcome(
                    status="complete",
                    publish_plan_ref=publish_plan.id,
                    plan_hash=publish_plan.plan_hash,
                    approval_ref=approval.id,
                    challenge_id=approval.challenge_id,
                    approval_revision=approval.revision,
                    current_stage="generating_structured_report",
                    current_node="generate_structured_report",
                )

            if normalized_action == APPROVAL_ACTION_CANCEL_PUBLISH:
                approval.actor_id = actor_id
                approval.actor_type = "feishu_user"
                approval.decision = normalized_action
                approval.decided_at = datetime.now(timezone.utc)
                approval.status = "cancelled"
                publish_plan.status = "cancelled"
                publish_plan.invalidated_at = publish_plan.invalidated_at or datetime.now(timezone.utc)
                run.approved_publish_plan_id = None
                session.commit()
                return PublishResumeOutcome(
                    status="complete",
                    publish_plan_ref=publish_plan.id,
                    plan_hash=publish_plan.plan_hash,
                    approval_ref=approval.id,
                    challenge_id=approval.challenge_id,
                    approval_revision=approval.revision,
                    current_stage="cancelled",
                    current_node="complete_run",
                )

            raise ValueError(f"unsupported publish approval action: {action}")

    def reissue_publish_approval(
        self,
        *,
        run_id: str,
        publish_plan_ref: str,
        approval_ref: str,
        challenge_id: str,
        approval_revision: int,
        actor_id: str,
    ) -> PublishResumeOutcome:
        with self._session_factory() as session:
            publish_plan = session.get(PublishPlan, publish_plan_ref)
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if publish_plan is None or approval is None:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_PLAN_OR_APPROVAL_MISSING",
                    error_summary="Publish plan or approval not found",
                )
            if approval.id != approval_ref or approval.revision != approval_revision:
                return PublishResumeOutcome(
                    status="blocked",
                    error_code="PUBLISH_APPROVAL_MISMATCH",
                    error_summary="Publish approval does not match the current challenge",
                    publish_plan_ref=publish_plan.id,
                )
            approval = self._mark_superseded_and_reissue(
                session,
                approval=approval,
                publish_plan=publish_plan,
                actor_id=actor_id,
            )
            session.commit()
            session.refresh(approval)
            return PublishResumeOutcome(
                status="complete",
                publish_plan_ref=publish_plan.id,
                plan_hash=publish_plan.plan_hash,
                approval_ref=approval.id,
                challenge_id=approval.challenge_id,
                approval_revision=approval.revision,
                current_stage="waiting_publish_approval",
                current_node="wait_publish_confirmation",
            )

    def _mark_superseded_and_reissue(
        self,
        session: Session,
        *,
        approval: HumanApproval,
        publish_plan: PublishPlan,
        actor_id: str,
    ) -> HumanApproval:
        approval.actor_id = actor_id
        approval.actor_type = "feishu_user"
        approval.decision = APPROVAL_ACTION_REGENERATE_REPORT
        approval.decided_at = datetime.now(timezone.utc)
        approval.status = "superseded"
        next_revision = approval.revision + 1
        new_approval = HumanApproval(
            id=new_id(),
            run_id=approval.run_id,
            approval_type=PUBLISH_APPROVAL_TYPE,
            revision=next_revision,
            status="pending",
            challenge_id=new_id(),
            card_message_id=approval.card_message_id,
            requested_from=list(approval.requested_from or ["local-demo"]),
            request_payload_hash=publish_plan.plan_hash,
            plan_hash=publish_plan.plan_hash,
            actor_id=None,
            actor_type=None,
            decision=None,
            supplement=None,
            decided_at=None,
            expires_at=None,
        )
        publish_plan.status = "pending_approval"
        session.add(new_approval)
        session.flush()
        return new_approval

    def _load_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        return run

    def _load_project(self, session: Session, project_id: str) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"unknown project_id: {project_id}")
        return project

    def _record_tool_execution(
        self,
        session: Session,
        *,
        run_id: str,
        node_execution_id: str,
        tool_name: str,
        request_summary: Mapping[str, object],
        result_summary: Mapping[str, object],
        data_ref: str | None,
        status: Literal["success", "failed", "unknown"],
        error_class: str | None = None,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> ToolExecution:
        attempt = 1
        idempotency_key = canonical_json_hash(
            {
                "run_id": run_id,
                "node_execution_id": node_execution_id,
                "tool_name": tool_name,
                "request_summary": dict(request_summary),
                "result_summary": dict(result_summary),
                "data_ref": data_ref,
            }
        )
        existing = session.scalar(
            select(ToolExecution).where(
                ToolExecution.run_id == run_id,
                ToolExecution.idempotency_key == idempotency_key,
                ToolExecution.attempt == attempt,
            )
        )
        if existing is not None:
            return existing
        started_at = datetime.now(timezone.utc)
        record = ToolExecution(
            id=new_id(),
            run_id=run_id,
            node_execution_id=node_execution_id,
            tool_name=tool_name,
            tool_version="minimal.v1",
            attempt=attempt,
            idempotency_key=idempotency_key,
            request_summary=dict(request_summary),
            result_summary=dict(result_summary),
            data_ref=data_ref,
            provider_request_id=None,
            status=status,
            error_class=error_class,
            error_code=error_code,
            retryable=retryable,
            started_at=started_at,
            ended_at=started_at,
            duration_ms=0,
        )
        session.add(record)
        session.flush()
        return record


def _expected_publish_group_ref(run: ReportRun) -> str | None:
    return "feishu-publish-group-example" if run.period_key else None


def _archive_resource_ref(session: Session, project_id: str) -> str | None:
    project = session.get(Project, project_id)
    if project is None:
        return None
    return f"{project.id}:feishu-archive"


def _maybe_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if value is None:
        return None
    return str(value)
