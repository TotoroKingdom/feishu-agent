from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AuditLog,
    Base,
    CallbackEvent,
    EncryptedCredential,
    LlmExecution,
    OnboardingSession,
    NodeExecution,
    NormalizedEntity,
    NormalizedSnapshot,
    OutboxMessage,
    Project,
    PublishPlan,
    ReportRun,
    ReportVersion,
    SideEffectOperation,
    SourceDataBatch,
    ToolExecution,
    new_id,
)
from app.domain.runs import RunCreationService
from app.runtime.leases import DataLifecycleService


def _make_factory() -> tuple[sessionmaker[Session], str, str, str]:
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
            datetime(2026, 7, 20, tzinfo=UTC).date(),
            datetime(2026, 7, 27, tzinfo=UTC).date(),
        )
        run.status = "completed"
        run.current_stage = "succeeded"
        run.current_node = "complete_run"
        waiting_run = RunCreationService(session).create_run(
            project.id,
            "2026-W31",
            datetime(2026, 7, 27, tzinfo=UTC).date(),
            datetime(2026, 8, 3, tzinfo=UTC).date(),
        )
        waiting_run.status = "waiting"
        waiting_run.current_stage = "waiting_publish_approval"
        waiting_run.current_node = "wait_publish_confirmation"
        session.commit()
        return factory, project.id, run.id, waiting_run.id


