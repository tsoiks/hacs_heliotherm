"""The Heliotherm heat pump integration.

Sets a heat pump up on a unit of the shared ``modbus`` connection, polls
it through a coordinator, and forwards to the entity platforms.
"""

from __future__ import annotations

import logging

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from modbus_connection import ModbusTcpParams

from .const import CONF_UNIT_ID
from .coordinator import HeliothermConfigEntry, HeliothermCoordinator
from .heliotherm_modbus import HeliothermHeatPump

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: HeliothermConfigEntry
) -> bool:
    """Set up a heat pump from its config entry."""
    params = ModbusTcpParams(
        host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]
    )
    try:
        unit = async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID])
    except HomeAssistantError as err:
        raise ConfigEntryError(str(err)) from err
    device = HeliothermHeatPump(unit)
    coordinator = HeliothermCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HeliothermConfigEntry
) -> bool:
    """Unload a heat pump, releasing its unit on the shared connection."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
