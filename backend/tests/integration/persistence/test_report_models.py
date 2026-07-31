from sqlalchemy import create_engine, inspect

from app.db.models import Base


def test_report_tables_and_constraints_exist() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "admin_sessions",
        "admin_users",
        "async_jobs",
        "audit_logs",
        "callback_events",
        "diagnosis_records",
        "encrypted_credentials",
        "evidence_items",
        "evidence_sets",
        "feishu_field_mappings",
        "feishu_resources",
        "feishu_message_deliveries",
        "human_approvals",
        "login_audits",
        "llm_executions",
        "metric_snapshots",
        "model_configs",
        "normalized_entities",
        "normalized_snapshots",
        "node_executions",
        "onboarding_sessions",
        "outbox_messages",
        "project_repositories",
        "projects",
        "prompt_versions",
        "publish_plans",
        "report_artifacts",
        "report_claims",
        "report_evidence",
        "report_runs",
        "report_versions",
        "run_status_history",
        "schedule_configs",
        "side_effect_attempts",
        "side_effect_operations",
        "source_data_batches",
        "tool_executions",
        "validation_results",
    }
    assert any(
        constraint["name"] == "uq_metric_snapshots"
        for constraint in inspector.get_unique_constraints("metric_snapshots")
    )
    assert any(
        constraint["name"] == "uq_evidence_sets"
        for constraint in inspector.get_unique_constraints("evidence_sets")
    )
    assert any(
        constraint["name"] == "uq_evidence_items"
        for constraint in inspector.get_unique_constraints("evidence_items")
    )
    assert any(
        constraint["name"] == "uq_report_versions_version"
        for constraint in inspector.get_unique_constraints("report_versions")
    )
    assert any(
        constraint["name"] == "uq_report_versions_content_hash"
        for constraint in inspector.get_unique_constraints("report_versions")
    )
    assert any(
        constraint["name"] == "uq_callback_events_provider_event_id"
        for constraint in inspector.get_unique_constraints("callback_events")
    )
    assert any(
        constraint["name"] == "uq_report_claims"
        for constraint in inspector.get_unique_constraints("report_claims")
    )
    assert any(
        constraint["name"] == "uq_report_evidence"
        for constraint in inspector.get_unique_constraints("report_evidence")
    )
    assert any(
        constraint["name"] == "uq_publish_plans_version"
        for constraint in inspector.get_unique_constraints("publish_plans")
    )
    assert any(
        constraint["name"] == "uq_publish_plans_plan_hash"
        for constraint in inspector.get_unique_constraints("publish_plans")
    )
    assert any(
        constraint["name"] == "uq_side_effect_operations_sequence"
        for constraint in inspector.get_unique_constraints("side_effect_operations")
    )
    assert any(
        constraint["name"] == "uq_side_effect_operations_idempotency_key"
        for constraint in inspector.get_unique_constraints("side_effect_operations")
    )
    assert any(
        constraint["name"] == "uq_outbox_messages_dedupe_key"
        for constraint in inspector.get_unique_constraints("outbox_messages")
    )
    assert any(
        constraint["name"] == "uq_feishu_message_deliveries_idempotency_key"
        for constraint in inspector.get_unique_constraints("feishu_message_deliveries")
    )
    assert any(
        constraint["name"] == "uq_feishu_message_deliveries_run_purpose_revision_recipient"
        for constraint in inspector.get_unique_constraints("feishu_message_deliveries")
    )
    assert any(
        constraint["name"] == "uq_side_effect_attempts"
        for constraint in inspector.get_unique_constraints("side_effect_attempts")
    )
    assert any(
        constraint["name"] == "uq_report_artifacts_operation"
        for constraint in inspector.get_unique_constraints("report_artifacts")
    )
