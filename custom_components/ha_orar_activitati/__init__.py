"""The Orar & Activități integration.

Holds a weekly timetable per child -- school hours and after-school
activities -- and exposes what is happening now, what is left today and
what tomorrow looks like as sensors.

There is no I/O: every value is derived from the config entry and the
clock, which is why the integration is declared ``iot_class: calculated``.
"""

from __future__ import annotations

import logging

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type OrarConfigEntry = ConfigEntry

#: Where the bundled Lovelace card is served from, and the file backing it.
CARD_URL = f"/{DOMAIN}/orar-activitati-card.js"
CARD_FILENAME = "orar-activitati-card.js"

#: hass.data flag, so the card is only registered once no matter how many
#: children are configured.
_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def async_setup_entry(hass: HomeAssistant, entry: OrarConfigEntry) -> bool:
    """Set up one child from a config entry."""
    await _async_register_card(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The timetable is edited through the Configure button, so reload the
    # entry whenever the options change to pick up the new slots at once.
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OrarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(hass: HomeAssistant, entry: OrarConfigEntry) -> None:
    """Reload the entry after its timetable has changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and load it in the frontend.

    Shipping the card with the integration means there is nothing to add
    under Settings → Dashboards → Resources by hand. It is registered as an
    extra JS module rather than a Lovelace resource because that also works
    on YAML-mode dashboards, where the resource list is not writable.
    """
    if hass.data.get(_CARD_REGISTERED):
        return
    hass.data[_CARD_REGISTERED] = True

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=True)]
    )

    # The version query string busts the browser cache on upgrade, so a new
    # release never leaves a stale card behind.
    integration = await async_get_integration(hass, DOMAIN)

    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    _LOGGER.debug("Cardul Lovelace a fost inregistrat la %s", CARD_URL)
