from sqlalchemy import create_engine, inspect

from app.db.models import Base


def test_t8_tables_and_unique_idempotency_constraint_exist() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "admin_sessions",
        "admin_users",
        "async_jobs",
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
        "metric_snapshots",
        "model_configs",
        "normalized_entities",
        "normalized_snapshots",
        "audit_logs",
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
        "llm_executions",
        "node_executions",
        "schedule_configs",
        "side_effect_attempts",
        "side_effect_operations",
        "source_data_batches",
        "tool_executions",
        "validation_results",
    }
    assert any(
        constraint["name"] == "uq_report_runs_project_period"
        for constraint in inspector.get_unique_constraints("report_runs")
    )
    assert any(
        constraint["name"] == "uq_report_runs_thread_id"
        for constraint in inspector.get_unique_constraints("report_runs")
    )
    assert any(
        constraint["name"] == "uq_schedule_configs_project_id"
        for constraint in inspector.get_unique_constraints("schedule_configs")
    )
    assert any(
        constraint["name"] == "uq_human_approvals_revision"
        for constraint in inspector.get_unique_constraints("human_approvals")
    )
    assert any(
        constraint["name"] == "uq_human_approvals_challenge_id"
        for constraint in inspector.get_unique_constraints("human_approvals")
    )
    assert any(
        constraint["name"] == "uq_callback_events_provider_event_id"
        for constraint in inspector.get_unique_constraints("callback_events")
    )
    assert any(
        constraint["name"] == "uq_source_data_batches_identity"
        for constraint in inspector.get_unique_constraints("source_data_batches")
    )
    assert any(
        constraint["name"] == "uq_normalized_snapshots"
        for constraint in inspector.get_unique_constraints("normalized_snapshots")
    )
    assert any(
        constraint["name"] == "uq_normalized_entities_identity"
        for constraint in inspector.get_unique_constraints("normalized_entities")
    )
    assert any(
        constraint["name"] == "uq_validation_results"
        for constraint in inspector.get_unique_constraints("validation_results")
    )
    assert any(
        constraint["name"] == "uq_metric_snapshots"
        for constraint in inspector.get_unique_constraints("metric_snapshots")
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
    assert any(
        constraint["name"] == "uq_tool_executions_attempt"
        for constraint in inspector.get_unique_constraints("tool_executions")
    )
    assert any(
        index["column_names"] == ["run_id", "started_at"]
        for index in inspector.get_indexes("tool_executions")
    )
    assert any(
        index["column_names"] == ["tool_name", "status", "started_at"]
        for index in inspector.get_indexes("tool_executions")
    )
