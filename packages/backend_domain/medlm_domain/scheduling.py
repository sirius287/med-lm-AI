"""Bounded, deterministic scheduling. No dose interpretation or notifications."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from medlm_domain.manual_medications import ScheduleInput, iana_zone


def local_instant(naive: datetime, zone: ZoneInfo) -> datetime:
    # An overlap chooses the first instant. A gap moves to the first valid minute.
    for _ in range(2881):
        candidate = naive.replace(tzinfo=zone, fold=0).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            return candidate
        naive += timedelta(minutes=1)
    raise ValueError("Local date could not be resolved")


def occurrences(schedule: ScheduleInput, start: date, end: date, effective: datetime):
    if not 0 <= (end - start).days <= 89:
        raise ValueError("Occurrence generation is limited to 90 days")
    zone = iana_zone(schedule.time_zone)
    start = max(start, schedule.start_date)
    end = min(end, schedule.end_date or end)
    if start > end:
        return []
    lower = max(local_instant(datetime.combine(start, datetime.min.time()), zone), effective)
    upper = local_instant(datetime.combine(end + timedelta(days=1), datetime.min.time()), zone)
    values = set()
    if schedule.kind == "one_time":
        values.add(schedule.one_time_at.astimezone(UTC))
    elif schedule.kind == "fixed_interval":
        anchor = schedule.anchor_at.astimezone(UTC)
        step = timedelta(seconds=int(schedule.interval_hours * 3600))
        offset = max(0, (lower - anchor) // step)
        current = anchor + offset * step
        while current < upper:
            values.add(current)
            current += step
    else:
        day = start
        while day <= end:
            if schedule.kind == "daily_times" or day.weekday() in schedule.weekdays:
                for clock in schedule.local_times:
                    values.add(local_instant(datetime.combine(day, clock), zone))
            day += timedelta(days=1)
    return [
        {"planned_at": instant, "original_local_time": instant.astimezone(zone).isoformat()}
        for instant in sorted(values)
        if lower <= instant < upper
    ]
