from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    HumanApproval,
    PublishPlan,
    ReportArtifact,
    ReportRun,
    ReportVersion,
    RunStatusHistory,
    SideEffectOperation,
    ToolExecution,
)
from app.security.redaction import redact_sensitive

SessionFactory = Callable[[], Session]
_TERMINAL_RUN_STATUSES = {"completed", "blocked", "rejected", "cancelled"}
_TERMINAL_STAGES = {"succeeded", "blocked", "rejected", "cancelled"}


class RunDetailNotFoundError(ValueError):
    pass


class RunTimestampSummary(BaseModel):
    created_at: datetime
    latest_activity_at: datetime | None = None
    completed_at: datetime | None = None


class RunApprovalSummary(BaseModel):
    approval_type: str
    status: str
    revision: int
    challenge_id: str
    requested_from: list[str] = Field(default_factory=list)
    decision: str | None = None
    actor_id: str | None = None
    actor_type: str | None = None
    decided_at: datetime | None = None
    request_payload_hash: str
    plan_hash: str | None = None


class RunToolSummary(BaseModel):
    node_execution_id: str
    tool_name: str
    status: str
    attempt: int
    duration_ms: int | None = None
    data_ref: str | None = None
    retryable: bool
    error_code: str | None = None
    error_class: str | None = None
    request_summary: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)


class RunArtifactSummary(BaseModel):
    artifact_type: str
    operation_id: str
    external_id: str | None = None
    url: str | None = None
    status: str
    verified_at: datetime | None = None


class RunSideEffectSummary(BaseModel):
    operation_id: str
    sequence: int
    operation_type: str
    status: str
    attempt_count: int
    external_resource_id: str | None = None
    external_url: str | None = None
    verification_status: str | None = None
    last_error_class: str | None = None
    last_error_summary: str | None = None


class RunRefs(BaseModel):
    report_version_ref: str | None = None
    publish_plan_ref: str | None = None
    approved_publish_plan_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    operation_refs: list[str] = Field(default_factory=list)


class RunDetailView(BaseModel):
    run_id: str
    project_id: str
    period_key: str
    period_start: date
    period_end: date
    status: str
    current_stage: str
    current_node: str | None = None
    graph_version: str
    requester_id: str
    approval_status: str
    approval_revision: int
    error_code: str | None = None
    error_summary: str | None = None
    is_terminal: bool
    should_poll: bool
    polling_interval_ms: int
    timestamps: RunTimestampSummary
    approvals: list[RunApprovalSummary] = Field(default_factory=list)
    tools: list[RunToolSummary] = Field(default_factory=list)
    artifacts: list[RunArtifactSummary] = Field(default_factory=list)
    side_effects: list[RunSideEffectSummary] = Field(default_factory=list)
    refs: RunRefs


class RunDetailEnvelope(BaseModel):
    data: RunDetailView
    meta: dict[str, str]