def _seed_cleanup_rows(
    factory: sessionmaker[Session], project_id: str, run_id: str, waiting_run_id: str
) -> None:
    old = datetime(2026, 1, 1, tzinfo=UTC)
    fresh = datetime(2026, 7, 31, tzinfo=UTC)
    with factory() as session:
        session.add(
            SourceDataBatch(
                id="batch-old",
                run_id=run_id,
                source_type="feishu",
                source_resource_id="resource-1",
                entity_type="record",
                page_no=1,
                cursor="cursor-1",
                period_start=old,
                period_end=old + timedelta(days=7),
                payload={"rows": [{"id": "row-1", "title": "old"}]},
                payload_hash="payload-hash-1",
                record_count=1,
                schema_version="v1",
                fetch_status="complete",
                fetched_at=old,
                expires_at=old + timedelta(days=30),
            )
        )
        snapshot = NormalizedSnapshot(
            id="snapshot-old",
            run_id=run_id,
            source_batch_set_hash="source-batch-hash",
            mapping_revision="1",
            normalizer_version="minimal.v1",
            entity_count=1,
            status="complete",
            content_hash="content-hash",
            created_at=old,
        )
        session.add(snapshot)
        session.add(
            NormalizedEntity(
                id="entity-old",
                run_id=run_id,
                normalized_snapshot_id=snapshot.id,
                source_type="feishu",
                entity_type="record",
                source_resource_id="resource-1",
                external_id="row-1",
                repository_id=None,
                url="https://example.test/item/1",
                title="Old row",
                state="active",
                author_external_id="user-1",
                assignee_external_ids=["user-2"],
                labels=[{"name": "old"}],
                milestone_external_id=None,
                created_at_external=old,
                updated_at_external=old,
                closed_at_external=None,
                occurred_at=old,
                raw_batch_id="batch-old",
                raw_summary="old summary",
                attributes={"payload": "large"},
                content_hash="entity-hash",
                fetched_at=old,
            )
        )
        session.add(
            NodeExecution(
                id="node-old",
                run_id=run_id,
                node_name="collect_feishu_data",
                node_attempt=1,
                checkpoint_before=None,
                checkpoint_after=None,
                status="succeeded",
                input_summary={"rows": 1},
                output_summary={"rows": 1},
                error_class=None,
                error_summary=None,
                started_at=old,
                ended_at=old,
                duration_ms=10,
            )
        )
        session.add(
            LlmExecution(
                id="llm-old",
                run_id=run_id,
                node_execution_id="node-old",
                provider="fake",
                model="fake-model",
                prompt_type="report",
                prompt_version_id=None,
                input_hash="input-hash",
                output_ref="output-ref",
                status="success",
                schema_valid=True,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                duration_ms=5,
                error_class=None,
                created_at=old,
            )
        )
        session.add(
            ToolExecution(
                id="tool-old",
                run_id=run_id,
                node_execution_id="node-old",
                tool_name="reports.calculate_metrics",
                tool_version="v1",
                attempt=1,
                idempotency_key="tool-old-key",
                request_summary={"run": run_id},
                result_summary={"ok": True},
                data_ref="metric-ref",
                provider_request_id="provider-request",
                status="success",
                error_class=None,
                error_code=None,
                retryable=False,
                started_at=old,
                ended_at=old,
                duration_ms=5,
            )
        )
        session.add(
            OutboxMessage(
                id="outbox-old",
                topic="report.completed",
                aggregate_type="report_run",
                aggregate_id=run_id,
                payload={"run_id": run_id},
                dedupe_key="outbox-old-key",
                status="published",
                attempt_count=1,
                available_at=old,
                created_at=old,
                claimed_at=None,
                claimed_by=None,
                lease_expires_at=None,
                provider_request_id=None,
                external_message_id="msg-1",
                published_at=old,
                dead_lettered_at=None,
                last_error_class=None,
                last_error_summary=None,
            )
        )
        session.add(
            CallbackEvent(
                id=1,
                provider="feishu",
                external_event_id="evt-old",
                event_type="card.action",
                payload_hash="payload-hash",
                actor_id="ou_123",
                run_id=run_id,
                status="processed",
                attempt_count=1,
                received_at=old,
                claimed_at=None,
                claimed_by=None,
                lease_expires_at=None,
                next_attempt_at=None,
                processed_at=old,
                dead_lettered_at=None,
                last_error_class=None,
                last_error_summary=None,
            )
        )
        session.add(
            EncryptedCredential(
                id="credential-old",
                project_id=project_id,
                credential_type="github_pat",
                label="github-pat",
                ciphertext=b"ciphertext",
                nonce=b"nonce",
                key_version="v1",
                fingerprint="f" * 64,
                status="revoked",
                expires_at=None,
                last_validated_at=None,
                created_by="admin",
                updated_by="admin",
                created_at=old,
                updated_at=old,
            )
        )
        onboarding_session = OnboardingSession(
            id="onboarding-session-old",
            feishu_actor_id="ou_123",
            status="cancelled",
            current_step="completed",
            draft_config={"credentials": {"github_pat_ref": "credential-session"}},
            credential_ref="credential-session",
            card_message_id=None,
            revision=3,
            expires_at=old + timedelta(days=30),
            created_at=old,
            updated_at=old,
        )
        session.add(onboarding_session)
        session.commit()

        session.add(
            EncryptedCredential(
                id="credential-session",
                project_id=project_id,
                credential_type="github_pat",
                label="github-pat-session",
                ciphertext=b"ciphertext-2",
                nonce=b"nonce-2",
                key_version="v1",
                fingerprint="e" * 64,
                status="revoked",
                expires_at=None,
                last_validated_at=None,
                created_by="admin",
                updated_by="admin",
                created_at=old,
                updated_at=old,
            )
        )
        waiting_run = session.get(ReportRun, waiting_run_id)
        assert waiting_run is not None
        waiting_run.status = "waiting"
        waiting_run.graph_version = "weekly_report.v1"
        waiting_run.state_schema_version = 1
        waiting_run.scope_revision = 1
        waiting_run.current_stage = "waiting_publish_approval"
        waiting_run.current_node = "wait_publish_confirmation"
        waiting_report_version = ReportVersion(
            run_id=waiting_run_id,
            version=1,
            status="verified",
            structured_report={"summary": "waiting"},
            structured_hash="structured-hash-waiting",
            rendered_content="rendered waiting report",
            content_hash="rendered-hash-waiting",
            data_snapshot_hash="snapshot-hash-waiting",
            prompt_version_ids=["prompt-v1"],
            model_info={"provider": "fake"},
            confidence=0.95,
            data_quality_status="complete",
            verified_at=fresh,
        )
        session.add(waiting_report_version)
        session.flush()
        session.add(
            PublishPlan(
                id="publish-plan-waiting",
                run_id=waiting_run_id,
                report_version_id=waiting_report_version.id,
                version=1,
                status="approved",
                canonical_plan={"operations": []},
                plan_hash="publish-plan-hash-waiting",
                content_version=1,
            )
        )
        session.add(
            SideEffectOperation(
                id="op-unknown",
                publish_plan_id="publish-plan-waiting",
                run_id=waiting_run_id,
                sequence=1,
                operation_type="create_feishu_document",
                target_ref="target",
                target_hash="target",
                payload_ref="payload",
                payload_hash="payload",
                idempotency_key="op-unknown-key",
                status="unknown",
                attempt_count=1,
                external_resource_id="ext-1",
                external_url=None,
                provider_request_id=None,
                verification_status="inconclusive",
                last_error_class="timeout",
                last_error_summary="unknown",
                lease_owner="worker-a",
                lease_expires_at=old + timedelta(seconds=30),
                heartbeat_at=old,
                started_at=old,
                completed_at=None,
                updated_at=old,
                version=1,
            )
        )
        session.commit()


