from sqlalchemy import create_engine, inspect

from app.db.models import Base


def test_report_tables_and_constraints_exist() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "evidence_items",
        "evidence_sets",
        "feishu_resources",
        "human_approvals",
        "metric_snapshots",
        "normalized_entities",
        "normalized_snapshots",
        "publish_plans",
        "projects",
        "project_repositories",
        "report_claims",
        "report_evidence",
        "report_runs",
        "report_versions",
        "run_status_history",
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
