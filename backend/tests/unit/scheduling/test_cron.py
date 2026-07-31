from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduler.cron import preview_next_fire_times


def test_weekly_schedule_preview_respects_timezone_and_week_boundaries() -> None:
    now = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    next_fire_times = preview_next_fire_times(
        cron_expression="0 9 * * 1",
        timezone="Asia/Shanghai",
        now=now,
        count=3,
    )

    assert next_fire_times == [
        datetime(2026, 8, 3, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        datetime(2026, 8, 10, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        datetime(2026, 8, 17, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    ]


def test_weekly_schedule_preview_skips_nonexistent_dst_wall_time() -> None:
    now = datetime(2026, 3, 7, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

    next_fire_times = preview_next_fire_times(
        cron_expression="30 2 * * 0",
        timezone="America/Los_Angeles",
        now=now,
        count=2,
    )

    assert next_fire_times == [
        datetime(2026, 3, 15, 2, 30, tzinfo=ZoneInfo("America/Los_Angeles")),
        datetime(2026, 3, 22, 2, 30, tzinfo=ZoneInfo("America/Los_Angeles")),
    ]
