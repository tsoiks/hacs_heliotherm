"""Config flow for the Heliotherm integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from modbus_connection import ModbusError, ModbusTcpParams

from .const import (
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .heliotherm_modbus import HeliothermHeatPump

_LOGGER = logging.getLogger(__name__)

_PORT_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
_UNIT_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
_SCAN_INTERVAL_SCHEMA = vol.All(
    vol.Coerce(int), vol.Range(min=5, max=3600)
)


async def _async_probe(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Read one block from the heat pump to confirm it answers.

    Asking for a unit performs no I/O, so a successful read here is what
    proves the address, port and unit ID are right.
    """
    params = ModbusTcpParams(
        host=user_input[CONF_HOST], port=user_input[CONF_PORT]
    )
    async with async_get_temporary_unit(
        hass, params, user_input[CONF_UNIT_ID]
    ) as unit:
        device = HeliothermHeatPump(unit)
        await device.temperatures.async_update()


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Return the fields of ``user_input`` that are out of range."""
    errors: dict[str, str] = {}
    host = user_input.get(CONF_HOST, "")
    if not isinstance(host, str) or not host.strip():
        errors[CONF_HOST] = "invalid_host"
    port = user_input.get(CONF_PORT)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        errors[CONF_PORT] = "invalid_port"
    unit_id = user_input.get(CONF_UNIT_ID)
    if not isinstance(unit_id, int) or not 0 <= unit_id <= 255:
        errors[CONF_UNIT_ID] = "invalid_unit_id"
    return errors


class HeliothermConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Heliotherm config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HeliothermOptionsFlow:
        """Create the options flow for the scan interval."""
        return HeliothermOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the connection details and probe the heat pump."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}_{user_input[CONF_PORT]}"
                    f"_{user_input[CONF_UNIT_ID]}"
                )
                self._abort_if_unique_id_configured()
                try:
                    await _async_probe(self.hass, user_input)
                except ModbusError as err:
                    _LOGGER.debug("Probe failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"Heliotherm ({user_input[CONF_HOST]})",
                        data=user_input,
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT_SCHEMA,
                    vol.Optional(
                        CONF_UNIT_ID, default=DEFAULT_UNIT_ID
                    ): _UNIT_SCHEMA,
                }
            ),
            errors=errors,
        )


class HeliothermOptionsFlow(OptionsFlow):
    """Let the user pick how often the heat pump is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the scan interval option."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): _SCAN_INTERVAL_SCHEMA,
                }
            ),
        )
