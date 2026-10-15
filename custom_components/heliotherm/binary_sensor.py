"""Support for Heliotherm heat pump binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HeliothermConfigEntry
from .entity import HeliothermEntity, HeliothermEntityDescription
from .heliotherm_modbus import HeliothermHeatPump

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HeliothermBinarySensorEntityDescription(
    HeliothermEntityDescription, BinarySensorEntityDescription
):
    """Describe a binary sensor reading an on/off state of the heat pump."""

    value_fn: Callable[[HeliothermHeatPump], bool | None]
    """Read the state from the polled device object."""


BINARY_SENSOR_DESCRIPTIONS: tuple[
    HeliothermBinarySensorEntityDescription, ...
] = (
    HeliothermBinarySensorEntityDescription(
        key="heating_circuit_pump",
        translation_key="heating_circuit_pump",
        component="digital_states",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.digital_states.heating_circuit_pump,
    ),
    HeliothermBinarySensorEntityDescription(
        key="buffer_charge_pump",
        translation_key="buffer_charge_pump",
        component="digital_states",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.digital_states.buffer_charge_pump,
    ),
    HeliothermBinarySensorEntityDescription(
        key="compressor",
        translation_key="compressor",
        component="digital_states",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.digital_states.compressor,
    ),
    HeliothermBinarySensorEntityDescription(
        key="fault",
        translation_key="fault",
        component="digital_states",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.digital_states.fault,
    ),
    HeliothermBinarySensorEntityDescription(
        key="four_way_valve",
        translation_key="four_way_valve",
        component="digital_states",
        # Per the documentation, on means defrost or reversal operation.
        value_fn=lambda d: d.digital_states.four_way_valve,
    ),
    HeliothermBinarySensorEntityDescription(
        key="source_pump_or_fan",
        translation_key="source_pump_or_fan",
        component="digital_states",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.digital_states.source_pump_or_fan,
    ),
    HeliothermBinarySensorEntityDescription(
        key="domestic_hot_water_priority",
        translation_key="domestic_hot_water_priority",
        component="digital_states",
        value_fn=lambda d: d.digital_states.domestic_hot_water_priority,
    ),
    HeliothermBinarySensorEntityDescription(
        key="passive_cooling_valve",
        translation_key="passive_cooling_valve",
        component="digital_states",
        value_fn=lambda d: d.digital_states.passive_cooling_valve,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors from the entry's coordinator."""
    coordinator = entry.runtime_data
    async_add_entities(
        HeliothermBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class HeliothermBinarySensor(HeliothermEntity, BinarySensorEntity):
    """A binary sensor reading a polled on/off state."""

    entity_description: HeliothermBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state the last poll read for this binary sensor."""
        return self.entity_description.value_fn(self.coordinator.device)
