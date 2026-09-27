"""Config and options flow for the Orar & Activități integration.

Adding a child asks for the bare minimum -- a name -- so the entry exists
straight away. The timetable itself is built afterwards from the Configure
button, through a menu that adds, edits and removes one slot at a time.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CHILD_NAME,
    CONF_CLASS,
    CONF_COLOR,
    CONF_ENTRIES,
    CONF_FREE_RANGES,
    CONF_PUBLIC_HOLIDAYS,
    DEFAULT_COLOR,
    DOMAIN,
    ENTRY_DAYS,
    ENTRY_END,
    ENTRY_ID,
    ENTRY_KIND,
    ENTRY_ONLINE,
    ENTRY_ROOM,
    ENTRY_START,
    ENTRY_TITLE,
    ENTRY_URL,
    ERROR_ALREADY_CONFIGURED,
    ERROR_INVALID_RANGE,
    ERROR_NO_NAME,
    ERROR_INVALID_INTERVAL,
    ERROR_INVALID_NAME,
    ERROR_NO_DAYS,
    FREE_END,
    FREE_ID,
    FREE_NAME,
    FREE_START,
    KIND_SCHOOL,
    KINDS,
    DATE_FORMAT_RO,
    TIME_FORMAT,
    WEEKDAY_NAMES_RO,
)
from .freedays import parse_date_value
from .schedule import parse_time_value


def normalise_name(raw: str) -> str:
    """Collapse whitespace in a child's name, for use as a unique id."""
    return " ".join(raw.split())


def _child_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the child identity form, pre-filled with the current values."""
    return vol.Schema(
        {
            vol.Required(
                CONF_CHILD_NAME,
                description={"suggested_value": defaults.get(CONF_CHILD_NAME)},
            ): selector.TextSelector(),
            vol.Optional(
                CONF_CLASS,
                description={"suggested_value": defaults.get(CONF_CLASS)},
            ): selector.TextSelector(),
            vol.Optional(
                CONF_COLOR,
                description={
                    "suggested_value": defaults.get(CONF_COLOR) or DEFAULT_COLOR
                },
            ): selector.TextSelector(),
        }
    )


def _slot_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the form for one timetable slot."""
    return vol.Schema(
        {
            vol.Required(
                ENTRY_TITLE,
                description={"suggested_value": defaults.get(ENTRY_TITLE)},
            ): selector.TextSelector(),
            vol.Required(
                ENTRY_DAYS,
                description={"suggested_value": defaults.get(ENTRY_DAYS)},
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=str(index), label=name)
                        for index, name in enumerate(WEEKDAY_NAMES_RO)
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                ENTRY_START,
                description={"suggested_value": defaults.get(ENTRY_START)},
            ): selector.TimeSelector(),
            vol.Required(
                ENTRY_END,
                description={"suggested_value": defaults.get(ENTRY_END)},
            ): selector.TimeSelector(),
            vol.Required(
                ENTRY_KIND,
                description={
                    "suggested_value": defaults.get(ENTRY_KIND) or KIND_SCHOOL
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(KINDS),
                    translation_key="tip_intrare",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                ENTRY_ROOM,
                description={"suggested_value": defaults.get(ENTRY_ROOM)},
            ): selector.TextSelector(),
            vol.Optional(
                ENTRY_ONLINE,
                description={"suggested_value": defaults.get(ENTRY_ONLINE, False)},
            ): selector.BooleanSelector(),
            vol.Optional(
                ENTRY_URL,
                description={"suggested_value": defaults.get(ENTRY_URL)},
            ): selector.TextSelector(),
        }
    )


