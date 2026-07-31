from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ScheduleConfig
from app.domain.runs import RunCreationService

from .cron import build_weekly_period, preview_next_fire_times

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class SchedulerTickResult:
    processed_schedule_ids: list[str] = field(default_factory=list)
    created_run_ids: list[str] = field(default_factory=list)
    skipped_schedule_ids: list[str] = field(default_factory=list)
    ticked_at: datetime | None = None


@dataclass(slots=True)
class SchedulerWorker:
    session_factory: SessionFactory
    settings: Settings

    def tick(self, now: datetime | None = None) -> SchedulerTickResult:
        current = now or datetime.now(UTC)
        result = SchedulerTickResult(ticked_at=current)
        with self.session_factory() as session:
            schedules = session.scalars(
                select(ScheduleConfig)
                .where(ScheduleConfig.enabled.is_(True))
                .order_by(ScheduleConfig.next_fire_at, ScheduleConfig.id)
            ).all()
            for schedule in schedules:
                due_at = _as_utc(schedule.next_fire_at)
                if due_at is None or due_at > current:
                    continue
                result.processed_schedule_ids.append(schedule.id)
                next_fire_times = preview_next_fire_times(
                    schedule.cron_expression,
                    schedule.timezone,
                    current,
                    count=1,
                )
                schedule.next_fire_at = next_fire_times[0].astimezone(UTC)
                if schedule.misfire_policy == "skip":
                    result.skipped_schedule_ids.append(schedule.id)
                    continue

                period = build_weekly_period(due_at, schedule.timezone)
                run = RunCreationService(session).create_run(
                    schedule.project_id,
                    period.period_key,
                    period.period_start,
                    period.period_end,
                )
                schedule.last_fire_at = due_at
                result.created_run_ids.append(run.id)
            session.flush()
            session.commit()
        return result


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
