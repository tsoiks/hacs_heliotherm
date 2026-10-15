"""Support for Heliotherm heat pump sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HeliothermConfigEntry
from .entity import HeliothermEntity, HeliothermEntityDescription
from .heliotherm_modbus import HeliothermHeatPump
from .heliotherm_modbus.enums import CompressorDemand

PARALLEL_UPDATES = 0

_DEMAND_OPTIONS = [member.name.lower() for member in CompressorDemand]


@dataclass(frozen=True, kw_only=True)
class HeliothermSensorEntityDescription(
    HeliothermEntityDescription, SensorEntityDescription
):
    """Describe a sensor reading an attribute of the heat pump."""

    value_fn: Callable[[HeliothermHeatPump], StateType]
    """Read the sensor's value from the polled device object."""


def _temperature(
    key: str, component: str, value_fn: Callable[[HeliothermHeatPump], StateType]
) -> HeliothermSensorEntityDescription:
    """Describe a temperature sensor."""
    return HeliothermSensorEntityDescription(
        key=key,
        translation_key=key,
        component=component,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


def _energy(
    key: str, component: str, value_fn: Callable[[HeliothermHeatPump], StateType]
) -> HeliothermSensorEntityDescription:
    """Describe a lifetime energy counter."""
    return HeliothermSensorEntityDescription(
        key=key,
        translation_key=key,
        component=component,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=value_fn,
    )


SENSOR_DESCRIPTIONS: tuple[HeliothermSensorEntityDescription, ...] = (
    # The three v1 sensors.
    _temperature(
        "supply_temperature", "temperatures", lambda d: d.temperatures.supply
    ),
    HeliothermSensorEntityDescription(
        key="compressor_demand",
        translation_key="compressor_demand",
        component="measurements",
        device_class=SensorDeviceClass.ENUM,
        options=_DEMAND_OPTIONS,
        value_fn=lambda d: (
            d.measurements.demand.name.lower()
            if d.measurements.demand is not None
            else None
        ),
    ),
    HeliothermSensorEntityDescription(
        key="electric_power",
        translation_key="electric_power",
        component="energy_counters",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.energy_counters.electric_power,
    ),
    # The remaining temperature registers.
    _temperature(
        "outside_temperature", "temperatures", lambda d: d.temperatures.outside
    ),
    _temperature(
        "domestic_hot_water_temperature",
        "temperatures",
        lambda d: d.temperatures.domestic_hot_water,
    ),
    _temperature(
        "return_temperature", "temperatures", lambda d: d.temperatures.return_
    ),
    _temperature(
        "buffer_temperature", "temperatures", lambda d: d.temperatures.buffer
    ),
    _temperature(
        "source_inlet_temperature",
        "temperatures",
        lambda d: d.temperatures.source_inlet,
    ),
    _temperature(
        "source_outlet_temperature",
        "temperatures",
        lambda d: d.temperatures.source_outlet,
    ),
    _temperature(
        "suction_gas_temperature",
        "temperatures",
        lambda d: d.temperatures.suction_gas,
    ),
    _temperature(
        "evaporation_temperature",
        "temperatures",
        lambda d: d.temperatures.evaporation,
    ),
    _temperature(
        "condensation_temperature",
        "temperatures",
        lambda d: d.temperatures.condensation,
    ),
    _temperature(
        "hot_gas_temperature", "temperatures", lambda d: d.temperatures.hot_gas
    ),
    _temperature(
        "fresh_water_temperature",
        "measurements",
        lambda d: d.measurements.fresh_water,
    ),
    _temperature(
        "outside_temperature_delayed",
        "measurements",
        lambda d: d.measurements.outside_delayed,
    ),
    _temperature(
        "return_setpoint_temperature",
        "measurements",
        lambda d: d.measurements.return_setpoint,
    ),
    _temperature(
        "mkr1_flow_setpoint_temperature",
        "measurements",
        lambda d: d.measurements.mkr1_flow_setpoint,
    ),
    _temperature(
        "mkr2_flow_setpoint_temperature",
        "measurements",
        lambda d: d.measurements.mkr2_flow_setpoint,
    ),
    # Pressures.
    HeliothermSensorEntityDescription(
        key="low_pressure",
        translation_key="low_pressure",
        component="pressures",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.pressures.low,
    ),
    HeliothermSensorEntityDescription(
        key="high_pressure",
        translation_key="high_pressure",
        component="pressures",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.pressures.high,
    ),
    # Mixed measurements.
    HeliothermSensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        component="measurements",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.measurements.flow_rate,
    ),
    HeliothermSensorEntityDescription(
        key="compressor_speed_setpoint",
        translation_key="compressor_speed_setpoint",
        component="measurements",
        native_unit_of_measurement="‰",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.measurements.compressor_speed_setpoint,
    ),
    HeliothermSensorEntityDescription(
        key="coefficient_of_performance",
        translation_key="coefficient_of_performance",
        component="measurements",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.measurements.cop,
    ),
    HeliothermSensorEntityDescription(
        key="expansion_valve",
        translation_key="expansion_valve",
        component="measurements",
        native_unit_of_measurement="‰",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.measurements.expansion_valve,
    ),
    HeliothermSensorEntityDescription(
        key="heat_power",
        translation_key="heat_power",
        component="energy_counters",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.energy_counters.heat_power,
    ),
    # Operating hour counters.
    HeliothermSensorEntityDescription(
        key="domestic_hot_water_hours",
        translation_key="domestic_hot_water_hours",
        component="operating_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.operating_hours.domestic_hot_water_hours,
    ),
    HeliothermSensorEntityDescription(
        key="heating_hours",
        translation_key="heating_hours",
        component="operating_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.operating_hours.heating_hours,
    ),
    # Lifetime energy counters.
    _energy(
        "heating_heat_energy",
        "energy_counters",
        lambda d: d.energy_counters.heating_heat,
    ),
    _energy(
        "heating_electric_energy",
        "energy_counters",
        lambda d: d.energy_counters.heating_electric,
    ),
    _energy(
        "domestic_hot_water_heat_energy",
        "energy_counters",
        lambda d: d.energy_counters.domestic_hot_water_heat,
    ),
    _energy(
        "domestic_hot_water_electric_energy",
        "energy_counters",
        lambda d: d.energy_counters.domestic_hot_water_electric,
    ),
    _energy(
        "total_electric_energy",
        "energy_counters",
        lambda d: d.energy_counters.electric_total,
    ),
    _energy(
        "total_heat_energy",
        "energy_counters",
        lambda d: d.energy_counters.heat_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors from the entry's coordinator."""
    coordinator = entry.runtime_data
    async_add_entities(
        HeliothermSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class HeliothermSensor(HeliothermEntity, SensorEntity):
    """A sensor reading a polled heat pump attribute."""

    entity_description: HeliothermSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value the last poll read for this sensor."""
        return self.entity_description.value_fn(self.coordinator.device)
