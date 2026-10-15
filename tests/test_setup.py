"""Setting a heat pump up exposes its three v1 sensors."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heliotherm.const import CONF_UNIT_ID, DOMAIN

from .conftest import HOST, INPUT_REGISTERS, UNIT_ID


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A configured heat pump entry."""
    return MockConfigEntry(
        title=f"Heliotherm ({HOST})",
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: 502, CONF_UNIT_ID: UNIT_ID},
        unique_id=f"{HOST}_502_{UNIT_ID}",
    )


@pytest.fixture
def mock_unit() -> MockModbusUnit:
    """A seeded mock unit handed out instead of a real connection."""
    connection = MockModbusConnection()
    unit = connection.for_unit(UNIT_ID)
    unit.input = dict(INPUT_REGISTERS)
    return unit


@contextmanager
def _patched_unit(unit: MockModbusUnit) -> Any:
    """Hand the mock unit to the integration instead of a real one."""
    with patch(
        "custom_components.heliotherm.async_get_unit", return_value=unit
    ):
        yield


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the entry up; keep the caller's unit patch active."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """The entity id of one of the entry's sensors."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_{key}"
    )
    assert entity_id is not None, key
    return entity_id


async def test_setup_creates_three_sensors(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    enable_custom_integrations: None,
) -> None:
    """Setup exposes the three v1 sensors with their polled values."""
    with _patched_unit(mock_unit):
        await _setup(hass, entry)
    states = {
        key: hass.states.get(_entity_id(hass, entry, key))
        for key in ("supply_temperature", "compressor_demand", "electric_power")
    }
    assert states["supply_temperature"].state == "42.5"
    assert states["compressor_demand"].state == "heating"
    assert states["electric_power"].state == "1500"
    # The friendly name comes from the translation and the device name.
    assert (
        states["supply_temperature"].attributes["friendly_name"]
        == "Heliotherm (10.0.0.42) Supply temperature"
    )


async def test_setup_exposes_the_whole_input_register_map(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    enable_custom_integrations: None,
) -> None:
    """Every input-register value except register 32 has an entity."""
    from custom_components.heliotherm.binary_sensor import (
        BINARY_SENSOR_DESCRIPTIONS,
    )
    from custom_components.heliotherm.sensor import SENSOR_DESCRIPTIONS

    with _patched_unit(mock_unit):
        await _setup(hass, entry)
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    assert len(SENSOR_DESCRIPTIONS) == 33
    assert len(BINARY_SENSOR_DESCRIPTIONS) == 8

    def state(key: str) -> str:
        return hass.states.get(_entity_id(hass, entry, key)).state

    # Spot checks across every component of the register map.
    assert state("outside_temperature") == "8.5"
    assert state("domestic_hot_water_temperature") == "48.5"
    assert state("return_temperature") == "37.1"
    assert state("buffer_temperature") == "40.2"
    assert state("source_inlet_temperature") == "3.5"
    # The source outlet is not installed: -100.0 marker -> unknown.
    assert state("source_outlet_temperature") == "unknown"
    assert state("suction_gas_temperature") == "21.0"
    assert state("evaporation_temperature") == "-5.2"
    assert state("condensation_temperature") == "61.2"
    assert state("hot_gas_temperature") == "88.5"
    assert state("fresh_water_temperature") == "11.2"
    assert state("outside_temperature_delayed") == "8.4"
    assert state("return_setpoint_temperature") == "40.5"
    # MKR2 flow setpoint not installed: -50.0 marker -> unknown.
    assert state("mkr2_flow_setpoint_temperature") == "unknown"
    assert state("low_pressure") == "6.2"
    assert state("high_pressure") == "25.1"
    assert state("flow_rate") == "18.3"
    assert state("compressor_speed_setpoint") == "450"
    assert state("coefficient_of_performance") == "4.1"
    assert state("expansion_valve") == "320"
    assert state("heat_power") == "4.5"
    assert state("domestic_hot_water_hours") == "1500"
    assert state("heating_hours") == "9000"
    assert state("heating_heat_energy") == "1842"
    assert state("heating_electric_energy") == "615"
    assert state("domestic_hot_water_heat_energy") == "980"
    assert state("domestic_hot_water_electric_energy") == "310"
    assert state("total_electric_energy") == "2871"
    assert state("total_heat_energy") == "2822"

    def binary_state(key: str) -> str:
        entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.unique_id}_{key}"
        )
        assert entity_id is not None, key
        return hass.states.get(entity_id).state

    assert binary_state("heating_circuit_pump") == "on"
    assert binary_state("buffer_charge_pump") == "off"
    assert binary_state("compressor") == "on"
    assert binary_state("fault") == "off"
    assert binary_state("four_way_valve") == "off"
    assert binary_state("source_pump_or_fan") == "on"
    assert binary_state("domestic_hot_water_priority") == "off"
    assert binary_state("passive_cooling_valve") == "off"


async def test_failed_component_marks_sensors_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    enable_custom_integrations: None,
) -> None:
    """A block that stops answering marks its sensors unavailable."""
    from modbus_connection import ModbusTimeoutError

    with _patched_unit(mock_unit):
        await _setup(hass, entry)
    power_id = _entity_id(hass, entry, "electric_power")
    supply_id = _entity_id(hass, entry, "supply_temperature")
    assert hass.states.get(power_id).state == "1500"
    mock_unit.fail_read(
        70, ModbusTimeoutError("no answer"), register_type="input"
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    # The power sensor goes unavailable; the temperature block is fine.
    assert hass.states.get(power_id).state == STATE_UNAVAILABLE
    assert hass.states.get(supply_id).state == "42.5"


async def test_unload(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    enable_custom_integrations: None,
) -> None:
    """Unloading takes the entry down."""
    with _patched_unit(mock_unit):
        await _setup(hass, entry)
    supply_id = _entity_id(hass, entry, "supply_temperature")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(supply_id)
    assert state is None or state.state == STATE_UNAVAILABLE


async def test_options_flow_sets_scan_interval(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
    enable_custom_integrations: None,
) -> None:
    """The options flow stores the scan interval and reloads the entry."""
    with _patched_unit(mock_unit):
        await _setup(hass, entry)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 60}
        )
        await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert entry.options == {"scan_interval": 60}
        assert entry.state is ConfigEntryState.LOADED
