"""
Config flow for Heliotherm integration.

Handles user configuration:
- Host and port for Modbus TCP connection
- Slave ID for Modbus device
- Read-only mode toggle (disable write operations)
"""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT, CONF_SLAVE_ID, CONF_READ_ONLY

_LOGGER = logging.getLogger(__name__)


class HeliotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Heliotherm integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle user-initiated config flow.

        Called when user adds integration via UI.
        Presents form for host, port, slave_id, and read_only mode.

        Args:
            user_input: Dictionary with form values or None if first display

        Returns:
            FlowResult - next step (form or create entry)
        """

        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate input
            validation_errors = self._validate_input(user_input)
            if validation_errors:
                for field, error in validation_errors.items():
                    errors[field] = error
            else:
                # Input valid, create config entry
                return self.async_create_entry(
                    title=f"Heliotherm ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        # Display form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_SLAVE_ID, default=1): int,
                    vol.Optional(CONF_READ_ONLY, default=True): bool,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """
        Validate user input.

        Args:
            user_input: Dictionary with form values

        Returns:
            Dictionary of field: error_key pairs, empty if valid
        """

        errors: dict[str, str] = {}

        # Validate host
        host = user_input.get(CONF_HOST)
        if not host or not isinstance(host, str):
            errors[CONF_HOST] = "invalid_host"
        elif host.strip() == "":
            errors[CONF_HOST] = "invalid_host"

        # Validate port
        port = user_input.get(CONF_PORT)
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors[CONF_PORT] = "invalid_port"

        # Validate slave_id
        slave_id = user_input.get(CONF_SLAVE_ID)
        if not isinstance(slave_id, int) or slave_id < 0 or slave_id > 247:
            errors[CONF_SLAVE_ID] = "invalid_slave_id"

        return errors
