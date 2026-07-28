from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
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
