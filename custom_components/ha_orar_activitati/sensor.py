"""Sensor platform for the Orar & Activități integration.

Each child gets four sensors -- what is on now, what comes next, today's
timetable and tomorrow's -- which together are everything the card needs to
draw one column.

All four are recomputed on the same schedule: at every slot boundary and at
local midnight, so "acum" flips the instant a lesson ends rather than up to
a minute later.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from . import OrarConfigEntry
from .const import (
    ATTR_ACTIVITIES,
    ATTR_AFTERNOON,
    ATTR_CHILD,
    ATTR_CLASS,
    ATTR_COLOR,
    ATTR_DATE,
    ATTR_DAY_NAME,
    ATTR_FREE,
    ATTR_IS_TOMORROW,
    ATTR_MINUTES_LEFT,
    ATTR_STARTS_IN,
    ATTR_VIEW,
    CONF_CHILD_NAME,
    CONF_CLASS,
    CONF_COLOR,
    CONF_ENTRIES,
    DEFAULT_COLOR,
    DOMAIN,
    WEEKDAY_NAMES_RO,
)
from .schedule import (
    ScheduleEntry,
    afternoon_entries,
    current_entry,
    entries_on,
    minutes_between,
    next_boundary,
    next_entry,
    next_scheduled_day,
    parse_entries,
)

_LOGGER = logging.getLogger(__name__)

# Nothing is polled or fetched, so unlimited parallel updates are fine.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OrarSensorEntityDescription(SensorEntityDescription):
    """Describes one of a child's timetable sensors."""

    #: Produces the state and the attributes from the parsed timetable.
    compute: Callable[[Sequence[ScheduleEntry], datetime], tuple[Any, dict[str, Any]]]


def _compute_now(
    entries: Sequence[ScheduleEntry], now: datetime
) -> tuple[Any, dict[str, Any]]:
    """Return the slot running right now, if any."""
    entry = current_entry(entries, now)

    if entry is None:
        return None, {ATTR_FREE: True}

    ends_at = datetime.combine(now.date(), entry.end, tzinfo=now.tzinfo)

    return entry.title, {
        ATTR_FREE: False,
        ATTR_MINUTES_LEFT: minutes_between(now, ends_at),
        **entry.as_dict(),
    }


def _compute_next(
    entries: Sequence[ScheduleEntry], now: datetime
) -> tuple[Any, dict[str, Any]]:
    """Return the next slot to start, looking into the coming week."""
    upcoming = next_entry(entries, now)

    if upcoming is None:
        return None, {ATTR_FREE: True}

    entry, day = upcoming
    starts_at = datetime.combine(day, entry.start, tzinfo=now.tzinfo)

    return entry.title, {
        ATTR_FREE: False,
        ATTR_STARTS_IN: minutes_between(now, starts_at),
        ATTR_DATE: day.isoformat(),
        ATTR_DAY_NAME: WEEKDAY_NAMES_RO[day.weekday()],
        **entry.as_dict(),
    }