def test_data_lifecycle_prunes_payloads_and_skips_waiting_or_unknown_runs() -> None:
    factory, project_id, eligible_run_id, waiting_run_id = _make_factory()
    _seed_cleanup_rows(factory, project_id, eligible_run_id, waiting_run_id)
    service = DataLifecycleService(factory)
    now = datetime(2026, 7, 31, tzinfo=UTC)

    dry_run = service.cleanup(now=now, dry_run=True)
    assert dry_run.dry_run is True
    assert waiting_run_id in dry_run.skipped_run_ids
    assert dry_run.pruned_payload_counts["source_data_batches"] == 1
    assert dry_run.deleted_row_counts["node_executions"] == 1
    assert dry_run.deleted_row_counts["tool_executions"] == 1
    assert dry_run.deleted_row_counts["llm_executions"] == 1
    assert dry_run.deleted_row_counts["onboarding_sessions"] == 1

    executed = service.cleanup(now=now, dry_run=False)
    assert executed.dry_run is False
    assert executed.skipped_run_ids == [waiting_run_id]
    assert executed.pruned_payload_counts["source_data_batches"] == 1
    assert executed.pruned_payload_counts["normalized_entities"] == 1
    assert executed.deleted_row_counts["node_executions"] == 1
    assert executed.deleted_row_counts["tool_executions"] == 1
    assert executed.deleted_row_counts["llm_executions"] == 1
    assert executed.deleted_row_counts["async_jobs"] == 0
    assert executed.deleted_row_counts["outbox_messages"] == 1
    assert executed.deleted_row_counts["callback_events"] == 1
    assert executed.deleted_row_counts["onboarding_sessions"] == 1
    assert executed.deleted_row_counts["encrypted_credentials"] == 2
    assert executed.audited is True

    with factory() as session:
        batch = session.get(SourceDataBatch, "batch-old")
        assert batch is not None
        assert batch.payload == {}

        entity = session.get(NormalizedEntity, "entity-old")
        assert entity is not None
        assert entity.attributes == {}
        assert entity.raw_summary is None

        assert session.get(NodeExecution, "node-old") is None
        assert session.get(ToolExecution, "tool-old") is None
        assert session.get(LlmExecution, "llm-old") is None
        assert session.get(OutboxMessage, "outbox-old") is None
        assert session.get(CallbackEvent, 1) is None
        assert session.get(EncryptedCredential, "credential-session") is None
        assert session.get(EncryptedCredential, "credential-old") is None
        assert session.get(OnboardingSession, "onboarding-session-old") is None

        waiting_run = session.get(ReportRun, waiting_run_id)
        assert waiting_run is not None
        stale_operation = session.get(SideEffectOperation, "op-unknown")
        assert stale_operation is not None
        audit_rows = session.scalars(select(AuditLog)).all()
        assert len(audit_rows) == 1
