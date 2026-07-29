from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid4())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectRepository(Base):
    __tablename__ = "project_repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "external_id", name="uq_project_repo"),
    )


class FeishuResource(Base):
    __tablename__ = "feishu_resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint("project_id", "resource_type", name="uq_feishu_resource"),)


class ReportRun(Base):
    __tablename__ = "report_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_report_runs_thread_id"),
        UniqueConstraint("project_id", "period_key", name="uq_report_runs_project_period"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(128))
    period_key: Mapped[str] = mapped_column(String(120))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="created")
    graph_version: Mapped[str] = mapped_column(String(32), default="weekly_report.v1")
    state_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    scope_revision: Mapped[int] = mapped_column(Integer, default=1)
    current_stage: Mapped[str] = mapped_column(String(40), default="created")
    current_node: Mapped[str | None] = mapped_column(String(80), nullable=True)
    approved_publish_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("publish_plans.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RunStatusHistory(Base):
    __tablename__ = "run_status_history"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    reason_code: Mapped[str] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(128))
    node_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    checkpoint_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanApproval(Base):
    __tablename__ = "human_approvals"
    __table_args__ = (
        UniqueConstraint("run_id", "approval_type", "revision", name="uq_human_approvals_revision"),
        UniqueConstraint("challenge_id", name="uq_human_approvals_challenge_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("report_runs.id"), index=True)
    approval_type: Mapped[str] = mapped_column(String(24))
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    challenge_id: Mapped[str] = mapped_column(String(36))
    card_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_from: Mapped[list[str]] = mapped_column(JSON, default=list)
    request_payload_hash: Mapped[str] = mapped_column(String(64))
    plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    supplement: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceDataBatch(Base):
    __tablename__ = "source_data_batches"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "source_type",
            "source_resource_id",
            "entity_type",
            "page_no",
            "payload_hash",
            name="uq_source_data_batches_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(24))
    source_resource_id: Mapped[str] = mapped_column(String(36))
    entity_type: Mapped[str] = mapped_column(String(32))
    page_no: Mapped[int] = mapped_column(Integer)
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(32))
    fetch_status: Mapped[str] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NormalizedSnapshot(Base):
    __tablename__ = "normalized_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "content_hash", name="uq_normalized_snapshots"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    source_batch_set_hash: Mapped[str] = mapped_column(String(64))
    mapping_revision: Mapped[str] = mapped_column(String(32))
    normalizer_version: Mapped[str] = mapped_column(String(32))
    entity_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NormalizedEntity(Base):
    __tablename__ = "normalized_entities"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "source_type",
            "source_resource_id",
            "entity_type",
            "external_id",
            "content_hash",
            name="uq_normalized_entities_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    normalized_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_snapshots.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(24))
    entity_type: Mapped[str] = mapped_column(String(32))
    source_resource_id: Mapped[str] = mapped_column(String(36))
    external_id: Mapped[str] = mapped_column(String(128))
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    author_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assignee_external_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    labels: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    milestone_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at_external: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at_external: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at_external: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attributes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = (UniqueConstraint("run_id", "input_snapshot_hash", name="uq_validation_results"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    validation_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    data_quality_status: Mapped[str] = mapped_column(String(24))
    rule_set_version: Mapped[str] = mapped_column(String(32))
    critical_count: Mapped[int] = mapped_column(Integer)
    warning_count: Mapped[int] = mapped_column(Integer)
    missing_items: Mapped[list[str]] = mapped_column(JSON, default=list)
    conflicts: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "normalized_snapshot_id",
            "definition_version",
            "content_hash",
            name="uq_metric_snapshots",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    normalized_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_snapshots.id", ondelete="CASCADE"), index=True
    )
    definition_version: Mapped[str] = mapped_column(String(32))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceSet(Base):
    __tablename__ = "evidence_sets"
    __table_args__ = (UniqueConstraint("run_id", "content_hash", name="uq_evidence_sets"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    normalized_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_snapshots.id", ondelete="CASCADE"), index=True
    )
    metric_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("metric_snapshots.id", ondelete="CASCADE"), index=True
    )
    builder_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("evidence_set_id", "evidence_key", name="uq_evidence_items"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evidence_set_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_sets.id", ondelete="CASCADE"), index=True
    )
    evidence_key: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(24))
    source_resource_id: Mapped[str] = mapped_column(String(36))
    external_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    normalized_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("normalized_entities.id", ondelete="CASCADE"), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("run_id", "version", name="uq_report_versions_version"),
        UniqueConstraint("run_id", "content_hash", name="uq_report_versions_content_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    structured_report: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    structured_hash: Mapped[str] = mapped_column(String(64))
    rendered_content: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    data_snapshot_hash: Mapped[str] = mapped_column(String(64))
    prompt_version_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_info: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    data_quality_status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublishPlan(Base):
    __tablename__ = "publish_plans"
    __table_args__ = (
        UniqueConstraint("run_id", "version", name="uq_publish_plans_version"),
        UniqueConstraint("run_id", "plan_hash", name="uq_publish_plans_plan_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    report_version_id: Mapped[str] = mapped_column(
        ForeignKey("report_versions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    canonical_plan: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    plan_hash: Mapped[str] = mapped_column(String(64))
    content_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportClaim(Base):
    __tablename__ = "report_claims"
    __table_args__ = (
        UniqueConstraint("report_version_id", "claim_key", name="uq_report_claims"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_version_id: Mapped[str] = mapped_column(
        ForeignKey("report_versions.id", ondelete="CASCADE"), index=True
    )
    claim_key: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(String(1024))
    claim_type: Mapped[str] = mapped_column(String(24))
    importance: Mapped[str] = mapped_column(String(24))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    grounding_status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportEvidence(Base):
    __tablename__ = "report_evidence"
    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_item_id", name="uq_report_evidence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("report_claims.id", ondelete="CASCADE"), index=True
    )
    evidence_item_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True
    )
    citation_order: Mapped[int] = mapped_column(Integer)
    relevance_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "idempotency_key", "attempt", name="uq_tool_executions_attempt"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    node_execution_id: Mapped[str] = mapped_column(String(128))
    tool_name: Mapped[str] = mapped_column(String(128))
    tool_version: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    data_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(24))
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
