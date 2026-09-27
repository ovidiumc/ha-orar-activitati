"""Timetable model and the pure logic built on top of it.

Everything here is deliberately free of Home Assistant imports (bar the
datetime helpers) so the interesting decisions -- what counts as "now",
what the next boundary is -- can be reasoned about, and tested, on their
own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .const import (
    ATTR_END,
    ATTR_ICON,
    ATTR_INTERVAL,
    ATTR_KIND,
    ATTR_ONLINE,
    ATTR_ROOM,
    ATTR_START,
    ATTR_TITLE,
    ATTR_URL,
    ENTRY_DAYS,
    ENTRY_END,
    ENTRY_ID,
    ENTRY_KIND,
    ENTRY_ONLINE,
    ENTRY_ROOM,
    ENTRY_START,
    ENTRY_TITLE,
    ENTRY_URL,
    KIND_ACTIVITY,
    KIND_ICONS,
    KIND_SCHOOL,
    TIME_FORMAT,
)


def parse_time_value(raw: Any) -> time | None:
    """Parse a stored time, or return None if it is unusable.

    ``TimeSelector`` writes ``HH:MM:SS``, but a config restored or edited by
    hand may well carry ``HH:MM`` instead, so both are accepted.
    """
    if isinstance(raw, time):
        return raw
    if not isinstance(raw, str):
        return None

    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, time_format).time()
        except ValueError:
            continue

    return None


@dataclass(frozen=True, kw_only=True)
class ScheduleEntry:
    """One recurring slot in a child's week.

    A single entry can repeat on several weekdays, so "Matematică, Mon/Wed,
    11:30-13:00" is one entry rather than two -- editing the hour then only
    has to happen once.
    """

    uid: str
    days: frozenset[int]
    start: time
    end: time
    title: str
    room: str | None
    kind: str
    online: bool
    url: str | None

    @property
    def interval(self) -> str:
        """Return the slot as it is displayed, e.g. ``11:30 - 13:00``."""
        return f"{self.start.strftime(TIME_FORMAT)} - {self.end.strftime(TIME_FORMAT)}"

    @property
    def icon(self) -> str:
        """Return the icon the card should use for this entry."""
        return KIND_ICONS.get(self.kind, KIND_ICONS[KIND_SCHOOL])

    def occurs_on(self, day: date) -> bool:
        """Return True if this entry runs on the given calendar day."""
        return day.weekday() in self.days

    def contains(self, moment: time) -> bool:
        """Return True if ``moment`` falls inside the slot.

        The start is inclusive and the end exclusive, so back-to-back slots
        (13:00-13:30 lunch, 13:45-14:30 art) never both report as current.
        """
        return self.start <= moment < self.end

    def as_dict(self) -> dict[str, Any]:
        """Return the display payload consumed by the card and templates."""
        return {
            ATTR_START: self.start.strftime(TIME_FORMAT),
            ATTR_END: self.end.strftime(TIME_FORMAT),
            ATTR_INTERVAL: self.interval,
            ATTR_TITLE: self.title,
            ATTR_ROOM: self.room,
            ATTR_KIND: self.kind,
            ATTR_ONLINE: self.online,
            ATTR_URL: self.url,
            ATTR_ICON: self.icon,
        }


def parse_entry(raw: Mapping[str, Any]) -> ScheduleEntry | None:
    """Build a ``ScheduleEntry`` from stored config, or None if unusable.

    Returning None rather than raising keeps one malformed entry -- from a
    hand-edited ``.storage`` file, say -- from taking the whole child's
    timetable down with it; the caller logs and skips it.
    """
    start = parse_time_value(raw.get(ENTRY_START))
    end = parse_time_value(raw.get(ENTRY_END))
    title = str(raw.get(ENTRY_TITLE) or "").strip()

    if start is None or end is None or not title or start >= end:
        return None

    try:
        days = frozenset(int(day) for day in raw.get(ENTRY_DAYS) or ())
    except (TypeError, ValueError):
        return None

    if not days or any(day not in range(7) for day in days):
        return None

    room = str(raw.get(ENTRY_ROOM) or "").strip() or None
    url = str(raw.get(ENTRY_URL) or "").strip() or None

    return ScheduleEntry(
        uid=str(raw.get(ENTRY_ID) or ""),
        days=days,
        start=start,
        end=end,
        title=title,
        room=room,
        kind=str(raw.get(ENTRY_KIND) or KIND_SCHOOL),
        online=bool(raw.get(ENTRY_ONLINE)),
        url=url,
    )


def parse_entries(raw_entries: Iterable[Mapping[str, Any]]) -> list[ScheduleEntry]:
    """Parse every stored entry, silently dropping the unusable ones."""
    parsed = (parse_entry(raw) for raw in raw_entries)
    return [entry for entry in parsed if entry is not None]


def entries_on(
    entries: Sequence[ScheduleEntry], day: date
) -> list[ScheduleEntry]:
    """Return the entries running on ``day``, in chronological order."""
    return sorted(
        (entry for entry in entries if entry.occurs_on(day)),
        key=lambda entry: (entry.start, entry.end, entry.title),
    )


def afternoon_entries(entries: Iterable[ScheduleEntry]) -> list[ScheduleEntry]:
    """Return only the after-school activities out of a day's entries."""
    return [entry for entry in entries if entry.kind == KIND_ACTIVITY]


def current_entry(
    entries: Sequence[ScheduleEntry], moment: datetime
) -> ScheduleEntry | None:
    """Return the entry running at ``moment``, if any."""
    for entry in entries_on(entries, moment.date()):
        if entry.contains(moment.time()):
            return entry
    return None


def next_entry(
    entries: Sequence[ScheduleEntry], moment: datetime
) -> tuple[ScheduleEntry, date] | None:
    """Return the next entry to start, and the day it starts on.

    Looks at the rest of today first, then walks forward a full week so the
    Friday-evening state is "Monday, 08:00 Matematică" rather than empty.
    Returns None only when the child has no entries at all.
    """
    for entry in entries_on(entries, moment.date()):
        if entry.start > moment.time():
            return entry, moment.date()

    for offset in range(1, 8):
        day = moment.date() + timedelta(days=offset)
        upcoming = entries_on(entries, day)
        if upcoming:
            return upcoming[0], day

    return None


def next_boundary(entries: Sequence[ScheduleEntry], moment: datetime) -> datetime:
    """Return when the sensors must next be recalculated.

    That is the first start or end time still ahead of us today; failing
    that, midnight, which is both the day rollover and the moment "today"
    and "tomorrow" change meaning.
    """
    midnight = datetime.combine(
        moment.date() + timedelta(days=1), time.min, tzinfo=moment.tzinfo
    )

    candidates = [
        datetime.combine(moment.date(), boundary, tzinfo=moment.tzinfo)
        for entry in entries_on(entries, moment.date())
        for boundary in (entry.start, entry.end)
    ]
    future = [candidate for candidate in candidates if candidate > moment]

    return min(future) if future else midnight


def minutes_between(start: datetime, end: datetime) -> int:
    """Return whole minutes from ``start`` to ``end``, never below zero."""
    return max(0, int((end - start).total_seconds() // 60))
