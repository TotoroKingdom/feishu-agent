from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Project
from app.domain.runs import RunCreationService


def test_run_creation_is_idempotent_and_persists_initial_state() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Demo", timezone="Asia/Shanghai")
        session.add(project)
        session.flush()
        service = RunCreationService(session)
        first = service.create_run(project.id, "period-001", date(2026, 7, 20), date(2026, 7, 27))
        second = service.create_run(project.id, "period-001", date(2026, 7, 20), date(2026, 7, 27))
        session.commit()

        assert first.id == second.id
        assert first.status == "created"
        assert first.period_key == "period-001"
