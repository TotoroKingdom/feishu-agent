from __future__ import annotations

from datetime import UTC, date, datetime

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.runtime import WorkflowRuntime, WorkflowWorker
from app.db.models import Base, Project, ReportVersion
from app.domain.runs import RunCreationService
from app.providers.fake import FakeEffectProvider, FakeScenario
from app.publishing.service import PublishingService


class PartialFailureVerifierProvider(FakeEffectProvider):
    def __init__(self) -> None:
        super().__init__(FakeScenario.HAPPY)

    def create_feishu_document(self, report_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-document-{report_id}",
            "url": f"https://fake.feishu.local/doc/{report_id}",
            "provider_request_id": f"fake-request-document-{report_id}",
        }

    def send_group_summary(self, run_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-message-{run_id}",
            "url": f"https://fake.feishu.local/message/{run_id}",
            "provider_request_id": f"fake-request-message-{run_id}",
        }

    def upsert_bitable_archive(self, run_id: str) -> dict[str, str]:
        return {
            "status": "success",
            "external_id": f"fake-archive-{run_id}",
            "url": f"https://fake.feishu.local/archive/{run_id}",
            "provider_request_id": f"fake-request-archive-{run_id}",
        }

    def query_feishu_document(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/doc/{run_id}",
        }

    def query_group_summary(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "confirmed",
            "external_id": external_id,
            "run_id": run_id,
            "url": f"https://fake.feishu.local/message/{run_id}",
        }

    def query_bitable_archive(self, external_id: str, run_id: str) -> dict[str, str]:
        return {
            "status": "not_found",
            "error_class": "resource_not_found",
            "error_summary": "archive is missing after publish",
            "external_id": external_id,
            "run_id": run_id,
        }


def _make_runtime() -> tuple[
    WorkflowRuntime,
    WorkflowWorker,
    sessionmaker[Session],
    MemorySaver,
    str,
]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        run = RunCreationService(session).create_run(
            project.id,
            "2026-W30",
            date(2026, 7, 20),
            date(2026, 7, 27),
        )
        report_version = ReportVersion(
            run_id=run.id,
            version=1,
            status="verified",
            structured_report={"summary": "ok"},
            structured_hash="structured-hash",
            rendered_content="rendered report",
            content_hash="rendered-hash",
            data_snapshot_hash="snapshot-hash",
            prompt_version_ids=["prompt-v1"],
            model_info={"provider": "fake"},
            confidence=0.95,
            data_quality_status="complete",
            verified_at=datetime.now(UTC),
        )
        session.add(report_version)
        session.commit()
        run_id = run.id

    publishing = PublishingService(factory, effect_provider=PartialFailureVerifierProvider())
    saver = MemorySaver()
    runtime = WorkflowRuntime(factory, saver, publishing_service=publishing)
    worker = WorkflowWorker(factory, saver)
    return runtime, worker, factory, saver, run_id


def _approve_generation(snapshot: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    scope = values["scope"]
    return {
        "action": "approve_generation",
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": scope["scope_hash"],
        "actor_id": "local-demo",
    }


def _approve_publish(snapshot: object) -> dict[str, object]:
    values = snapshot.values  # type: ignore[attr-defined]
    approval = values["approval"]
    publish = values["publish"]
    return {
        "action": "approve_publish",
        "challenge_id": approval["challenge_id"],
        "approval_revision": approval["approval_revision"],
        "presented_hash": publish["plan_hash"],
        "actor_id": "local-demo",
    }


def test_restart_recovery_finds_partial_failed_publish_runs() -> None:
    runtime, _, factory, saver, run_id = _make_runtime()

    first = runtime.start(run_id)
    waiting_publish = runtime.resume(run_id, _approve_generation(first.snapshot))
    finished = runtime.resume(run_id, _approve_publish(waiting_publish.snapshot))

    restarted_worker = WorkflowWorker(factory, saver)

    assert finished.status == "partial_failed"
    assert restarted_worker.recover_partial_failed_runs() == [run_id]
