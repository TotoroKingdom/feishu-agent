from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.state import STATE_SCHEMA_VERSION, WORKFLOW_GRAPH_VERSION, thread_id_for_run
from app.db.models import ReportRun, new_id


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
            if existing.thread_id is None:
                existing.thread_id = thread_id_for_run(existing.id)
            if not existing.graph_version:
                existing.graph_version = WORKFLOW_GRAPH_VERSION
            if not existing.state_schema_version:
                existing.state_schema_version = STATE_SCHEMA_VERSION
            if not existing.scope_revision:
                existing.scope_revision = 1
            if not existing.current_stage:
                existing.current_stage = "created"
            return existing
        run_id = new_id()
        run = ReportRun(
            id=run_id,
            project_id=project_id,
            thread_id=thread_id_for_run(run_id),
            period_key=period_key,
            period_start=period_start,
            period_end=period_end,
            status="created",
            graph_version=WORKFLOW_GRAPH_VERSION,
            state_schema_version=STATE_SCHEMA_VERSION,
            scope_revision=1,
            current_stage="created",
            current_node=None,
        )
        self.session.add(run)
        self.session.flush()
        return run
