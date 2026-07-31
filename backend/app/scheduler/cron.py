from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class WeeklyPeriod:
    period_key: str
    period_start: date
    period_end: date


@dataclass(frozen=True, slots=True)
class _CronSpec:
    minute: frozenset[int]
    hour: frozenset[int]
    month: frozenset[int]
    day_of_month: frozenset[int]
    day_of_week: frozenset[int]
    day_of_month_wildcard: bool
    day_of_week_wildcard: bool


def preview_next_fire_times(
    cron_expression: str,
    timezone: str,
    now: datetime,
    count: int = 3,
) -> list[datetime]:
    if count <= 0:
        return []
    spec = _parse_cron_expression(cron_expression)
    tz = _load_timezone(timezone)
    current = _coerce_datetime(now, tz)
    results: list[datetime] = []
    candidate_date = current.date()
    search_limit = candidate_date + timedelta(days=370 * 5)

    while len(results) < count and candidate_date <= search_limit:
        if _date_matches(spec, candidate_date):
            for hour in sorted(spec.hour):
                for minute in sorted(spec.minute):
                    candidate = datetime.combine(
                        candidate_date,
                        time(hour=hour, minute=minute),
                        tzinfo=tz,
                    )
                    if not _is_real_local_time(candidate):
                        continue
                    if candidate <= current:
                        continue
                    results.append(candidate)
                    if len(results) >= count:
                        break
                if len(results) >= count:
                    break
        candidate_date += timedelta(days=1)

    if len(results) < count:
        raise ValueError("could not resolve enough future fire times")
    return results


def build_weekly_period(fire_at: datetime, timezone: str) -> WeeklyPeriod:
    tz = _load_timezone(timezone)
    fire_local = _coerce_datetime(fire_at, tz)
    period_end_date = _start_of_week(fire_local.date())
    period_start_date = period_end_date - timedelta(days=7)
    iso_year, iso_week, _ = period_start_date.isocalendar()
    return WeeklyPeriod(
        period_key=f"{iso_year}-W{iso_week:02d}",
        period_start=period_start_date,
        period_end=period_end_date,
    )


def _parse_cron_expression(cron_expression: str) -> _CronSpec:
    fields = cron_expression.split()
    if len(fields) != 5:
        raise ValueError("cron_expression must contain 5 fields")

    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    day_of_month = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    day_of_week = _parse_field(fields[4], 0, 7, day_of_week=True)
    return _CronSpec(
        minute=frozenset(minute.values),
        hour=frozenset(hour.values),
        month=frozenset(month.values),
        day_of_month=frozenset(day_of_month.values),
        day_of_week=frozenset(day_of_week.values),
        day_of_month_wildcard=day_of_month.wildcard,
        day_of_week_wildcard=day_of_week.wildcard,
    )


@dataclass(frozen=True, slots=True)
class _ParsedField:
    values: frozenset[int]
    wildcard: bool


def _parse_field(
    field: str,
    minimum: int,
    maximum: int,
    *,
    day_of_week: bool = False,
) -> _ParsedField:
    parts = field.split(",")
    values: set[int] = set()
    wildcard = False
    for part in parts:
        if part == "*":
            wildcard = True
            values.update(range(minimum, maximum + 1))
            continue
        step_base, step = _parse_step(part)
        if step_base == "*":
            start = minimum
            end = maximum
        elif "-" in step_base:
            start_text, end_text = step_base.split("-", 1)
            start = _parse_int(start_text, minimum, maximum, day_of_week=day_of_week)
            end = _parse_int(end_text, minimum, maximum, day_of_week=day_of_week)
            if end < start:
                raise ValueError(f"invalid cron range: {part}")
        else:
            start = _parse_int(step_base, minimum, maximum, day_of_week=day_of_week)
            end = start
        if step <= 0:
            raise ValueError(f"invalid cron step: {part}")
        for value in range(start, end + 1, step):
            values.add(_normalize_day_of_week(value) if day_of_week else value)
    if not values:
        raise ValueError(f"invalid cron field: {field}")
    if day_of_week and 7 in values:
        values.remove(7)
        values.add(0)
    return _ParsedField(values=frozenset(values), wildcard=wildcard)


def _parse_step(part: str) -> tuple[str, int]:
    if "/" not in part:
        return part, 1
    base, step_text = part.split("/", 1)
    return base, int(step_text)


def _parse_int(
    value: str,
    minimum: int,
    maximum: int,
    *,
    day_of_week: bool = False,
) -> int:
    parsed = int(value)
    if day_of_week and parsed == 7:
        parsed = 0
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"cron value out of range: {value}")
    return parsed


def _normalize_day_of_week(value: int) -> int:
    return 0 if value == 7 else value


def _date_matches(spec: _CronSpec, candidate_date: date) -> bool:
    if candidate_date.month not in spec.month:
        return False
    dom_matches = candidate_date.day in spec.day_of_month
    cron_day_of_week = (candidate_date.weekday() + 1) % 7
    dow_matches = cron_day_of_week in spec.day_of_week
    if spec.day_of_month_wildcard and spec.day_of_week_wildcard:
        return True
    if spec.day_of_month_wildcard:
        return dow_matches
    if spec.day_of_week_wildcard:
        return dom_matches
    return dom_matches or dow_matches


def _start_of_week(candidate_date: date) -> date:
    return candidate_date - timedelta(days=candidate_date.weekday())


def _load_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown timezone: {timezone}") from error


def _coerce_datetime(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(timezone)
    return value.astimezone(timezone)


def _is_real_local_time(candidate: datetime) -> bool:
    round_tripped = candidate.astimezone(UTC).astimezone(candidate.tzinfo)
    return round_tripped.replace(fold=candidate.fold) == candidate
