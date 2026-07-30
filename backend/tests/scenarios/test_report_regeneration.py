from __future__ import annotations

from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.agent.runtime import WorkflowRuntime
from app.db.models import (
    Base,
    EvidenceSet,
    HumanApproval,
    MetricSnapshot,
    Project,
    PublishPlan,
    ReportRun,
    ReportVersion,
)
from app.domain.runs import RunCreationService


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


def _generation_payload(snapshot: object, action: str) -> dict[str, object]:
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


def _publish_payload(
    snapshot: object,
    action: str,
    *,
    supplement: dict[str, object] | None = None,
) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    payload: dict[str, object] = {
        "action": action,
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }
    if supplement is not None:
        payload["supplement"] = supplement
    return payload


def test_regenerate_report_reuses_inputs_but_creates_new_versions() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    publish_waiting = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))
    regenerated = runtime.resume(run_id, _publish_payload(publish_waiting.snapshot, "regenerate_report"))

    assert started.status == "waiting"
    assert publish_waiting.status == "waiting"
    assert regenerated.status == "waiting"
    assert regenerated.snapshot.values["current_stage"] == "waiting_publish_approval"  # type: ignore[index]
    assert regenerated.snapshot.values["current_node"] == "wait_publish_confirmation"  # type: ignore[index]
    assert regenerated.snapshot.values["approval"]["approval_revision"] == 2  # type: ignore[index]
    assert regenerated.snapshot.values["metrics_ref"] == publish_waiting.snapshot.values["metrics_ref"]  # type: ignore[index]
    assert regenerated.snapshot.values["evidence_set_ref"] == publish_waiting.snapshot.values["evidence_set_ref"]  # type: ignore[index]
    assert regenerated.snapshot.values["report_version_ref"] != publish_waiting.snapshot.values["report_version_ref"]  # type: ignore[index]
    assert regenerated.snapshot.values["publish_plan_ref"] != publish_waiting.snapshot.values["publish_plan_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        metric_rows = session.scalars(select(MetricSnapshot).where(MetricSnapshot.run_id == run_id)).all()
        evidence_sets = session.scalars(select(EvidenceSet).where(EvidenceSet.run_id == run_id)).all()
        report_versions = session.scalars(
            select(ReportVersion).where(ReportVersion.run_id == run_id).order_by(ReportVersion.version)
        ).all()
        publish_plans = session.scalars(
            select(PublishPlan).where(PublishPlan.run_id == run_id).order_by(PublishPlan.version)
        ).all()
        publish_approvals = session.scalars(
            select(HumanApproval)
            .where(HumanApproval.run_id == run_id, HumanApproval.approval_type == "publish")
            .order_by(HumanApproval.revision)
        ).all()

        assert run_row is not None
        assert run_row.status == "waiting"
        assert len(metric_rows) == 1
        assert len(evidence_sets) == 1
        assert len(report_versions) == 2
        assert len(publish_plans) == 2
        assert len(publish_approvals) == 2
        assert [approval.status for approval in publish_approvals] == ["superseded", "pending"]
        assert report_versions[0].structured_hash == report_versions[1].structured_hash
        assert report_versions[0].content_hash != report_versions[1].content_hash
        assert publish_plans[0].content_version == 1
        assert publish_plans[1].content_version == 2
        assert publish_plans[0].plan_hash != publish_plans[1].plan_hash


def test_update_supplement_scope_change_returns_to_generation_hitl() -> None:
    runtime, run_id, factory = make_runtime()

    started = runtime.start(run_id)
    publish_waiting = runtime.resume(run_id, _generation_payload(started.snapshot, "approve_generation"))
    scoped = runtime.resume(
        run_id,
        _publish_payload(
            publish_waiting.snapshot,
            "update_supplement",
            supplement={
                "scope_override": {
                    "selected_repository_ids": [
                        "github-repository-example",
                        "github-repository-extra",
                    ]
                }
            },
        ),
    )

    assert scoped.status == "waiting"
    assert scoped.snapshot.values["current_stage"] == "waiting_confirmation"  # type: ignore[index]
    assert scoped.snapshot.values["current_node"] == "wait_generation_confirmation"  # type: ignore[index]
    assert scoped.snapshot.values["scope_revision"] == 2  # type: ignore[index]
    assert scoped.snapshot.values["approval"]["approval_type"] == "generation"  # type: ignore[index]
    assert scoped.snapshot.values["approval"]["approval_revision"] == 2  # type: ignore[index]
    assert scoped.snapshot.values["publish_plan_ref"] is None  # type: ignore[index]
    assert scoped.snapshot.values["metrics_ref"] == publish_waiting.snapshot.values["metrics_ref"]  # type: ignore[index]
    assert scoped.snapshot.values["evidence_set_ref"] == publish_waiting.snapshot.values["evidence_set_ref"]  # type: ignore[index]

    with factory() as session:
        run_row = session.scalar(select(ReportRun).where(ReportRun.id == run_id))
        publish_plan = session.scalar(select(PublishPlan).where(PublishPlan.run_id == run_id))
        generation_approvals = session.scalars(
            select(HumanApproval)
            .where(HumanApproval.run_id == run_id, HumanApproval.approval_type == "generation")
            .order_by(HumanApproval.revision)
        ).all()
        publish_approvals = session.scalars(
            select(HumanApproval)
            .where(HumanApproval.run_id == run_id, HumanApproval.approval_type == "publish")
            .order_by(HumanApproval.revision)
        ).all()

        assert run_row is not None
        assert run_row.status == "waiting"
        assert run_row.scope_revision == 2
        assert publish_plan is not None
        assert publish_plan.status == "invalidated"
        assert len(generation_approvals) == 2
        assert [approval.status for approval in generation_approvals] == ["approved", "pending"]
        assert len(publish_approvals) == 1
        assert publish_approvals[0].status == "superseded"