def _compute_day(
    entries: Sequence[ScheduleEntry],
    day: date,
    *,
    today: date | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Return the full timetable for one calendar day.

    The state is the number of slots -- a plain count that works in badges
    and history -- while the slots themselves ride along as attributes.
    """
    of_the_day = entries_on(entries, day)

    return len(of_the_day), {
        ATTR_DATE: day.isoformat(),
        ATTR_DAY_NAME: WEEKDAY_NAMES_RO[day.weekday()],
        ATTR_IS_TOMORROW: today is None or day == today + timedelta(days=1),
        ATTR_ACTIVITIES: [entry.as_dict() for entry in of_the_day],
        ATTR_AFTERNOON: [
            entry.as_dict() for entry in afternoon_entries(of_the_day)
        ],
    }


def _compute_lookahead(
    entries: Sequence[ScheduleEntry], now: datetime
) -> tuple[Any, dict[str, Any]]:
    """Return the next day that has anything scheduled.

    Not simply tomorrow: school runs Monday to Friday, so on a Friday
    evening tomorrow would be an empty Saturday and the band would say
    nothing is coming when Monday is full. Weekend activities still win --
    a Saturday practice shows as Saturday, not skipped in favour of Monday.

    When the whole week is empty this falls back to tomorrow, so the sensor
    still reports a date and a count of zero rather than going unavailable.
    """
    day = next_scheduled_day(entries, now.date()) or now.date() + timedelta(days=1)
    return _compute_day(entries, day, today=now.date())


SENSOR_DESCRIPTIONS: tuple[OrarSensorEntityDescription, ...] = (
    OrarSensorEntityDescription(
        key="acum",
        translation_key="acum",
        icon="mdi:bell-ring",
        compute=_compute_now,
    ),
    OrarSensorEntityDescription(
        key="urmatoarea",
        translation_key="urmatoarea",
        icon="mdi:timer-sand",
        compute=_compute_next,
    ),
    OrarSensorEntityDescription(
        key="azi",
        translation_key="azi",
        icon="mdi:calendar-today",
        compute=lambda entries, now: _compute_day(
            entries, now.date(), today=now.date()
        ),
    ),
    OrarSensorEntityDescription(
        key="maine",
        translation_key="maine",
        icon="mdi:calendar-arrow-right",
        compute=_compute_lookahead,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OrarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timetable sensors for one child."""
    async_add_entities(
        OrarSensor(entry, description) for description in SENSOR_DESCRIPTIONS
    )


class OrarSensor(SensorEntity):
    """One view onto a child's weekly timetable."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    entity_description: OrarSensorEntityDescription

    def __init__(
        self, entry: OrarConfigEntry, description: OrarSensorEntityDescription
    ) -> None:
        """Initialise the sensor."""
        self.entity_description = description
        self._entry = entry
        self._unschedule: Callable[[], None] | None = None

        # Keyed on entry_id rather than on the name, so that renaming the
        # child in the options flow does not orphan the entity or its history.
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self._child_name,
            manufacturer="Orar & Activități",
            model=entry.data.get(CONF_CLASS) or "Copil",
        )

    @property
    def _child_name(self) -> str:
        """Return the name of this child."""
        return self._entry.data.get(CONF_CHILD_NAME) or self._entry.title

    @property
    def _entries(self) -> list[ScheduleEntry]:
        """Return the parsed timetable, dropping any unusable slot.

        Parsed on demand rather than cached: the entry is reloaded whenever
        the options change, so there is no stale copy to invalidate, and a
        week's timetable is a few dozen dicts.
        """
        raw = self._entry.options.get(CONF_ENTRIES) or []
        parsed = parse_entries(raw)

        if len(parsed) != len(raw):
            _LOGGER.warning(
                "%d intrari din orarul lui %s sunt invalide si au fost ignorate",
                len(raw) - len(parsed),
                self._child_name,
            )

        return parsed

    def _computed(self) -> tuple[Any, dict[str, Any]]:
        """Run this sensor's computation against the current local time."""
        return self.entity_description.compute(self._entries, dt_util.now())

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        return self._computed()[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the slot details, plus the child's identity.

        The identity travels on every sensor so the card can draw a whole
        column -- name, class, accent colour -- from a single entity.
        """
        return {
            ATTR_VIEW: self.entity_description.key,
            ATTR_CHILD: self._child_name,
            ATTR_CLASS: self._entry.data.get(CONF_CLASS),
            ATTR_COLOR: self._entry.data.get(CONF_COLOR) or DEFAULT_COLOR,
            **self._computed()[1],
        }

    async def async_added_to_hass(self) -> None:
        """Start recalculating at each slot boundary."""
        await super().async_added_to_hass()
        self._schedule_next()
        self.async_on_remove(self._cancel_scheduled)

    @callback
    def _schedule_next(self) -> None:
        """Arm a one-shot timer for the next boundary.

        Rearmed after every firing rather than run on a fixed interval, so
        an idle evening costs nothing and a lesson change is still exact.
        """
        self._cancel_scheduled()

        now = dt_util.now()
        when = next_boundary(self._entries, now)

        self._unschedule = async_track_point_in_time(
            self.hass, self._handle_boundary, when
        )

    @callback
    def _cancel_scheduled(self) -> None:
        """Cancel the pending timer, if there is one."""
        if self._unschedule is not None:
            self._unschedule()
            self._unschedule = None

    @callback
    def _handle_boundary(self, now: datetime) -> None:
        """Write a fresh state and arm the timer for the boundary after."""
        self.async_write_ha_state()
        self._schedule_next()
