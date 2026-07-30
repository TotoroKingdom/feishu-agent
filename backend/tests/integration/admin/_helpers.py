from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.models import Base, Project
from app.main import create_app


def make_admin_client() -> tuple[TestClient, sessionmaker[Session], str]:
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
        session.commit()
        project_id = project.id
    client = TestClient(
        create_app(
            settings=Settings(_env_file=None, app_profile="local-demo"),
            session_factory=factory,
        )
    )
    return client, factory, project_id
