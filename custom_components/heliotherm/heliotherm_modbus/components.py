"""Typed components of the Heliotherm Modbus register map.

Every register, data type, scale and unit below comes from the official
Heliotherm Modbus documentation (``Heliotherm.RCG.Modbusregister.pdf``, STAND
31.10.2019, cross-checked against ``Modbus-Doku_DE.pdf`` for the RCG2+), and
was additionally validated against the field-tested community integration
mbuchber/ha_heliotherm. Do not add registers here from unverified sources.

The read map lives in the input register space (function code 04) and is
readable with a block read per component. Write registers (100+) are
deliberately not modelled yet; they belong to a future, explicit write
mode. The official documentation warns that writing wrong data types can
damage the controller, so write support must be designed carefully.

``nan`` marks raw patterns that decode to impossible values the device sends
for sensors that are not installed. Two such markers were observed on a live
pump (2026-10-15): -50.0 degrees Celsius for a missing temperature (the
community had found this one) and -100.0 degrees Celsius for another
(the RCG X documentation does not document either).

The 32-bit values (registers 42-45 and 60-75) span two registers each with
the high word at the lower address (``word_order="big"``), confirmed by a
live read on 2026-10-15: the counter registers answered (0, 670) for a
plausible 670 kWh, not 43 million.
"""

from __future__ import annotations

from modbus_connection.model import Component, NumberField, enum, gauge, uint32

from .enums import CompressorDemand

__all__ = [
    "DigitalStates",
    "EnergyCounters",
    "Measurements",
    "OperatingHours",
    "Pressures",
    "Temperatures",
]

# Raw patterns of the missing-value markers, masked like the decoder sees
# them: a signed -500 (=-50.0 after scaling) and a signed -1000 (=-100.0
# after scaling). Both are impossible values for any field that carries
# them, whatever its unit.
_MISSING_TEMPERATURES = (-500 & 0xFFFF, -1000 & 0xFFFF)


def _on_when_nonzero(value: int) -> bool:
    """Decode the device's on/off convention: any nonzero value means on."""
    return value != 0


def on_off(address: int) -> NumberField[bool]:
    """Create an input register field decoding nonzero values to on."""
    return NumberField(address, signed=False, convert=_on_when_nonzero)


class Temperatures(Component):
    """The temperature registers 10-20, in 0.1 degrees Celsius."""

    register_space = "input"

    outside = gauge(10, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Outside temperature."""
    domestic_hot_water = gauge(11, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Domestic hot water temperature."""
    supply = gauge(12, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Supply (flow) temperature."""
    return_ = gauge(13, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Return temperature."""
    buffer = gauge(14, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Buffer tank temperature."""
    source_inlet = gauge(15, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Source (energy quell) inlet temperature."""
    source_outlet = gauge(16, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Source (energy quell) outlet temperature."""
    suction_gas = gauge(17, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Suction gas temperature."""
    evaporation = gauge(18, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Evaporation temperature."""
    condensation = gauge(19, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Condensation temperature."""
    hot_gas = gauge(20, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Hot gas temperature."""


class Pressures(Component):
    """The pressure registers 21-22, in 0.1 bar."""

    register_space = "input"

    low = gauge(21, 0.1, unit="bar", nan=_MISSING_TEMPERATURES)
    """Low pressure."""
    high = gauge(22, 0.1, unit="bar", nan=_MISSING_TEMPERATURES)
    """High pressure."""


class DigitalStates(Component):
    """The on/off states in registers 23-27 and 37-39.

    Per the official documentation these registers are on when nonzero.
    """

    register_space = "input"

    heating_circuit_pump = on_off(23)
    """Heating circuit pump running."""
    buffer_charge_pump = on_off(24)
    """Buffer charge pump running."""
    compressor = on_off(25)
    """Heat pump / compressor running."""
    fault = on_off(26)
    """A fault is active."""
    four_way_valve = on_off(27)
    """Four-way valve in defrost / reversal mode."""
    source_pump_or_fan = on_off(37)
    """Source pump or fan running."""
    domestic_hot_water_priority = on_off(38)
    """Domestic hot water priority active."""
    passive_cooling_valve = on_off(39)
    """Passive cooling diverter valve switched on."""


class Measurements(Component):
    """The mixed measurements in registers 28-41.

    Register 32 (EVU release/lockout) is deliberately not modelled: the
    two official documents describe its semantics contradictorily, so it
    stays out until a live read resolves them.
    """

    register_space = "input"

    flow_rate = gauge(28, 0.1, unit="l/min", nan=_MISSING_TEMPERATURES)
    """Flow rate. The newer document says 0.1 l/min, the older 0.1 l/h."""
    compressor_speed_setpoint = gauge(29, 1, unit="‰")
    """Compressor speed setpoint, in per mille."""
    cop = gauge(30, 0.1, unit=None, nan=_MISSING_TEMPERATURES)
    """Coefficient of performance."""
    fresh_water = gauge(31, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Fresh water temperature."""
    outside_delayed = gauge(33, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Outside temperature, delayed."""
    return_setpoint = gauge(34, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Return / storage setpoint (the device's own, not a write register)."""
    mkr1_flow_setpoint = gauge(35, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Heating circuit 1 (MKR1) flow setpoint."""
    mkr2_flow_setpoint = gauge(36, 0.1, unit="°C", nan=_MISSING_TEMPERATURES)
    """Heating circuit 2 (MKR2) flow setpoint."""
    expansion_valve = gauge(40, 1, unit="‰")
    """Expansion valve position, in per mille."""
    demand = enum(41, CompressorDemand, signed=False)
    """The heat pump's current compressor demand."""


class OperatingHours(Component):
    """The operating hour counters in registers 42-45 (RCG X and newer)."""

    register_space = "input"

    domestic_hot_water_hours = uint32(42, unit="h", word_order="big")
    """Hours run in domestic hot water mode."""
    heating_hours = uint32(44, unit="h", word_order="big")
    """Hours run in heating mode."""


class EnergyCounters(Component):
    """The energy counters in registers 60-75."""

    register_space = "input"

    heating_heat = uint32(60, unit="kWh", word_order="big")
    """Thermal energy produced while heating."""
    heating_electric = uint32(62, unit="kWh", word_order="big")
    """Electrical energy consumed while heating."""
    domestic_hot_water_heat = uint32(64, unit="kWh", word_order="big")
    """Thermal energy produced while making hot water."""
    domestic_hot_water_electric = uint32(66, unit="kWh", word_order="big")
    """Electrical energy consumed while making hot water."""
    electric_total = uint32(68, unit="kWh", word_order="big")
    """Total electrical energy consumed."""
    electric_power = uint32(70, unit="W", word_order="big")
    """Current electrical power uptake."""
    heat_total = uint32(72, unit="kWh", word_order="big")
    """Total thermal energy produced."""
    heat_power = uint32(74, scale=0.1, unit="kW", word_order="big")
    """Current thermal power output."""
