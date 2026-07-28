from sqlalchemy import create_engine, inspect

from app.db.models import Base


def test_t8_tables_and_unique_idempotency_constraint_exist() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "human_approvals",
        "projects",
        "project_repositories",
        "feishu_resources",
        "report_runs",
        "run_status_history",
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
