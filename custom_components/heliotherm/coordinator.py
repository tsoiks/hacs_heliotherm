"""Data update coordinator for the Heliotherm heat pump."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from .const import (
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .heliotherm_modbus import HeliothermHeatPump

_LOGGER = logging.getLogger(__name__)


class HeliothermCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll the heat pump and hand the report to the entities."""

    config_entry: HeliothermConfigEntry
    device: HeliothermHeatPump

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HeliothermConfigEntry,
        device: HeliothermHeatPump,
    ) -> None:
        """Initialize the coordinator from the entry's scan interval."""
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.device = device

    @property
    def device_id(self) -> str:
        """The stable identifier for the physical heat pump."""
        data = self.config_entry.data
        return f"{data[CONF_HOST]}_{data[CONF_PORT]}_{data[CONF_UNIT_ID]}"

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Describe the heat pump for the device registry."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.config_entry.title,
        )

    async def _async_update_data(self) -> UpdateReport:
        """Poll the heat pump, keeping the last report's failures visible."""
        try:
            report = await self.device.async_update()
        except (ModbusError, HomeAssistantError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err)},
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        for name, cause in report.failed.items():
            _LOGGER.warning(
                "%s: component %s failed to refresh and kept its previous"
                " values: %s",
                self.name,
                name,
                cause,
            )
        return report


type HeliothermConfigEntry = ConfigEntry[HeliothermCoordinator]
