"""
U.S. federal business time in America/New_York (ET).
- Business days: Mon–Fri, excluding federal holidays with standard “observed” rules.
- Business hours: 09:00–17:00 local ET (wall; DST via zoneinfo).

Holidays (observed): Sat → prior Fri; Sun → following Mon. Floating holidays
that already fall on Monday are used as-is.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Monday = 0 ... Sunday = 6
_WD_MON = 0
_WD_THU = 3


def _observed_calendar(d: date) -> date:
    """Federal “observed” date when holiday falls on weekend."""
    wd = d.weekday()
    if wd == 5:  # Saturday
        return d - timedelta(days=1)
    if wd == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def _nth_weekday_in_month(year: int, month: int, weekday: int, n: int) -> date:
    """n-th occurrence of weekday (0=Mon) in month (1-based n)."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    first_occ = first + timedelta(days=offset)
    return first_occ + timedelta(weeks=n - 1)


def _last_weekday_in_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last = next_first - timedelta(days=1)
    while last.weekday() != weekday:
        last -= timedelta(days=1)
    return last


def federal_observed_holiday_dates(y: int) -> set[date]:
    """All dates that are non-working federal holidays in year y (ET calendar)."""
    ds: set[date] = set()
    for m, d in (
        (1, 1),   # New Year's Day
        (6, 19),  # Juneteenth
        (7, 4),   # Independence Day
        (11, 11), # Veterans Day
        (12, 25), # Christmas
    ):
        ds.add(_observed_calendar(date(y, m, d)))

    # 若次年元旦落在周末，「 observed 」可能落在本年 12 月（如 2027-01-01 周六 → 2026-12-31）
    spill_nyd = _observed_calendar(date(y + 1, 1, 1))
    if spill_nyd.year == y:
        ds.add(spill_nyd)

    ds.add(_nth_weekday_in_month(y, 1, _WD_MON, 3))   # MLK
    ds.add(_nth_weekday_in_month(y, 2, _WD_MON, 3))   # Presidents' Day
    ds.add(_last_weekday_in_month(y, 5, _WD_MON))  # Memorial Day
    ds.add(_nth_weekday_in_month(y, 9, _WD_MON, 1))   # Labor Day
    ds.add(_nth_weekday_in_month(y, 10, _WD_MON, 2))  # Columbus Day
    ds.add(_nth_weekday_in_month(y, 11, _WD_THU, 4)) # Thanksgiving
    return ds


def is_federal_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    y = d.year
    return d not in federal_observed_holiday_dates(y)


def _combine_et(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=ET)


def _next_calendar_business_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    for _ in range(370):
        if is_federal_business_day(nxt):
            return nxt
        nxt += timedelta(days=1)
    return nxt


def snap_start_of_next_business_session_et(dt_et: datetime) -> datetime:
    """Next moment business hours can begin: next business day 9:00 if outside 9–17 or not a business day."""
    if dt_et.tzinfo is None:
        dt_et = dt_et.replace(tzinfo=ET)
    else:
        dt_et = dt_et.astimezone(ET)

    d = dt_et.date()
    t = dt_et.time()
    start = _combine_et(d, time(9, 0))
    end = _combine_et(d, time(17, 0))

    if not is_federal_business_day(d):
        nd = _next_calendar_business_day(d)
        return _combine_et(nd, time(9, 0))

    if t < time(9, 0):
        return start
    if t >= time(17, 0):
        nd = _next_calendar_business_day(d)
        return _combine_et(nd, time(9, 0))
    return dt_et


def add_business_hours(start_et: datetime, hours: float) -> datetime:
    """
    Advance ``hours`` of federal business time from ``start_et`` (aware ET preferred).
    Fractional hours supported (e.g. 0.5 = 30 minutes).
    """
    if hours <= 0:
        return snap_start_of_next_business_session_et(start_et)

    cur = snap_start_of_next_business_session_et(start_et)
    remaining = float(hours)
    eps = 1e-9

    while remaining > eps:
        d = cur.date()
        if not is_federal_business_day(d):
            nd = _next_calendar_business_day(d)
            cur = _combine_et(nd, time(9, 0))
            continue

        day_end = _combine_et(d, time(17, 0))
        room_h = (day_end - cur).total_seconds() / 3600.0
        if room_h <= eps:
            nd = _next_calendar_business_day(d)
            cur = _combine_et(nd, time(9, 0))
            continue
        if remaining <= room_h + eps:
            return cur + timedelta(hours=remaining)
        remaining -= room_h
        nd = _next_calendar_business_day(d)
        cur = _combine_et(nd, time(9, 0))

    return cur


def random_business_hours(low: float, high: float) -> float:
    return random.uniform(low, high)


def now_et() -> datetime:
    return datetime.now(ET)


def add_calendar_days_et(dt_et: datetime, days: int, *, at_hour: int = 10, at_minute: int = 0) -> datetime:
    """Wall-clock ET: same clock time (default 10:00) N calendar days later."""
    if dt_et.tzinfo is None:
        dt_et = dt_et.replace(tzinfo=ET)
    else:
        dt_et = dt_et.astimezone(ET)
    d = dt_et.date() + timedelta(days=days)
    return _combine_et(d, time(at_hour, at_minute))
