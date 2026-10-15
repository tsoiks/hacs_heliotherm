"""Read Heliotherm heat pumps over Modbus, as typed Python objects.

This is a small, Home Assistant-agnostic device library built on the
``modbus_connection`` device-modelling framework. It owns no connection and
no I/O policy: the caller hands it a ``ModbusUnit`` and drives the polling.

Only the read map is modelled; see :mod:`heliotherm_modbus.components` for
where every register comes from and what is deliberately left out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection.model import Device, UpdateReport

from .components import (
    DigitalStates,
    EnergyCounters,
    Measurements,
    OperatingHours,
    Pressures,
    Temperatures,
)

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

__all__ = ["HeliothermHeatPump", "READ_COMPONENTS"]

READ_COMPONENTS = (
    "temperatures",
    "pressures",
    "digital_states",
    "measurements",
    "operating_hours",
    "energy_counters",
)


class HeliothermHeatPump(Device):
    """A Heliotherm heat pump behind its Remote Control Gateway (RCG).

    Use :meth:`async_update` to poll every readable sub-system. The
    returned :class:`~modbus_connection.model.UpdateReport` names the
    components that refreshed and the ones that failed and kept their
    previous values.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        """Initialize the sub-systems on the given unit handle."""
        super().__init__(unit)
        self.temperatures = Temperatures(unit)
        self.pressures = Pressures(unit)
        self.digital_states = DigitalStates(unit)
        self.measurements = Measurements(unit)
        self.operating_hours = OperatingHours(unit)
        self.energy_counters = EnergyCounters(unit)

    async def async_update(self) -> UpdateReport:
        """Poll every readable sub-system and report what happened."""
        return await self.async_poll(READ_COMPONENTS)
