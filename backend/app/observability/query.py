from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    DiagnosisRecord,
    LlmExecution,
    NodeExecution,
    ReportRun,
    ToolExecution,
)
from app.security.redaction import redact_sensitive

SessionFactory = Callable[[], Session]
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


class ObservabilityNotFoundError(ValueError):
    pass


@dataclass(slots=True)
class QueryPage:
    items: list[dict[str, object]]
    cursor: str | None
    next_cursor: str | None
    has_more: bool

    def model_dump(self) -> dict[str, object]:
        return {
            "items": self.items,
            "cursor": self.cursor,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
        }


@dataclass(slots=True)
class RunObservabilityQueryService:
    session_factory: SessionFactory

    def timeline(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            items = self._timeline_items(session, run_id)
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def nodes(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            rows = session.scalars(
                select(NodeExecution)
                .where(NodeExecution.run_id == run_id)
                .order_by(NodeExecution.started_at, NodeExecution.node_name, NodeExecution.node_attempt)
            ).all()
            items = [self._node_item(row) for row in rows]
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def tools(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            rows = session.scalars(
                select(ToolExecution)
                .where(ToolExecution.run_id == run_id)
                .order_by(ToolExecution.started_at, ToolExecution.attempt)
            ).all()
            items = [self._tool_item(row) for row in rows]
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def llm_executions(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            rows = session.scalars(
                select(LlmExecution)
                .where(LlmExecution.run_id == run_id)
                .order_by(LlmExecution.created_at, LlmExecution.id)
            ).all()
            items = [self._llm_item(row) for row in rows]
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def diagnoses(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            rows = session.scalars(
                select(DiagnosisRecord)
                .where(DiagnosisRecord.run_id == run_id)
                .order_by(DiagnosisRecord.created_at, DiagnosisRecord.attempt)
            ).all()
            items = [self._diagnosis_item(row) for row in rows]
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def audit_logs(
        self,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            self._ensure_run_exists(session, run_id)
            rows = session.scalars(
                select(AuditLog)
                .where(AuditLog.run_id == run_id)
                .order_by(AuditLog.occurred_at, AuditLog.id)
            ).all()
            items = [self._audit_item(row) for row in rows]
            return self._paginate(items, cursor=cursor, limit=limit).model_dump()

    def _ensure_run_exists(self, session: Session, run_id: str) -> None:
        if session.get(ReportRun, run_id) is None:
            raise ObservabilityNotFoundError(f"run not found: {run_id}")

    def _timeline_items(self, session: Session, run_id: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        rows.extend(self._node_item(node) for node in session.scalars(
            select(NodeExecution)
            .where(NodeExecution.run_id == run_id)
            .order_by(NodeExecution.started_at, NodeExecution.node_name, NodeExecution.node_attempt)
        ).all())
        rows.extend(self._tool_item(tool) for tool in session.scalars(
            select(ToolExecution)
            .where(ToolExecution.run_id == run_id)
            .order_by(ToolExecution.started_at, ToolExecution.attempt)
        ).all())
        rows.extend(self._llm_item(llm) for llm in session.scalars(
            select(LlmExecution)
            .where(LlmExecution.run_id == run_id)
            .order_by(LlmExecution.created_at, LlmExecution.id)
        ).all())
        rows.extend(self._diagnosis_item(diagnosis) for diagnosis in session.scalars(
            select(DiagnosisRecord)
            .where(DiagnosisRecord.run_id == run_id)
            .order_by(DiagnosisRecord.created_at, DiagnosisRecord.attempt)
        ).all())
        rows.extend(self._audit_item(audit) for audit in session.scalars(
            select(AuditLog)
            .where(AuditLog.run_id == run_id)
            .order_by(AuditLog.occurred_at, AuditLog.id)
        ).all())
        rows.sort(key=lambda item: (str(item["occurred_at"]), str(item["event_type"]), str(item["id"])))
        return rows

    def _paginate(
        self, items: Sequence[dict[str, object]], *, cursor: str | None, limit: int
    ) -> QueryPage:
        page_size = self._validate_limit(limit)
        start = self._parse_cursor(cursor)
        slice_items = list(items[start : start + page_size])
        next_cursor = str(start + page_size) if start + page_size < len(items) else None
        return QueryPage(
            items=slice_items,
            cursor=cursor if cursor is not None else None,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    def _validate_limit(self, limit: int) -> int:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        return min(limit, MAX_PAGE_SIZE)

    def _parse_cursor(self, cursor: str | None) -> int:
        if cursor is None or cursor == "":
            return 0
        try:
            offset = int(cursor)
        except ValueError as error:
            raise ValueError("cursor must be an integer offset") from error
        if offset < 0:
            raise ValueError("cursor must be non-negative")
        return offset

    def _node_item(self, row: NodeExecution) -> dict[str, object]:
        return {
            "event_type": "node_execution",
            "id": row.id,
            "run_id": row.run_id,
            "occurred_at": _iso(row.started_at),
            "node_name": row.node_name,
            "node_attempt": row.node_attempt,
            "checkpoint_before": row.checkpoint_before,
            "checkpoint_after": row.checkpoint_after,
            "status": row.status,
            "input_summary": _redact_mapping(row.input_summary),
            "output_summary": _redact_mapping(row.output_summary),
            "error_class": row.error_class,
            "error_summary": row.error_summary,
            "started_at": _iso(row.started_at),
            "ended_at": _iso(row.ended_at),
            "duration_ms": row.duration_ms,
        }

    def _tool_item(self, row: ToolExecution) -> dict[str, object]:
        return {
            "event_type": "tool_execution",
            "id": row.id,
            "run_id": row.run_id,
            "occurred_at": _iso(row.started_at),
            "node_execution_id": row.node_execution_id,
            "tool_name": row.tool_name,
            "tool_version": row.tool_version,
            "attempt": row.attempt,
            "status": row.status,
            "request_summary": _redact_mapping(row.request_summary),
            "result_summary": _redact_mapping(row.result_summary),
            "data_ref": row.data_ref,
            "provider_request_id": row.provider_request_id,
            "error_class": row.error_class,
            "error_code": row.error_code,
            "retryable": row.retryable,
            "started_at": _iso(row.started_at),
            "ended_at": _iso(row.ended_at),
            "duration_ms": row.duration_ms,
        }

    def _llm_item(self, row: LlmExecution) -> dict[str, object]:
        return {
            "event_type": "llm_execution",
            "id": row.id,
            "run_id": row.run_id,
            "occurred_at": _iso(row.created_at),
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
        }

    def _diagnosis_item(self, row: DiagnosisRecord) -> dict[str, object]:
        return {
            "event_type": "diagnosis",
            "id": row.id,
            "run_id": row.run_id,
            "occurred_at": _iso(row.created_at),
            "problem_key": row.problem_key,
            "problem_type": row.problem_type,
            "severity": row.severity,
            "observation": _redact_mapping(row.observation),
            "diagnosis": _redact_mapping(row.diagnosis),
            "impact_scope": _redact_mapping(row.impact_scope),
            "recoverability": row.recoverability,
            "planned_action": row.planned_action,
            "action_params": _redact_mapping(row.action_params),
            "attempt": row.attempt,
            "result": row.result,
            "next_node": row.next_node,
            "resolved_at": _iso(row.resolved_at),
        }

    def _audit_item(self, row: AuditLog) -> dict[str, object]:
        return {
            "event_type": "audit_log",
            "id": row.id,
            "run_id": row.run_id,
            "occurred_at": _iso(row.occurred_at),
            "request_id": row.request_id,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "before_summary": _redact_mapping(row.before_summary),
            "after_summary": _redact_mapping(row.after_summary),
            "result": row.result,
            "ip_hash": row.ip_hash,
            "metadata": _redact_mapping(row.metadata_),
        }


def _redact_mapping(value: Mapping[str, object] | None) -> dict[str, object]:
    if value is None:
        return {}
    redacted = redact_sensitive(value)
    if isinstance(redacted, Mapping):
        return {str(key): _jsonable(item) for key, item in redacted.items()}
    return {}


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat() if value.tzinfo else value.replace(tzinfo=UTC).isoformat()
