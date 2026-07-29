from sqlalchemy import create_engine, inspect

from app.db.models import Base


def test_t8_tables_and_unique_idempotency_constraint_exist() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "feishu_resources",
        "human_approvals",
        "normalized_entities",
        "normalized_snapshots",
        "projects",
        "project_repositories",
        "report_runs",
        "run_status_history",
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
        constraint["name"] == "uq_human_approvals_revision"
        for constraint in inspector.get_unique_constraints("human_approvals")
    )
    assert any(
        constraint["name"] == "uq_human_approvals_challenge_id"
        for constraint in inspector.get_unique_constraints("human_approvals")
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
        constraint["name"] == "uq_tool_executions_attempt"
        for constraint in inspector.get_unique_constraints("tool_executions")
    )
