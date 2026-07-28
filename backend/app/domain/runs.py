from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReportRun


class RunCreationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self, project_id: str, period_key: str, period_start: date, period_end: date
    ) -> ReportRun:
        existing = self.session.scalar(
            select(ReportRun).where(
                ReportRun.project_id == project_id,
                ReportRun.period_key == period_key,
            )
        )
        if existing is not None:
            return existing
        run = ReportRun(
            project_id=project_id,
            period_key=period_key,
            period_start=period_start,
            period_end=period_end,
            status="created",
        )
        self.session.add(run)
        self.session.flush()
        return run
