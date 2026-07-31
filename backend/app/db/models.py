from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid4())


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (UniqueConstraint("username", name="uq_admin_users_username"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="active")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_admin_sessions_refresh_token_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    admin_user_id: Mapped[str] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)


class LoginAudit(Base):
    __tablename__ = "login_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    admin_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    default_period_rule: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    default_prompt_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_versions.id"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectRepository(Base):
    __tablename__ = "project_repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repository_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_connectivity_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_connectivity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "external_id", name="uq_project_repo"),
    )


class ScheduleConfig(Base):
    __tablename__ = "schedule_configs"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_schedule_configs_project_id"),
        Index("ix_schedule_configs_enabled_next_fire_at", "enabled", "next_fire_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    cron_expression: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    misfire_policy: Mapped[str] = mapped_column(String(24), default="fire_once")
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeishuResource(Base):
    __tablename__ = "feishu_resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(300))
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    last_connectivity_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_connectivity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (UniqueConstraint("project_id", "resource_type", name="uq_feishu_resource"),)


class FeishuFieldMapping(Base):
    __tablename__ = "feishu_field_mappings"
    __table_args__ = (
        UniqueConstraint("resource_id", "logical_field", name="uq_feishu_field_mappings_logical"),
        UniqueConstraint(
            "resource_id", "external_field_id", name="uq_feishu_field_mappings_external"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("feishu_resources.id", ondelete="CASCADE"), index=True
    )
    logical_field: Mapped[str] = mapped_column(String(128))
    external_field_id: Mapped[str] = mapped_column(String(128))
    external_field_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_field_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    converter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    required_level: Mapped[str] = mapped_column(String(16))
    mapping_options: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EncryptedCredential(Base):
    __tablename__ = "encrypted_credentials"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "credential_type", "label", name="uq_encrypted_credentials_label"
        ),
        UniqueConstraint("fingerprint", name="uq_encrypted_credentials_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    credential_type: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(128))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(128))
    updated_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class ModelConfig(Base):
    __tablename__ = "model_configs"
    __table_args__ = (UniqueConstraint("scope", name="uq_model_configs_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model: Mapped[str] = mapped_column(String(128))
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    stream: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_type", "version", name="uq_prompt_versions_type_version"),
        Index("ix_prompt_versions_type_status", "prompt_type", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prompt_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    model_constraints: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AsyncJob(Base):
    __tablename__ = "async_jobs"
    __table_args__ = (
        UniqueConstraint("job_type", "requested_by", "request_hash", name="uq_async_jobs_request"),
        Index("ix_async_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("report_runs.id"), nullable=True, index=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    __table_args__ = (
        UniqueConstraint("run_id", "input_snapshot_hash", name="uq_validation_results"),
    )

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


class DiagnosisRecord(Base):
    __tablename__ = "diagnosis_records"
    __table_args__ = (
        UniqueConstraint("run_id", "problem_key", "attempt", name="uq_diagnosis_records_attempt"),
        Index("ix_diagnosis_records_run_created_at", "run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    validation_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("validation_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    problem_key: Mapped[str] = mapped_column(String(128))
    problem_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(24))
    observation: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    diagnosis: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    impact_scope: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    recoverability: Mapped[str] = mapped_column(String(24))
    planned_action: Mapped[str] = mapped_column(String(64))
    action_params: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    attempt: Mapped[int] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(24))
    next_node: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NodeExecution(Base):
    __tablename__ = "node_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "node_name", "node_attempt", name="uq_node_executions_attempt"),
        Index("ix_node_executions_run_started", "run_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    node_name: Mapped[str] = mapped_column(String(80))
    node_attempt: Mapped[int] = mapped_column(Integer)
    checkpoint_before: Mapped[str | None] = mapped_column(String(256), nullable=True)
    checkpoint_after: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    input_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LlmExecution(Base):
    __tablename__ = "llm_executions"
    __table_args__ = (
        Index("ix_llm_executions_run_created", "run_id", "created_at"),
        Index("ix_llm_executions_node_created", "node_execution_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    node_execution_id: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_type: Mapped[str] = mapped_column(String(32))
    prompt_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_versions.id"), nullable=True, index=True
    )
    input_hash: Mapped[str] = mapped_column(String(64))
    output_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24))
    schema_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_run_occurred_at", "run_id", "occurred_at"),
        Index("ix_audit_logs_actor_occurred_at", "actor_id", "occurred_at"),
        Index("ix_audit_logs_action_occurred_at", "action", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(128))
    before_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    after_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(24))
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)


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


class SideEffectOperation(Base):
    __tablename__ = "side_effect_operations"
    __table_args__ = (
        UniqueConstraint("publish_plan_id", "sequence", name="uq_side_effect_operations_sequence"),
        UniqueConstraint("idempotency_key", name="uq_side_effect_operations_idempotency_key"),
        Index("ix_side_effect_operations_run_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publish_plan_id: Mapped[str] = mapped_column(
        ForeignKey("publish_plans.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    operation_type: Mapped[str] = mapped_column(String(64))
    target_ref: Mapped[str] = mapped_column(String(512))
    target_hash: Mapped[str] = mapped_column(String(64))
    payload_ref: Mapped[str] = mapped_column(String(512))
    payload_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    external_resource_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class SideEffectAttempt(Base):
    __tablename__ = "side_effect_attempts"
    __table_args__ = (UniqueConstraint("operation_id", "attempt", name="uq_side_effect_attempts"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("side_effect_operations.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    request_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    provider_request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    response_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportArtifact(Base):
    __tablename__ = "report_artifacts"
    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_report_artifacts_operation"),
        Index("ix_report_artifacts_run_type", "run_id", "artifact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), index=True
    )
    report_version_id: Mapped[str] = mapped_column(
        ForeignKey("report_versions.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32))
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("side_effect_operations.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_ref: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CallbackEvent(Base):
    __tablename__ = "callback_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_callback_events_provider_event_id",
        ),
        Index("ix_callback_events_run_id", "run_id"),
        Index("ix_callback_events_status_received_at", "status", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    external_event_id: Mapped[str] = mapped_column(String(256))
    event_type: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="received")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_outbox_messages_dedupe_key"),
        Index("ix_outbox_messages_status_available_at", "status", "available_at"),
        Index("ix_outbox_messages_topic", "topic"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(String(128))
    aggregate_type: Mapped[str] = mapped_column(String(64))
    aggregate_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_request_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)


class FeishuMessageDelivery(Base):
    __tablename__ = "feishu_message_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_feishu_message_deliveries_idempotency_key"),
        UniqueConstraint(
            "run_id",
            "purpose",
            "revision",
            "recipient_type",
            "recipient_id",
            name="uq_feishu_message_deliveries_run_purpose_revision_recipient",
        ),
        Index("ix_feishu_message_deliveries_status_created_at", "status", "created_at"),
        Index("ix_feishu_message_deliveries_run_id", "run_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=True
    )
    onboarding_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    recipient_type: Mapped[str] = mapped_column(String(16))
    recipient_id: Mapped[str] = mapped_column(String(128))
    content_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    external_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReportClaim(Base):
    __tablename__ = "report_claims"
    __table_args__ = (UniqueConstraint("report_version_id", "claim_key", name="uq_report_claims"),)

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
    __table_args__ = (UniqueConstraint("claim_id", "evidence_item_id", name="uq_report_evidence"),)

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
        Index("ix_tool_executions_run_started", "run_id", "started_at"),
        Index("ix_tool_executions_tool_status_started", "tool_name", "status", "started_at"),
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
