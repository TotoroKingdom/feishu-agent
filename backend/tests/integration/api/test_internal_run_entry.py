from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.models import Base, Project
from app.main import create_app


def make_app(profile: str = "local-demo") -> tuple[TestClient, str]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.commit()
        project_id = project.id
    factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    if profile == "production":
        settings = Settings(
            _env_file=None,
            app_profile="production",
            feishu_provider="real",
            github_provider="real",
            llm_provider="real",
            app_encryption_key="A" * 43,
        )
    else:
        settings = Settings(_env_file=None, app_profile=profile)
    return TestClient(create_app(settings=settings, session_factory=factory)), project_id


def test_local_demo_internal_entry_creates_idempotent_run() -> None:
    client, project_id = make_app()
    payload = {
        "project_id": project_id,
        "period_key": "2026-W30",
        "period_start": "2026-07-20",
        "period_end": "2026-07-27",
    }

    first = client.post("/internal/v1/runs", json=payload)
    second = client.post("/internal/v1/runs", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["run_id"] == second.json()["run_id"]
    assert first.json()["status"] == "created"


def test_production_disables_internal_entry() -> None:
    client, project_id = make_app("production")

    response = client.post(
        "/internal/v1/runs",
        json={
            "project_id": project_id,
            "period_key": "2026-W30",
            "period_start": date(2026, 7, 20).isoformat(),
            "period_end": date(2026, 7, 27).isoformat(),
        },
    )

    assert response.status_code == 404
