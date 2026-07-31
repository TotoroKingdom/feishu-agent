from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ScheduleConfig, new_id

from .cron import preview_next_fire_times

SessionFactory = Callable[[], Session]

DEFAULT_WEEKLY_CRON = "0 9 * * 1"


class RevisionConflictError(ValueError):
    pass


class ScheduleConfigUpdateRequest(BaseModel):
    cron_expression: str = Field(min_length=1, max_length=128)
    timezone: str = Field(min_length=1, max_length=64)
    enabled: bool
    misfire_policy: Literal["skip", "fire_once"]
    revision: int


class ScheduleConfigPayload(BaseModel):
    id: str
    project_id: str
    cron_expression: str
    timezone: str
    enabled: bool
    misfire_policy: Literal["skip", "fire_once"]
    next_fire_at: datetime | None
    last_fire_at: datetime | None
    revision: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    next_fire_times: list[datetime] = Field(default_factory=list)


@dataclass(slots=True)
class ScheduleService:
    session_factory: SessionFactory
    settings: Settings

    def get_schedule(self) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            row = self._load_or_create_schedule(session, project)
            session.flush()
            session.commit()
            return self._payload(row, project.timezone).model_dump(mode="json")

    def update_schedule(self, payload: ScheduleConfigUpdateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            row = self._load_or_create_schedule(session, project)
            if payload.revision != row.revision:
                raise RevisionConflictError("schedule revision conflict")
            preview = preview_next_fire_times(
                payload.cron_expression,
                payload.timezone,
                datetime.now(UTC),
                count=3,
            )
            row.cron_expression = payload.cron_expression
            row.timezone = payload.timezone
            row.enabled = payload.enabled
            row.misfire_policy = payload.misfire_policy
            row.next_fire_at = preview[0].astimezone(UTC)
            row.revision += 1
            session.flush()
            session.commit()
            return self._payload(row, project.timezone).model_dump(mode="json")

    def validate_schedule(
        self, payload: ScheduleConfigUpdateRequest, now: datetime | None = None
    ) -> dict[str, object]:
        preview = preview_next_fire_times(
            payload.cron_expression,
            payload.timezone,
            now or datetime.now(UTC),
            count=3,
        )
        return ScheduleConfigPayload(
            id="",
            project_id="",
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            enabled=payload.enabled,
            misfire_policy=payload.misfire_policy,
            next_fire_at=preview[0].astimezone(UTC),
            last_fire_at=None,
            revision=payload.revision,
            next_fire_times=preview,
        ).model_dump(mode="json")

    def _load_or_create_project(self, session: Session) -> Project:
        project = session.scalar(select(Project).order_by(Project.created_at))
        if project is None:
            project = Project(name="Default Project", timezone="UTC")
            session.add(project)
            session.flush()
        return project

    def _load_or_create_schedule(self, session: Session, project: Project) -> ScheduleConfig:
        row = session.scalar(select(ScheduleConfig).where(ScheduleConfig.project_id == project.id))
        if row is None:
            now = datetime.now(UTC)
            preview = preview_next_fire_times(DEFAULT_WEEKLY_CRON, project.timezone, now, count=3)
            row = ScheduleConfig(
                id=new_id(),
                project_id=project.id,
                cron_expression=DEFAULT_WEEKLY_CRON,
                timezone=project.timezone,
                enabled=False,
                misfire_policy="fire_once",
                next_fire_at=preview[0].astimezone(UTC),
                last_fire_at=None,
                revision=1,
            )
            session.add(row)
            session.flush()
        return row

    def _payload(self, row: ScheduleConfig, fallback_timezone: str) -> ScheduleConfigPayload:
        timezone = row.timezone or fallback_timezone
        next_fire_times = preview_next_fire_times(
            row.cron_expression,
            timezone,
            datetime.now(UTC),
            count=3,
        )
        return ScheduleConfigPayload(
            id=row.id,
            project_id=row.project_id,
            cron_expression=row.cron_expression,
            timezone=timezone,
            enabled=row.enabled,
            misfire_policy=cast(Literal["skip", "fire_once"], row.misfire_policy),
            next_fire_at=_as_utc(row.next_fire_at),
            last_fire_at=_as_utc(row.last_fire_at),
            revision=row.revision,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
            next_fire_times=next_fire_times,
        )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
