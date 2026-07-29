from __future__ import annotations

from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime
from app.db.models import (
    Base,
    EvidenceItem,
    EvidenceSet,
    MetricSnapshot,
    Project,
    ReportClaim,
    ReportEvidence,
    ReportRun,
    ReportVersion,
    ToolExecution,
)
from app.domain.runs import RunCreationService
from app.reports.metrics import extract_metric_values


def make_runtime() -> tuple[WorkflowRuntime, str, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        session.commit()
        run_id = run.id
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    runtime = WorkflowRuntime(factory, MemorySaver())
    return runtime, run_id, factory


def _approval_payload(snapshot: object, action: str) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def test_structured_report_and_evidence_chain_are_persisted() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    first_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))
    duplicate_resume = runtime.resume(run_id, _approval_payload(started.snapshot, "approve_generation"))

    assert started.status == "waiting"
    assert first_resume.status == "completed"
    assert duplicate_resume.status == "completed"
    assert first_resume.snapshot.values["current_stage"] == "report_rendered"  # type: ignore[index]
    assert first_resume.snapshot.values["current_node"] == "complete_run"  # type: ignore[index]
    assert first_resume.snapshot.values["metrics_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["evidence_set_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["rendered_report_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["report_version_ref"] == duplicate_resume.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert first_resume.snapshot.values["rendered_report_ref"] == duplicate_resume.snapshot.values["rendered_report_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        metric_row = session.scalar(select(MetricSnapshot).where(MetricSnapshot.run_id == run_id))
        evidence_sets = session.scalars(select(EvidenceSet).where(EvidenceSet.run_id == run_id)).all()
        evidence_items = session.scalars(
            select(EvidenceItem)
            .join(EvidenceSet, EvidenceItem.evidence_set_id == EvidenceSet.id)
            .where(EvidenceSet.run_id == run_id)
        ).all()
        report_versions = session.scalars(select(ReportVersion).where(ReportVersion.run_id == run_id)).all()
        report_claims = session.scalars(
            select(ReportClaim).join(ReportVersion).where(ReportVersion.run_id == run_id)
        ).all()
        report_evidence = session.scalars(
            select(ReportEvidence)
            .join(ReportClaim)
            .join(ReportVersion)
            .where(ReportVersion.run_id == run_id)
        ).all()
        tool_executions = session.scalars(
            select(ToolExecution).where(ToolExecution.run_id == run_id)
        ).all()

        assert run_row is not None
        assert run_row.status == "completed"
        assert run_row.current_stage == "report_rendered"
        assert metric_row is not None
        assert len(evidence_sets) == 1
        assert len(evidence_items) == 4
        assert len(report_versions) == 1
        assert len(report_claims) == 4
        assert len(report_evidence) == 10
        assert len(tool_executions) == 9

        report_version = report_versions[0]
        assert report_version.status == "verified"
        assert report_version.rendered_content is not None
        assert report_version.data_quality_status == "complete"
        assert report_version.structured_hash == report_version.structured_report["structured_hash"]
        assert report_version.structured_report["metrics"] == extract_metric_values(metric_row.metrics)
        assert report_version.structured_report["evidence_set_ref"] == evidence_sets[0].id
        assert report_version.structured_report["metric_snapshot_ref"] == metric_row.id
        assert report_version.rendered_content
        assert report_version.content_hash != report_version.structured_hash
