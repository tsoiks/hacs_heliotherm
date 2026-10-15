"""The register map, decoded over the mock backend."""

from __future__ import annotations

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
from modbus_connection.model import UpdateReport

from custom_components.heliotherm.heliotherm_modbus import HeliothermHeatPump
from custom_components.heliotherm.heliotherm_modbus.enums import CompressorDemand


async def test_v1_registers_decode(device: HeliothermHeatPump) -> None:
    """The three v1 registers read their documented values."""
    await device.async_update()
    assert device.temperatures.supply == 42.5
    assert device.measurements.demand is CompressorDemand.HEATING
    assert device.energy_counters.electric_power == 1500


async def test_temperatures_decode(device: HeliothermHeatPump) -> None:
    """Every temperature register decodes with its scale."""
    await device.temperatures.async_update()
    temperatures = device.temperatures
    assert temperatures.outside == 8.5
    assert temperatures.domestic_hot_water == 48.5
    assert temperatures.supply == 42.5
    assert temperatures.return_ == 37.1
    assert temperatures.buffer == 40.2
    assert temperatures.source_inlet == 3.5
    assert temperatures.suction_gas == 21.0
    assert temperatures.evaporation == -5.2
    assert temperatures.condensation == 61.2
    assert temperatures.hot_gas == 88.5


async def test_missing_sensor_decodes_to_none(
    device: HeliothermHeatPump,
) -> None:
    """The -50.0 and -100.0 markers of an uninstalled sensor decode to None."""
    unit = device.modbus_unit
    await device.temperatures.async_update()
    await device.measurements.async_update()
    # -100.0 °C marker, observed live on register 16.
    assert device.temperatures.source_outlet is None
    # -50.0 °C marker on register 36.
    assert device.measurements.mkr2_flow_setpoint is None
    # The -50.0 marker on any scaled field, wherever the device sends it.
    unit.input[31] = -500
    await device.measurements.async_update()
    assert device.measurements.fresh_water is None


async def test_digital_states_decode(device: HeliothermHeatPump) -> None:
    """On/off registers decode nonzero values as on."""
    await device.digital_states.async_update()
    states = device.digital_states
    assert states.heating_circuit_pump is True
    assert states.buffer_charge_pump is False
    assert states.compressor is True
    assert states.fault is False
    assert states.four_way_valve is False
    assert states.source_pump_or_fan is True
    assert states.domestic_hot_water_priority is False
    assert states.passive_cooling_valve is False


async def test_measurements_decode(device: HeliothermHeatPump) -> None:
    """The mixed measurement registers decode with their scales."""
    await device.measurements.async_update()
    measurements = device.measurements
    assert measurements.flow_rate == 18.3
    assert measurements.compressor_speed_setpoint == 450
    assert measurements.cop == 4.1
    assert measurements.fresh_water == 11.2
    assert measurements.outside_delayed == 8.4
    assert measurements.return_setpoint == 40.5
    assert measurements.mkr1_flow_setpoint == 38.0
    assert measurements.expansion_valve == 320


async def test_demand_codes(device: HeliothermHeatPump) -> None:
    """The demand register maps its documented codes, and only those."""
    unit = device.modbus_unit
    for code, expected in (
        (0, CompressorDemand.NONE),
        (10, CompressorDemand.COOLING),
        (20, CompressorDemand.HEATING),
        (30, CompressorDemand.DOMESTIC_HOT_WATER),
        (40, CompressorDemand.EXTERNAL),
    ):
        unit.input[41] = code
        await device.measurements.async_update()
        assert device.measurements.demand is expected, code
    # An undocumented code decodes to None instead of inventing a value.
    unit.input[41] = 50
    await device.measurements.async_update()
    assert device.measurements.demand is None


async def test_counters_decode_high_word_first(
    device: HeliothermHeatPump,
) -> None:
    """The 32-bit counters read the low register as the high word."""
    unit = device.modbus_unit
    unit.input.update({70: 0x0100, 71: 0x1234})
    await device.energy_counters.async_update()
    # big word order: register 70 is the high word, 71 the low word.
    assert device.energy_counters.electric_power == 0x0100_1234


async def test_operating_hours_decode(device: HeliothermHeatPump) -> None:
    """The hour counters decode as 32-bit values."""
    await device.operating_hours.async_update()
    assert device.operating_hours.domestic_hot_water_hours == 1500
    assert device.operating_hours.heating_hours == 9000


async def test_energy_counters_decode(device: HeliothermHeatPump) -> None:
    """The energy counters decode with their scales."""
    await device.energy_counters.async_update()
    counters = device.energy_counters
    assert counters.heating_heat == 1842
    assert counters.heating_electric == 615
    assert counters.domestic_hot_water_heat == 980
    assert counters.domestic_hot_water_electric == 310
    assert counters.electric_total == 2871
    assert counters.electric_power == 1500
    assert counters.heat_total == 2822
    assert counters.heat_power == 4.5


async def test_pressures_decode(device: HeliothermHeatPump) -> None:
    """The pressure registers decode in bar."""
    await device.pressures.async_update()
    assert device.pressures.low == 6.2
    assert device.pressures.high == 25.1


async def test_update_polls_every_component(device: HeliothermHeatPump) -> None:
    """A poll updates every component and reports all of them."""
    report = await device.async_update()
    assert report.complete
    assert report.updated == {
        "temperatures",
        "pressures",
        "digital_states",
        "measurements",
        "operating_hours",
        "energy_counters",
    }


async def test_failed_component_keeps_values_and_is_reported(
    unit: MockModbusUnit, device: HeliothermHeatPump
) -> None:
    """A failing block keeps its previous values and lands in the report."""
    await device.async_update()
    unit.fail_read(60, ModbusTimeoutError("no answer"), register_type="input")
    report = await device.async_update()
    assert isinstance(report, UpdateReport)
    assert report.failed.keys() == {"energy_counters"}
    assert report.updated == {
        "temperatures",
        "pressures",
        "digital_states",
        "measurements",
        "operating_hours",
    }
    # The failed counter block keeps its previous values.
    assert device.energy_counters.electric_power == 1500


async def test_no_writable_fields() -> None:
    """The read-only map must not declare any writable field."""
    from custom_components.heliotherm.heliotherm_modbus.components import (
        DigitalStates,
        EnergyCounters,
        Measurements,
        OperatingHours,
        Pressures,
        Temperatures,
    )

    for component in (
        Temperatures,
        Pressures,
        DigitalStates,
        Measurements,
        OperatingHours,
        EnergyCounters,
    ):
        for field in component.declared_fields.values():
            assert not field.writable, (component.__name__, field.name)


async def test_unknown_registers_are_not_read(device: HeliothermHeatPump) -> None:
    """Register 32 stays unmodelled until its semantics are resolved."""
    from custom_components.heliotherm.heliotherm_modbus import (
        READ_COMPONENTS,
    )

    for name in READ_COMPONENTS:
        component = getattr(device, name)
        for field in component.declared_fields.values():
            assert field.address != 32, (name, field.name)
            assert field.address + field.count - 1 < 32 or field.address > 32, (
                name,
                field.name,
            )
