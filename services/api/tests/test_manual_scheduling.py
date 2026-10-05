from datetime import UTC, date, datetime, timedelta

import pytest
from medlm_domain.manual_medications import MedicationInput, ScheduleInput
from medlm_domain.scheduling import occurrences
from pydantic import ValidationError


def schedule(**values):
    return ScheduleInput.model_validate(
        dict(
            kind="daily_times",
            time_zone="Asia/Kolkata",
            start_date="2028-01-01",
            open_ended=True,
            local_times=["08:00"],
            **values,
        )
    )


def test_leap_year_and_month_boundaries():
    s = schedule()
    for start in (date(2028, 2, 28), date(2028, 12, 31)):
        result = occurrences(s, start, start + timedelta(days=2), datetime(2028, 1, 1, tzinfo=UTC))
        assert len(result) == 3
        assert all(r["planned_at"].hour == 2 and r["planned_at"].minute == 30 for r in result)
        assert len({r["planned_at"] for r in result}) == len(result)


@pytest.mark.parametrize(
    "day,clock,expected",
    [
        ("2028-03-12", "02:30", "2028-03-12T07:00:00+00:00"),
        ("2028-11-05", "01:30", "2028-11-05T05:30:00+00:00"),
    ],
)
def test_dst_gap_and_overlap(day, clock, expected):
    s = ScheduleInput(
        kind="daily_times",
        time_zone="America/New_York",
        start_date=day,
        end_date=day,
        local_times=[clock],
    )
    result = occurrences(
        s, date.fromisoformat(day), date.fromisoformat(day), datetime(2028, 1, 1, tzinfo=UTC)
    )
    assert [r["planned_at"].isoformat() for r in result] == [expected]


def test_elapsed_interval_stays_elapsed_across_dst():
    s = ScheduleInput(
        kind="fixed_interval",
        time_zone="America/New_York",
        start_date="2028-03-11",
        open_ended=True,
        interval_hours="12",
        anchor_at="2028-03-11T08:00:00-05:00",
    )
    result = occurrences(s, date(2028, 3, 11), date(2028, 3, 13), datetime(2028, 1, 1, tzinfo=UTC))
    assert all(
        b["planned_at"] - a["planned_at"] == timedelta(hours=12) for a, b in zip(result, result[1:])
    )


def test_weekdays_one_time_and_explicit_boundaries():
    s = ScheduleInput(
        kind="weekdays",
        time_zone="Asia/Kolkata",
        start_date="2028-01-03",
        end_date="2028-01-10",
        weekdays=[0],
        local_times=["08:00"],
    )
    result = occurrences(s, date(2028, 1, 1), date(2028, 1, 20), datetime(2028, 1, 1, tzinfo=UTC))
    assert len(result) == 2
    s = ScheduleInput(
        kind="one_time",
        time_zone="Asia/Kolkata",
        start_date="2028-01-03",
        end_date="2028-01-03",
        one_time_at="2028-01-03T08:00:00+05:30",
    )
    assert (
        len(occurrences(s, date(2028, 1, 1), date(2028, 1, 5), datetime(2028, 1, 1, tzinfo=UTC)))
        == 1
    )


@pytest.mark.parametrize(
    "change",
    [
        {"open_ended": False},
        {"local_times": ["08:00", "08:00"]},
        {"time_zone": "invalid/zone"},
        {"weekdays": [1]},
        {"interval_hours": "12"},
        {"local_times": ["08:00:01"]},
        {"end_date": "2027-01-01"},
    ],
)
def test_invalid_schedule_is_not_guessed(change):
    body = dict(
        kind="daily_times",
        time_zone="Asia/Kolkata",
        start_date="2028-01-01",
        open_ended=True,
        local_times=["08:00"],
    )
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(body | change)


def test_no_inferred_medical_fields_or_provenance():
    with pytest.raises(ValidationError):
        MedicationInput(display_name="Synthetic", dose_text="   ")
    with pytest.raises(ValidationError):
        MedicationInput(
            display_name="Synthetic", dose_text="Literal", origin="confirmed_prescription"
        )


def test_bounded_generation_and_effective_cutoff():
    s = schedule()
    with pytest.raises(ValueError):
        occurrences(s, date(2028, 1, 1), date(2029, 1, 1), datetime(2028, 1, 1, tzinfo=UTC))
    assert (
        occurrences(s, date(2028, 1, 1), date(2028, 1, 1), datetime(2028, 1, 2, tzinfo=UTC)) == []
    )


def test_calendar_properties_across_zones_and_random_date_windows():
    from random import Random

    from medlm_domain.manual_medications import iana_zone

    random = Random(20261005)
    for _ in range(150):
        day = date(2028, 1, 1) + timedelta(days=random.randrange(730))
        zone = random.choice(["Asia/Kolkata", "America/New_York", "Europe/London", "Pacific/Apia"])
        times = random.sample(["00:00", "01:30", "02:30", "08:00", "23:59"], random.randrange(1, 5))
        s = ScheduleInput(
            kind="daily_times",
            time_zone=zone,
            start_date=day,
            end_date=day + timedelta(days=10),
            local_times=times,
        )
        values = occurrences(s, day, day + timedelta(days=10), datetime(2027, 1, 1, tzinfo=UTC))
        instants = [r["planned_at"] for r in values]
        assert instants == sorted(set(instants))
        assert all(
            day <= value.astimezone(iana_zone(zone)).date() <= day + timedelta(days=10)
            for value in instants
        )
        assert values == occurrences(
            s, day, day + timedelta(days=10), datetime(2027, 1, 1, tzinfo=UTC)
        )


@pytest.mark.parametrize(
    "name", ["C:/Windows/win.ini", "../UTC", "/etc/localtime", "America\\New_York"]
)
def test_timezone_names_cannot_escape_packaged_data(name, monkeypatch):
    import medlm_domain.manual_medications as module

    def forbidden_lookup(*args):
        raise AssertionError("Unsafe timezone reached filesystem lookup")

    monkeypatch.setattr(module, "files", forbidden_lookup)
    with pytest.raises(ValueError):
        module.iana_zone(name)
