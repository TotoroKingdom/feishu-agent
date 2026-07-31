from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    EvidenceItem,
    EvidenceSet,
    DiagnosisRecord,
    HumanApproval,
    LlmExecution,
    PublishPlan,
    ReportArtifact,
    NodeExecution,
    ReportRun,
    RunStatusHistory,
    SideEffectOperation,
    ToolExecution,
)
from app.security.redaction import redact_sensitive

SessionFactory = Callable[[], Session]
_MAX_LIMIT = 100


class RunObservabilityNotFoundError(ValueError):
    pass


@dataclass(slots=True)
class RunObservabilityQueryService:
    session_factory: SessionFactory

    def timeline(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            events = self._timeline_events(session, run_id)
            return self._page(events, cursor=cursor, limit=limit)

    def nodes(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(NodeExecution)
                .where(NodeExecution.run_id == run_id)
                .order_by(NodeExecution.started_at, NodeExecution.node_attempt, NodeExecution.id)
            ).all()
            items = [self._node_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def tools(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(ToolExecution)
                .where(ToolExecution.run_id == run_id)
                .order_by(ToolExecution.started_at, ToolExecution.attempt, ToolExecution.id)
            ).all()
            items = [self._tool_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def llm_executions(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(LlmExecution)
                .where(LlmExecution.run_id == run_id)
                .order_by(LlmExecution.created_at, LlmExecution.id)
            ).all()
            items = [self._llm_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def diagnoses(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(DiagnosisRecord)
                .where(DiagnosisRecord.run_id == run_id)
                .order_by(DiagnosisRecord.created_at, DiagnosisRecord.attempt, DiagnosisRecord.id)
            ).all()
            items = [self._diagnosis_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def audit_logs(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(AuditLog)
                .where(AuditLog.run_id == run_id)
                .order_by(AuditLog.occurred_at, AuditLog.id)
            ).all()
            items = [self._audit_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def approvals(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(HumanApproval).where(HumanApproval.run_id == run_id).order_by(
                    HumanApproval.created_at, HumanApproval.revision, HumanApproval.id
                )
            ).all()
            items = [self._approval_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def artifacts(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(ReportArtifact)
                .where(ReportArtifact.run_id == run_id)
                .order_by(ReportArtifact.created_at, ReportArtifact.id)
            ).all()
            items = [self._artifact_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def side_effects(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(SideEffectOperation)
                .where(SideEffectOperation.run_id == run_id)
                .order_by(SideEffectOperation.sequence, SideEffectOperation.id)
            ).all()
            items = [self._side_effect_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def evidence(
        self, run_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            rows = session.scalars(
                select(EvidenceItem)
                .join(EvidenceSet, EvidenceItem.evidence_set_id == EvidenceSet.id)
                .where(EvidenceSet.run_id == run_id)
                .order_by(EvidenceItem.created_at, EvidenceItem.id)
            ).all()
            items = [self._evidence_row(row) for row in rows]
            return self._page(items, cursor=cursor, limit=limit)

    def publish_plan(self, run_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            self._require_run(session, run_id)
            row = session.scalar(
                select(PublishPlan)
                .where(PublishPlan.run_id == run_id)
                .order_by(PublishPlan.version.desc(), PublishPlan.created_at.desc(), PublishPlan.id.desc())
            )
            if row is None:
                return None
            return self._publish_plan_row(row)

    def _require_run(self, session: Session, run_id: str) -> ReportRun:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise RunObservabilityNotFoundError(f"run not found: {run_id}")
        return run

    def _timeline_events(self, session: Session, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for row in session.scalars(
            select(RunStatusHistory)
            .where(RunStatusHistory.run_id == run_id)
            .order_by(RunStatusHistory.created_at, RunStatusHistory.id)
        ).all():
            events.append(
                {
                    "event_type": "status_transition",
                    "event_id": row.id,
                    "occurred_at": row.created_at,
                    "summary": {
                        "from_status": row.from_status,
                        "to_status": row.to_status,
                        "reason_code": row.reason_code,
                        "actor_type": row.actor_type,
                        "actor_id": row.actor_id,
                        "node_name": row.node_name,
                        "checkpoint_ref": row.checkpoint_ref,
                    },
                }
            )
        for row in session.scalars(
            select(NodeExecution)
            .where(NodeExecution.run_id == run_id)
            .order_by(NodeExecution.started_at, NodeExecution.node_attempt, NodeExecution.id)
        ).all():
            events.append(
                {
                    "event_type": "node_execution",
                    "event_id": row.id,
                    "occurred_at": row.started_at,
                    "summary": self._node_row(row),
                }
            )
        for row in session.scalars(
            select(ToolExecution)
            .where(ToolExecution.run_id == run_id)
            .order_by(ToolExecution.started_at, ToolExecution.attempt, ToolExecution.id)
        ).all():
            events.append(
                {
                    "event_type": "tool_execution",
                    "event_id": row.id,
                    "occurred_at": row.started_at,
                    "summary": self._tool_row(row),
                }
            )
        for row in session.scalars(
            select(LlmExecution)
            .where(LlmExecution.run_id == run_id)
            .order_by(LlmExecution.created_at, LlmExecution.id)
        ).all():
            events.append(
                {
                    "event_type": "llm_execution",
                    "event_id": row.id,
                    "occurred_at": row.created_at,
                    "summary": self._llm_row(row),
                }
            )
        for row in session.scalars(
            select(DiagnosisRecord)
            .where(DiagnosisRecord.run_id == run_id)
            .order_by(DiagnosisRecord.created_at, DiagnosisRecord.attempt, DiagnosisRecord.id)
        ).all():
            events.append(
                {
                    "event_type": "diagnosis_record",
                    "event_id": row.id,
                    "occurred_at": row.created_at,
                    "summary": self._diagnosis_row(row),
                }
            )
        for row in session.scalars(
            select(AuditLog)
            .where(AuditLog.run_id == run_id)
            .order_by(AuditLog.occurred_at, AuditLog.id)
        ).all():
            events.append(
                {
                    "event_type": "audit_log",
                    "event_id": row.id,
                    "occurred_at": row.occurred_at,
                    "summary": self._audit_row(row),
                }
            )
        events.sort(
            key=lambda item: (
                item["occurred_at"] or datetime.min.replace(tzinfo=timezone.utc),
                item["event_type"],
                str(item["event_id"]),
            )
        )
        return events

    def _node_row(self, row: NodeExecution) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "node_name": row.node_name,
            "node_attempt": row.node_attempt,
            "checkpoint_before": row.checkpoint_before,
            "checkpoint_after": row.checkpoint_after,
            "status": row.status,
            "input_summary": redact_sensitive(dict(row.input_summary or {})),
            "output_summary": redact_sensitive(dict(row.output_summary or {})),
            "error_class": row.error_class,
            "error_summary": row.error_summary,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "duration_ms": row.duration_ms,
        }

    def _tool_row(self, row: ToolExecution) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "node_execution_id": row.node_execution_id,
            "tool_name": row.tool_name,
            "tool_version": row.tool_version,
            "attempt": row.attempt,
            "idempotency_key": row.idempotency_key,
            "request_summary": redact_sensitive(dict(row.request_summary or {})),
            "result_summary": redact_sensitive(dict(row.result_summary or {})),
            "data_ref": row.data_ref,
            "provider_request_id": row.provider_request_id,
            "status": row.status,
            "error_class": row.error_class,
            "error_code": row.error_code,
            "retryable": row.retryable,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "duration_ms": row.duration_ms,
        }

    def _llm_row(self, row: LlmExecution) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "node_execution_id": row.node_execution_id,
            "provider": row.provider,
            "model": row.model,
            "prompt_type": row.prompt_type,
            "prompt_version_id": row.prompt_version_id,
            "input_hash": row.input_hash,
            "output_ref": row.output_ref,
            "status": row.status,
            "schema_valid": row.schema_valid,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "total_tokens": row.total_tokens,
            "duration_ms": row.duration_ms,
            "error_class": row.error_class,
            "created_at": row.created_at,
        }

    def _diagnosis_row(self, row: DiagnosisRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "validation_result_id": row.validation_result_id,
            "problem_key": row.problem_key,
            "problem_type": row.problem_type,
            "severity": row.severity,
            "observation": redact_sensitive(dict(row.observation or {})),
            "diagnosis": redact_sensitive(dict(row.diagnosis or {})),
            "impact_scope": redact_sensitive(dict(row.impact_scope or {})),
            "recoverability": row.recoverability,
            "planned_action": row.planned_action,
            "action_params": redact_sensitive(dict(row.action_params or {})),
            "attempt": row.attempt,
            "result": row.result,
            "next_node": row.next_node,
            "created_at": row.created_at,
            "resolved_at": row.resolved_at,
        }

    def _audit_row(self, row: AuditLog) -> dict[str, Any]:
        return {
            "id": row.id,
            "occurred_at": row.occurred_at,
            "request_id": row.request_id,
            "run_id": row.run_id,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "before_summary": redact_sensitive(dict(row.before_summary or {})),
            "after_summary": redact_sensitive(dict(row.after_summary or {})),
            "result": row.result,
            "ip_hash": row.ip_hash,
            "metadata": redact_sensitive(dict(row.metadata_ or {})),
        }

    def _approval_row(self, row: HumanApproval) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "approval_type": row.approval_type,
            "revision": row.revision,
            "status": row.status,
            "challenge_id": row.challenge_id,
            "card_message_id": row.card_message_id,
            "requested_from": list(row.requested_from or []),
            "request_payload_hash": row.request_payload_hash,
            "plan_hash": row.plan_hash,
            "actor_id": row.actor_id,
            "actor_type": row.actor_type,
            "decision": row.decision,
            "supplement": redact_sensitive(dict(row.supplement or {})) if row.supplement else None,
            "decided_at": row.decided_at,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        }

    def _artifact_row(self, row: ReportArtifact) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "report_version_id": row.report_version_id,
            "artifact_type": row.artifact_type,
            "operation_id": row.operation_id,
            "external_id": row.external_id,
            "url": row.url,
            "target_ref": row.target_ref,
            "content_hash": row.content_hash,
            "status": row.status,
            "created_at": row.created_at,
            "verified_at": row.verified_at,
        }

    def _side_effect_row(self, row: SideEffectOperation) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "publish_plan_id": row.publish_plan_id,
            "sequence": row.sequence,
            "operation_type": row.operation_type,
            "target_ref": row.target_ref,
            "target_hash": row.target_hash,
            "payload_ref": row.payload_ref,
            "payload_hash": row.payload_hash,
            "idempotency_key": row.idempotency_key,
            "status": row.status,
            "attempt_count": row.attempt_count,
            "external_resource_id": row.external_resource_id,
            "external_url": row.external_url,
            "provider_request_id": row.provider_request_id,
            "verification_status": row.verification_status,
            "last_error_class": row.last_error_class,
            "last_error_summary": row.last_error_summary,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "updated_at": row.updated_at,
            "version": row.version,
        }

    def _evidence_row(self, row: EvidenceItem) -> dict[str, Any]:
        return {
            "id": row.id,
            "evidence_set_id": row.evidence_set_id,
            "evidence_key": row.evidence_key,
            "source_type": row.source_type,
            "source_resource_id": row.source_resource_id,
            "external_id": row.external_id,
            "url": row.url,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "evidence_summary": row.evidence_summary,
            "confidence": row.confidence,
            "normalized_entity_id": row.normalized_entity_id,
            "content_hash": row.content_hash,
            "created_at": row.created_at,
        }

    def _publish_plan_row(self, row: PublishPlan) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "report_version_id": row.report_version_id,
            "version": row.version,
            "status": row.status,
            "canonical_plan": redact_sensitive(dict(row.canonical_plan or {})),
            "plan_hash": row.plan_hash,
            "content_version": row.content_version,
            "created_at": row.created_at,
            "approved_at": row.approved_at,
            "invalidated_at": row.invalidated_at,
        }

    def _page(
        self, items: list[dict[str, Any]], *, cursor: str | None, limit: int
    ) -> dict[str, object]:
        page_limit = self._normalize_limit(limit)
        offset = self._normalize_cursor(cursor)
        sliced = items[offset : offset + page_limit]
        next_cursor = str(offset + len(sliced)) if offset + len(sliced) < len(items) else None
        return {
            "items": sliced,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

    def _normalize_cursor(self, cursor: str | None) -> int:
        if cursor in {None, ""}:
            return 0
        try:
            offset = int(cursor)
        except ValueError as error:
            raise ValueError("cursor must be a non-negative integer") from error
        if offset < 0:
            raise ValueError("cursor must be a non-negative integer")
        return offset

    def _normalize_limit(self, limit: int) -> int:
        if limit < 1 or limit > _MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_LIMIT}")
        return limit