def _validate_slot(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Return the form errors for a submitted slot, empty when it is valid."""
    errors: dict[str, str] = {}

    if not user_input.get(ENTRY_DAYS):
        errors[ENTRY_DAYS] = ERROR_NO_DAYS

    start = parse_time_value(user_input.get(ENTRY_START))
    end = parse_time_value(user_input.get(ENTRY_END))

    # An end at or before the start would silently produce a slot that can
    # never be "now", so it is rejected rather than stored.
    if start is None or end is None or start >= end:
        errors[ENTRY_END] = ERROR_INVALID_INTERVAL

    return errors


def _slot_from_input(user_input: Mapping[str, Any], uid: str) -> dict[str, Any]:
    """Build the stored slot from a validated form submission."""
    return {
        ENTRY_ID: uid,
        ENTRY_TITLE: normalise_name(str(user_input[ENTRY_TITLE])),
        ENTRY_DAYS: sorted(int(day) for day in user_input[ENTRY_DAYS]),
        ENTRY_START: user_input[ENTRY_START],
        ENTRY_END: user_input[ENTRY_END],
        ENTRY_KIND: user_input.get(ENTRY_KIND, KIND_SCHOOL),
        ENTRY_ROOM: (str(user_input.get(ENTRY_ROOM) or "").strip() or None),
        ENTRY_ONLINE: bool(user_input.get(ENTRY_ONLINE)),
        ENTRY_URL: (str(user_input.get(ENTRY_URL) or "").strip() or None),
    }


def _free_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the form for one stretch of days without school."""
    return vol.Schema(
        {
            vol.Required(
                FREE_NAME,
                description={"suggested_value": defaults.get(FREE_NAME)},
            ): selector.TextSelector(),
            vol.Required(
                FREE_START,
                description={"suggested_value": defaults.get(FREE_START)},
            ): selector.DateSelector(),
            vol.Required(
                FREE_END,
                description={"suggested_value": defaults.get(FREE_END)},
            ): selector.DateSelector(),
        }
    )


def _validate_free(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Return the form errors for a submitted range, empty when valid."""
    errors: dict[str, str] = {}

    if not str(user_input.get(FREE_NAME) or "").strip():
        errors[FREE_NAME] = ERROR_NO_NAME

    start = parse_date_value(user_input.get(FREE_START))
    end = parse_date_value(user_input.get(FREE_END))

    # A single day is a valid range, so only an end *before* the start is
    # rejected -- that would silently cover nothing.
    if start is None or end is None or end < start:
        errors[FREE_END] = ERROR_INVALID_RANGE

    return errors


def _free_from_input(user_input: Mapping[str, Any], uid: str) -> dict[str, Any]:
    """Build the stored range from a validated form submission."""
    return {
        FREE_ID: uid,
        FREE_NAME: " ".join(str(user_input[FREE_NAME]).split()),
        FREE_START: user_input[FREE_START],
        FREE_END: user_input[FREE_END],
    }


def _free_label(free: Mapping[str, Any]) -> str:
    """Return a one-line description of a range, for the pick lists."""
    start = parse_date_value(free.get(FREE_START))
    end = parse_date_value(free.get(FREE_END))
    name = free.get(FREE_NAME) or "?"

    if start is None or end is None:
        return f"{name} | ??"
    if start == end:
        return f"{name} | {start.strftime(DATE_FORMAT_RO)}"

    return (
        f"{name} | {start.strftime(DATE_FORMAT_RO)}"
        f" - {end.strftime(DATE_FORMAT_RO)}"
    )


def _slot_label(slot: Mapping[str, Any]) -> str:
    """Return a one-line description of a slot, for the pick lists.

    Reads as "Lu, Mi | 11:30 - 13:00 | Matematică (Sala 104)", which is
    enough to tell two otherwise identical lessons apart.
    """
    days = ", ".join(
        WEEKDAY_NAMES_RO[int(day)][:2] for day in slot.get(ENTRY_DAYS) or ()
    )

    start = parse_time_value(slot.get(ENTRY_START))
    end = parse_time_value(slot.get(ENTRY_END))
    interval = (
        f"{start.strftime(TIME_FORMAT)} - {end.strftime(TIME_FORMAT)}"
        if start and end
        else "??"
    )

    title = slot.get(ENTRY_TITLE) or "?"
    room = slot.get(ENTRY_ROOM)

    return f"{days} | {interval} | {title}" + (f" ({room})" if room else "")


class OrarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding a child."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a child, keyed by their name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = normalise_name(user_input[CONF_CHILD_NAME])

            if not name:
                errors[CONF_CHILD_NAME] = ERROR_INVALID_NAME
            else:
                # The name is the unique id, so the same child cannot be
                # added twice even if typed with different spacing.
                await self.async_set_unique_id(name.casefold())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_CHILD_NAME: name,
                        CONF_CLASS: (
                            str(user_input.get(CONF_CLASS) or "").strip() or None
                        ),
                        CONF_COLOR: (
                            str(user_input.get(CONF_COLOR) or "").strip()
                            or DEFAULT_COLOR
                        ),
                    },
                    # The timetable starts empty and is filled in from the
                    # Configure button, one slot at a time.
                    options={CONF_ENTRIES: []},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_child_schema(dict(user_input or {})),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OrarOptionsFlow:
        """Return the options flow handler."""
        return OrarOptionsFlow()


class OrarOptionsFlow(OptionsFlow):
    """Edit a child's details and build their weekly timetable.

    The slots are held in ``self._slots`` while the menu is open and only
    written back on "Gata", so backing out of the flow halfway through
    cannot leave a half-edited timetable behind.
    """

    def __init__(self) -> None:
        """Initialise the in-progress timetable."""
        self._slots: list[dict[str, Any]] = []
        self._free: list[dict[str, Any]] = []
        self._public_holidays = True
        self._loaded = False
        self._editing: str | None = None

    def _load(self) -> None:
        """Take a working copy of the stored timetable, once per flow."""
        if self._loaded:
            return
        options = self.config_entry.options
        self._slots = [dict(slot) for slot in options.get(CONF_ENTRIES, [])]
        self._free = [dict(free) for free in options.get(CONF_FREE_RANGES, [])]
        self._public_holidays = options.get(CONF_PUBLIC_HOLIDAYS, True)
        self._loaded = True

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the timetable menu."""
        self._load()

        # Edit and remove are pointless on an empty timetable, so they are
        # left out until there is something to act on.
        options = ["adauga"]
        if self._slots:
            options += ["editeaza", "sterge"]
        options += ["libere", "copil", "gata"]

        return self.async_show_menu(
            step_id="init",
            menu_options=options,
            description_placeholders={
                "numar": str(len(self._slots)),
                "libere": str(len(self._free)),
            },
        )

    async def async_step_libere(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the free-days menu."""
        self._load()

        options = ["adauga_liber"]
        if self._free:
            options += ["sterge_liber"]
        options += ["sarbatori", "init"]

        return self.async_show_menu(
            step_id="libere",
            menu_options=options,
            description_placeholders={
                "libere": str(len(self._free)),
                "sarbatori": "pornite" if self._public_holidays else "oprite",
            },
        )

    async def async_step_adauga_liber(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one stretch of days without school."""
        self._load()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_free(user_input)
            if not errors:
                self._free.append(_free_from_input(user_input, uuid4().hex))
                return await self.async_step_libere()

        return self.async_show_form(
            step_id="adauga_liber",
            data_schema=_free_schema(dict(user_input or {})),
            errors=errors,
        )

    async def async_step_sterge_liber(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more free-day ranges."""
        self._load()

        if user_input is not None:
            doomed = set(user_input.get(FREE_ID) or ())
            self._free = [
                free for free in self._free if free[FREE_ID] not in doomed
            ]
            return await self.async_step_libere()

        return self.async_show_form(
            step_id="sterge_liber",
            data_schema=vol.Schema(
                {
                    vol.Optional(FREE_ID, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=free[FREE_ID], label=_free_label(free)
                                )
                                for free in self._sorted_free()
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_sarbatori(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Switch the automatic Romanian public holidays on or off."""
        self._load()

        if user_input is not None:
            self._public_holidays = bool(user_input.get(CONF_PUBLIC_HOLIDAYS))
            return await self.async_step_libere()

        return self.async_show_form(
            step_id="sarbatori",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PUBLIC_HOLIDAYS,
                        description={"suggested_value": self._public_holidays},
                    ): selector.BooleanSelector()
                }
            ),
        )

    async def async_step_adauga(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one slot to the timetable."""
        self._load()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_slot(user_input)
            if not errors:
                self._slots.append(_slot_from_input(user_input, uuid4().hex))
                return await self.async_step_init()

        return self.async_show_form(
            step_id="adauga",
            data_schema=_slot_schema(dict(user_input or {})),
            errors=errors,
        )

    async def async_step_editeaza(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the slot to edit."""
        self._load()

        if user_input is not None:
            self._editing = user_input[ENTRY_ID]
            return await self.async_step_modifica()

        return self.async_show_form(
            step_id="editeaza",
            data_schema=vol.Schema(
                {
                    vol.Required(ENTRY_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=slot[ENTRY_ID], label=_slot_label(slot)
                                )
                                for slot in self._sorted_slots()
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_modifica(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the slot picked in the previous step."""
        self._load()

        current = self._slot_by_id(self._editing)
        if current is None:
            # The slot vanished (a parallel edit, or a stale flow); drop
            # back to the menu rather than writing to nothing.
            return await self.async_step_init()

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_slot(user_input)
            if not errors:
                updated = _slot_from_input(user_input, current[ENTRY_ID])
                self._slots = [
                    updated if slot[ENTRY_ID] == current[ENTRY_ID] else slot
                    for slot in self._slots
                ]
                self._editing = None
                return await self.async_step_init()

        defaults = dict(current)
        if user_input is not None:
            defaults.update(user_input)
        # The multi-select hands back strings, so the stored ints have to be
        # rendered the same way or nothing shows as selected.
        defaults[ENTRY_DAYS] = [str(day) for day in defaults.get(ENTRY_DAYS) or ()]

        return self.async_show_form(
            step_id="modifica",
            data_schema=_slot_schema(defaults),
            errors=errors,
            description_placeholders={"intrare": _slot_label(current)},
        )

    async def async_step_sterge(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more slots."""
        self._load()

        if user_input is not None:
            doomed = set(user_input.get(ENTRY_ID) or ())
            self._slots = [
                slot for slot in self._slots if slot[ENTRY_ID] not in doomed
            ]
            return await self.async_step_init()

        return self.async_show_form(
            step_id="sterge",
            data_schema=vol.Schema(
                {
                    vol.Optional(ENTRY_ID, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=slot[ENTRY_ID], label=_slot_label(slot)
                                )
                                for slot in self._sorted_slots()
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_copil(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the child's name, class and colour."""
        self._load()
        entry = self.config_entry
        errors: dict[str, str] = {}

        if user_input is not None:
            name = normalise_name(user_input[CONF_CHILD_NAME])

            if not name:
                errors[CONF_CHILD_NAME] = ERROR_INVALID_NAME
            elif self._name_taken(name):
                errors[CONF_CHILD_NAME] = ERROR_ALREADY_CONFIGURED
            else:
                # Renaming is safe: entity unique ids are derived from the
                # entry_id, not from the name, so history survives it.
                self.hass.config_entries.async_update_entry(
                    entry,
                    title=name,
                    unique_id=name.casefold(),
                    data={
                        **entry.data,
                        CONF_CHILD_NAME: name,
                        CONF_CLASS: (
                            str(user_input.get(CONF_CLASS) or "").strip() or None
                        ),
                        CONF_COLOR: (
                            str(user_input.get(CONF_COLOR) or "").strip()
                            or DEFAULT_COLOR
                        ),
                    },
                )
                return await self.async_step_init()

        defaults = {
            CONF_CHILD_NAME: entry.data.get(CONF_CHILD_NAME, entry.title),
            CONF_CLASS: entry.data.get(CONF_CLASS),
            CONF_COLOR: entry.data.get(CONF_COLOR),
        }
        if user_input is not None:
            defaults.update(user_input)

        return self.async_show_form(
            step_id="copil", data_schema=_child_schema(defaults), errors=errors
        )

    async def async_step_gata(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save the timetable and close the flow."""
        self._load()
        return self.async_create_entry(
            data={
                CONF_ENTRIES: self._sorted_slots(),
                CONF_FREE_RANGES: self._sorted_free(),
                CONF_PUBLIC_HOLIDAYS: self._public_holidays,
            }
        )

    def _sorted_slots(self) -> list[dict[str, Any]]:
        """Return the slots in the order they run during the week."""
        return sorted(
            self._slots,
            key=lambda slot: (
                min((int(day) for day in slot.get(ENTRY_DAYS) or ()), default=7),
                str(slot.get(ENTRY_START) or ""),
                str(slot.get(ENTRY_TITLE) or ""),
            ),
        )

    def _sorted_free(self) -> list[dict[str, Any]]:
        """Return the free-day ranges in calendar order."""
        return sorted(self._free, key=lambda free: str(free.get(FREE_START) or ""))

    def _slot_by_id(self, uid: str | None) -> dict[str, Any] | None:
        """Return the slot with this id, or None if it is gone."""
        return next((slot for slot in self._slots if slot[ENTRY_ID] == uid), None)

    def _name_taken(self, name: str) -> bool:
        """Return True if another configured child already uses this name."""
        return any(
            other.entry_id != self.config_entry.entry_id
            and other.unique_id == name.casefold()
            for other in self.hass.config_entries.async_entries(DOMAIN)
        )
