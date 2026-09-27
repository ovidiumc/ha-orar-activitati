"""Constants for the Orar & Activități integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_orar_activitati"

# --- Configuration keys -------------------------------------------------
# The child's identity lives in `entry.data`; the timetable itself lives in
# `entry.options` so it can be edited from the Configure button without
# recreating the entry (and without losing the entities' history).

CONF_CHILD_NAME: Final = "nume_copil"
CONF_CLASS: Final = "clasa"
CONF_COLOR: Final = "culoare"
CONF_ENTRIES: Final = "intrari"
CONF_FREE_RANGES: Final = "zile_libere"
CONF_PUBLIC_HOLIDAYS: Final = "sarbatori_legale"

#: Free-text field of the bulk import step.
CONF_IMPORT: Final = "import_text"

# --- Keys of a single timetable entry -----------------------------------
# Kept in Romanian: they are exposed verbatim in the sensor attributes, so
# renaming them would break any card or template reading them.

ENTRY_ID: Final = "id"
ENTRY_DAYS: Final = "zile"
ENTRY_START: Final = "ora_inceput"
ENTRY_END: Final = "ora_sfarsit"
ENTRY_TITLE: Final = "titlu"
ENTRY_ROOM: Final = "sala"
ENTRY_KIND: Final = "tip"
ENTRY_ONLINE: Final = "online"
ENTRY_URL: Final = "locatie_url"

# --- Keys of a free-day range -------------------------------------------
# A range rather than a single date, because school holidays are weeks
# long: one entry covers "Vacanta de iarna, 20.12 - 07.01".

FREE_ID: Final = "id"
FREE_START: Final = "data_inceput"
FREE_END: Final = "data_sfarsit"
FREE_NAME: Final = "denumire"

#: Country used for the automatic public holidays.
HOLIDAY_COUNTRY: Final = "RO"

# --- Entry kinds --------------------------------------------------------
# `activitate` is what makes an entry count as "after school": the
# `activitati_azi` sensor and the card's afternoon section filter on it,
# rather than on a hard-coded hour, because a 16:30 football practice and a
# 13:45 online drawing class are both activities while an 17:00 remedial
# maths *lesson* is not.

KIND_SCHOOL: Final = "scoala"
KIND_ACTIVITY: Final = "activitate"
KIND_BREAK: Final = "pauza"

KINDS: Final[tuple[str, ...]] = (KIND_SCHOOL, KIND_ACTIVITY, KIND_BREAK)

#: Icon shown by the card for each kind.
KIND_ICONS: Final[dict[str, str]] = {
    KIND_SCHOOL: "mdi:school",
    KIND_ACTIVITY: "mdi:star-four-points",
    KIND_BREAK: "mdi:food-apple",
}

# --- Colors -------------------------------------------------------------
# Per-child accent colour, used by the card for the column header and the
# glow. Free-form so any CSS colour works, with the two from the design as
# the suggested values.

DEFAULT_COLORS: Final[tuple[str, ...]] = ("#2196f3", "#ff9800", "#4caf50", "#e91e63")
DEFAULT_COLOR: Final = DEFAULT_COLORS[0]

# --- Formats ------------------------------------------------------------

#: How a time is rendered in the display attributes, e.g. 11:30.
TIME_FORMAT: Final = "%H:%M"

#: Romanian display format for dates, e.g. 20.12.2026.
DATE_FORMAT_RO: Final = "%d.%m.%Y"

#: Non-ISO date formats accepted when parsing, for values edited by hand.
#: ISO is what the date picker writes and is tried first, separately.
ACCEPTED_DATE_FORMATS: Final[tuple[str, ...]] = (
    DATE_FORMAT_RO,
    "%d/%m/%Y",
    "%d-%m-%Y",
)

#: Romanian weekday names, indexed by `date.weekday()` (0 = Monday).
WEEKDAY_NAMES_RO: Final[tuple[str, ...]] = (
    "Luni",
    "Marți",
    "Miercuri",
    "Joi",
    "Vineri",
    "Sâmbătă",
    "Duminică",
)

# --- Sensor attribute names ---------------------------------------------

#: Which of the four views a sensor is. The card keys off this rather than
#: off the entity_id, which changes with the language and with any rename.
ATTR_VIEW: Final = "vizualizare"

ATTR_CHILD: Final = "copil"
ATTR_CLASS: Final = "clasa"
ATTR_COLOR: Final = "culoare"
ATTR_INTERVAL: Final = "interval"
ATTR_START: Final = "ora_inceput"
ATTR_END: Final = "ora_sfarsit"
ATTR_TITLE: Final = "titlu"
ATTR_ROOM: Final = "sala"
ATTR_KIND: Final = "tip"
ATTR_ONLINE: Final = "online"
ATTR_URL: Final = "locatie_url"
ATTR_ICON: Final = "iconita"
ATTR_MINUTES_LEFT: Final = "minute_ramase"
ATTR_STARTS_IN: Final = "incepe_in"
ATTR_FREE: Final = "liber"

#: Set on every sensor for the day it describes: whether school is off, and
#: why. Activities still run on a free day, so this is not the same as the
#: day being empty.
ATTR_FREE_DAY: Final = "zi_libera"
ATTR_FREE_DAY_NAME: Final = "denumire_zi_libera"
ATTR_DATE: Final = "data"
ATTR_DAY_NAME: Final = "zi"
#: True when the lookahead day really is tomorrow. School stops at the
#: weekend, so on a Friday the lookahead is usually Monday, and the card
#: has to label it by name rather than calling it "tomorrow".
ATTR_IS_TOMORROW: Final = "este_maine"

ATTR_ACTIVITIES: Final = "activitati"
ATTR_AFTERNOON: Final = "activitati_dupa_masa"

# --- Config flow error keys ---------------------------------------------

ERROR_INVALID_NAME: Final = "invalid_name"
ERROR_ALREADY_CONFIGURED: Final = "already_configured"
ERROR_INVALID_INTERVAL: Final = "invalid_interval"
ERROR_NO_DAYS: Final = "no_days"
ERROR_INVALID_RANGE: Final = "invalid_range"
ERROR_NO_NAME: Final = "no_name"
ERROR_IMPORT_FAILED: Final = "import_failed"
