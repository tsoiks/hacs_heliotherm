"""Fixtures: a seeded mock heat pump on the in-memory Modbus backend."""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from custom_components.heliotherm.heliotherm_modbus import HeliothermHeatPump

pytest_plugins = ("pytest_homeassistant_custom_component",)

HOST = "10.0.0.42"
UNIT_ID = 1

# Realistic input-register values for a heat pump in heating mode.
INPUT_REGISTERS: dict[int, int] = {
    10: 85,  # outside 8.5 °C
    11: 485,  # domestic hot water 48.5 °C
    12: 425,  # supply 42.5 °C
    13: 371,  # return 37.1 °C
    14: 402,  # buffer 40.2 °C
    15: 35,  # source inlet 3.5 °C
    16: -1000,  # source outlet: not installed (-100.0 °C marker)
    17: 210,  # suction gas 21.0 °C
    18: -52,  # evaporation -5.2 °C
    19: 612,  # condensation 61.2 °C
    20: 885,  # hot gas 88.5 °C
    21: 62,  # low pressure 6.2 bar
    22: 251,  # high pressure 25.1 bar
    23: 1,  # heating circuit pump on
    24: 0,  # buffer charge pump off
    25: 1,  # compressor on
    26: 0,  # no fault
    27: 0,  # four-way valve off
    28: 183,  # flow rate 18.3 l/min
    29: 450,  # compressor speed setpoint 450 permille
    30: 41,  # COP 4.1
    31: 112,  # fresh water 11.2 °C
    33: 84,  # outside delayed 8.4 °C
    34: 405,  # return setpoint 40.5 °C
    35: 380,  # MKR1 flow setpoint 38.0 °C
    36: -500,  # MKR2 flow setpoint: not installed
    37: 1,  # source pump on
    38: 0,  # no domestic hot water priority
    39: 0,  # passive cooling valve off
    40: 320,  # expansion valve 320 permille
    41: 20,  # demand: heating
    # 32-bit values, high word at the lower address (confirmed live):
    42: 0,
    43: 1500,  # hot water hours
    44: 0,
    45: 9000,  # heating hours
    60: 0,
    61: 1842,  # heating heat energy
    62: 0,
    63: 615,  # heating electric energy
    64: 0,
    65: 980,  # hot water heat energy
    66: 0,
    67: 310,  # hot water electric energy
    68: 0,
    69: 2871,  # total electric energy
    70: 0,
    71: 1500,  # electric power
    72: 0,
    73: 2822,  # total heat energy
    74: 0,
    75: 45,  # heat power: 4.5 kW
}


@pytest.fixture
def unit() -> MockModbusUnit:
    """A mock unit seeded like a heating heat pump."""
    connection = MockModbusConnection()
    unit = connection.for_unit(UNIT_ID)
    unit.input = dict(INPUT_REGISTERS)
    return unit


@pytest.fixture
def device(unit: MockModbusUnit) -> HeliothermHeatPump:
    """A heat pump object on the seeded mock unit."""
    return HeliothermHeatPump(unit)
