"""Days when school is off: public holidays and school holidays.

Two sources, because they behave differently. Romanian public holidays are
a solved problem -- fixed rules plus a movable Easter -- so they are
computed rather than typed in. School holidays are published once a year by
the ministry, move around, and differ between schools, so they are entered
by hand as date ranges.

A free day stops school, not life: activities still run, which is why this
module only answers "is school off, and why" and leaves the filtering of
entries to the caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    ACCEPTED_DATE_FORMATS,
    FREE_END,
    FREE_ID,
    FREE_NAME,
    FREE_START,
    HOLIDAY_COUNTRY,
)

_LOGGER = logging.getLogger(__name__)


def parse_date_value(raw: Any) -> date | None:
    """Parse a stored date, or return None if it is unusable.

    ISO is what the date picker writes and is tried first; the Romanian
    formats are accepted so a date edited by hand still works.
    """
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        return None

    if (parsed := dt_util.parse_date(raw)) is not None:
        return parsed

    for date_format in ACCEPTED_DATE_FORMATS:
        try:
            return datetime.strptime(raw, date_format).date()
        except ValueError:
            continue

    return None


@dataclass(frozen=True, kw_only=True)
class FreeRange:
    """One stretch of days with no school, such as a holiday week."""

    uid: str
    start: date
    end: date
    name: str

    def covers(self, day: date) -> bool:
        """Return True if ``day`` falls inside the range, ends included."""
        return self.start <= day <= self.end


def parse_free_range(raw: Mapping[str, Any]) -> FreeRange | None:
    """Build a ``FreeRange`` from stored config, or None if unusable.

    Returning None rather than raising keeps one malformed range from
    taking the whole timetable down; the caller logs and skips it.
    """
    start = parse_date_value(raw.get(FREE_START))
    end = parse_date_value(raw.get(FREE_END))
    name = str(raw.get(FREE_NAME) or "").strip()

    if start is None or end is None or not name or end < start:
        return None

    return FreeRange(
        uid=str(raw.get(FREE_ID) or ""), start=start, end=end, name=name
    )


def parse_free_ranges(raw_ranges: Iterable[Mapping[str, Any]]) -> list[FreeRange]:
    """Parse every stored range, silently dropping the unusable ones."""
    parsed = (parse_free_range(raw) for raw in raw_ranges)
    return [item for item in parsed if item is not None]


class FreeDayLookup:
    """Answers whether school is off on a given day, and why.

    Public holidays are resolved through the `holidays` package, the same
    one Home Assistant's own Workday sensor uses, so Easter and the rest of
    the movable feasts come for free. Years are loaded lazily and kept, so
    a timetable that only ever asks about this week never builds a decade.
    """

    def __init__(
        self,
        ranges: Sequence[FreeRange],
        *,
        public_holidays: bool = True,
        country: str = HOLIDAY_COUNTRY,
    ) -> None:
        """Initialise the lookup."""
        self._ranges = list(ranges)
        self._public_holidays = public_holidays
        self._country = country
        self._loaded_years: set[int] = set()
        self._holidays: Any = None

    def _holiday_name(self, day: date) -> str | None:
        """Return the public-holiday name for ``day``, if it is one."""
        if not self._public_holidays:
            return None

        try:
            if self._holidays is None:
                # Imported here rather than at module scope: the package is
                # only needed when automatic holidays are switched on, and
                # a missing dependency should degrade to the manual ranges
                # rather than stop the platform from loading at all.
                import holidays  # noqa: PLC0415

                self._holidays = holidays.country_holidays(self._country)

            if day.year not in self._loaded_years:
                # Touching a date in the year makes the library populate it.
                self._holidays.get(date(day.year, 1, 1))
                self._loaded_years.add(day.year)

            return self._holidays.get(day)
        except Exception:  # noqa: BLE001 - never break the timetable over this
            _LOGGER.exception(
                "Nu am putut citi sarbatorile legale pentru %s; "
                "raman doar zilele libere introduse manual",
                self._country,
            )
            self._public_holidays = False
            return None

    def name_for(self, day: date) -> str | None:
        """Return why school is off on ``day``, or None if it is a school day.

        Manual ranges win over public holidays, so a school holiday that
        swallows Christmas reads as "Vacanta de iarna" rather than
        "Craciunul" -- the longer, more useful label.
        """
        for free in self._ranges:
            if free.covers(day):
                return free.name

        return self._holiday_name(day)

    def is_free(self, day: date) -> bool:
        """Return True if school is off on ``day``."""
        return self.name_for(day) is not None