@dataclass(slots=True)
class RunDetailService:
    session_factory: SessionFactory

    def load(self, run_id: str, *, request_id: str) -> RunDetailEnvelope:
        with self.session_factory() as session:
            run = session.get(ReportRun, run_id)
            if run is None:
                raise RunDetailNotFoundError(f"run not found: {run_id}")
            approvals = self._load_approvals(session, run_id)
            tools = self._load_tools(session, run_id)
            artifacts = self._load_artifacts(session, run_id)
            side_effects = self._load_side_effects(session, run_id)
            refs = self._load_refs(session, run, approvals, artifacts, side_effects)
            timestamps = self._build_timestamps(session, run_id)
            approval_status, approval_revision = self._build_approval_status(approvals)
            error_code, error_summary = self._build_error_summary(session, run_id, run, tools, side_effects)
            requester_id = self._build_requester_id(approvals, run.thread_id)

            detail = RunDetailView(
                run_id=run.id,
                project_id=run.project_id,
                period_key=run.period_key,
                period_start=run.period_start,
                period_end=run.period_end,
                status=run.status,
                current_stage=run.current_stage,
                current_node=run.current_node,
                graph_version=run.graph_version,
                requester_id=requester_id,
                approval_status=approval_status,
                approval_revision=approval_revision,
                error_code=error_code,
                error_summary=error_summary,
                is_terminal=self._is_terminal(run.status, run.current_stage),
                should_poll=not self._is_terminal(run.status, run.current_stage),
                polling_interval_ms=5000,
                timestamps=timestamps,
                approvals=approvals,
                tools=tools,
                artifacts=artifacts,
                side_effects=side_effects,
                refs=refs,
            )
            return RunDetailEnvelope(data=detail, meta={"request_id": request_id})

    def _load_approvals(self, session: Session, run_id: str) -> list[RunApprovalSummary]:
        rows = session.scalars(
            select(HumanApproval).where(HumanApproval.run_id == run_id).order_by(HumanApproval.created_at)
        ).all()
        approvals: list[RunApprovalSummary] = []
        for row in rows:
            approvals.append(
                RunApprovalSummary(
                    approval_type=row.approval_type,
                    status=row.status,
                    revision=row.revision,
                    challenge_id=row.challenge_id,
                    requested_from=list(row.requested_from or []),
                    decision=row.decision,
                    actor_id=row.actor_id,
                    actor_type=row.actor_type,
                    decided_at=row.decided_at,
                    request_payload_hash=row.request_payload_hash,
                    plan_hash=row.plan_hash,
                )
            )
        return approvals

    def _load_tools(self, session: Session, run_id: str) -> list[RunToolSummary]:
        rows = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id).order_by(
                ToolExecution.started_at, ToolExecution.attempt
            )
        ).all()
        tools: list[RunToolSummary] = []
        for row in rows:
            tools.append(
                RunToolSummary(
                    node_execution_id=row.node_execution_id,
                    tool_name=row.tool_name,
                    status=row.status,
                    attempt=row.attempt,
                    duration_ms=row.duration_ms,
                    data_ref=row.data_ref,
                    retryable=row.retryable,
                    error_code=row.error_code,
                    error_class=row.error_class,
                    request_summary=_summarize_mapping(row.request_summary),
                    result_summary=_summarize_mapping(row.result_summary),
                )
            )
        return tools

    def _load_artifacts(self, session: Session, run_id: str) -> list[RunArtifactSummary]:
        rows = session.scalars(
            select(ReportArtifact).where(ReportArtifact.run_id == run_id).order_by(ReportArtifact.created_at)
        ).all()
        artifacts: list[RunArtifactSummary] = []
        for row in rows:
            artifacts.append(
                RunArtifactSummary(
                    artifact_type=row.artifact_type,
                    operation_id=row.operation_id,
                    external_id=row.external_id,
                    url=row.url,
                    status=row.status,
                    verified_at=row.verified_at,
                )
            )
        return artifacts

    def _load_side_effects(self, session: Session, run_id: str) -> list[RunSideEffectSummary]:
        rows = session.scalars(
            select(SideEffectOperation).where(SideEffectOperation.run_id == run_id).order_by(
                SideEffectOperation.sequence
            )
        ).all()
        side_effects: list[RunSideEffectSummary] = []
        for row in rows:
            side_effects.append(
                RunSideEffectSummary(
                    operation_id=row.id,
                    sequence=row.sequence,
                    operation_type=row.operation_type,
                    status=row.status,
                    attempt_count=row.attempt_count,
                    external_resource_id=row.external_resource_id,
                    external_url=row.external_url,
                    verification_status=row.verification_status,
                    last_error_class=row.last_error_class,
                    last_error_summary=row.last_error_summary,
                )
            )
        return side_effects

    def _load_refs(
        self,
        session: Session,
        run: ReportRun,
        approvals: Sequence[RunApprovalSummary],
        artifacts: Sequence[RunArtifactSummary],
        side_effects: Sequence[RunSideEffectSummary],
    ) -> RunRefs:
        report_version = session.scalar(
            select(ReportVersion).where(ReportVersion.run_id == run.id).order_by(ReportVersion.created_at.desc())
        )
        publish_plan = (
            session.get(PublishPlan, run.approved_publish_plan_id)
            if run.approved_publish_plan_id is not None
            else None
        )
        if publish_plan is None:
            publish_plan = session.scalar(
                select(PublishPlan).where(PublishPlan.run_id == run.id).order_by(PublishPlan.created_at.desc())
            )
        approved_publish_plan_ref = publish_plan.id if publish_plan is not None else None
        artifact_refs = [artifact.external_id or artifact.operation_id for artifact in artifacts]
        operation_refs = [side_effect.operation_id for side_effect in side_effects]
        return RunRefs(
            report_version_ref=report_version.id if report_version is not None else None,
            publish_plan_ref=publish_plan.id if publish_plan is not None else None,
            approved_publish_plan_ref=approved_publish_plan_ref,
            artifact_refs=artifact_refs,
            operation_refs=operation_refs,
        )

    def _build_timestamps(self, session: Session, run_id: str) -> RunTimestampSummary:
        run = session.get(ReportRun, run_id)
        if run is None:
            raise RunDetailNotFoundError(f"run not found: {run_id}")
        latest_activity_at = session.scalar(_latest_activity_query(run_id))
        completed_at = latest_activity_at if self._is_terminal(run.status, run.current_stage) else None
        return RunTimestampSummary(
            created_at=run.created_at,
            latest_activity_at=latest_activity_at,
            completed_at=completed_at,
        )

    def _build_approval_status(self, approvals: Sequence[RunApprovalSummary]) -> tuple[str, int]:
        if not approvals:
            return "none", 0
        latest = approvals[-1]
        return latest.status, latest.revision

    def _build_error_summary(
        self,
        session: Session,
        run_id: str,
        run: ReportRun,
        tools: Sequence[RunToolSummary],
        side_effects: Sequence[RunSideEffectSummary],
    ) -> tuple[str | None, str | None]:
        failed_tool = next((tool for tool in reversed(tools) if tool.status == "failed"), None)
        if failed_tool is not None:
            return failed_tool.error_code, failed_tool.error_class or failed_tool.error_code
        failed_side_effect = next((item for item in reversed(side_effects) if item.status == "failed"), None)
        if failed_side_effect is not None:
            return failed_side_effect.last_error_class, failed_side_effect.last_error_summary
        if run.status == "blocked":
            history = session.scalar(
                select(RunStatusHistory)
                .where(RunStatusHistory.run_id == run_id)
                .order_by(RunStatusHistory.created_at.desc())
            )
            if history is not None:
                return history.reason_code, history.node_name
        return None, None

    def _build_requester_id(
        self, approvals: Sequence[RunApprovalSummary], fallback: str | None
    ) -> str:
        for approval in approvals:
            if approval.requested_from:
                return approval.requested_from[0]
        if fallback:
            return fallback
        return "local-demo"

    def _is_terminal(self, status: str, current_stage: str) -> bool:
        return status in _TERMINAL_RUN_STATUSES or current_stage in _TERMINAL_STAGES


def _latest_activity_query(run_id: str) -> Select[tuple[datetime | None]]:
    return select(func.max(RunStatusHistory.created_at)).where(RunStatusHistory.run_id == run_id)


def _summarize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    redacted = redact_sensitive(value)
    return _shrink_value(redacted)


def _shrink_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value if len(value) <= 240 else f"{value[:237]}..."
    if isinstance(value, Mapping):
        items = list(value.items())[:8]
        return {str(key): _shrink_value(item, depth + 1) for key, item in items}
    if isinstance(value, list):
        return [_shrink_value(item, depth + 1) for item in value[:8]]
    if isinstance(value, tuple):
        return [_shrink_value(item, depth + 1) for item in value[:8]]
    if isinstance(value, set):
        return [_shrink_value(item, depth + 1) for item in sorted(value, key=repr)[:8]]
    return value
