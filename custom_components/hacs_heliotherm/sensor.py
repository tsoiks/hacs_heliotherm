"""
Sensor platform for Heliotherm integration.

This module creates Home Assistant sensor entities from SENSOR_DESCRIPTORS.
Each descriptor automatically becomes a sensor entity that:
1. Reads from the coordinator's cached data
2. Updates when coordinator refreshes
3. Applies scaling factors
4. Sets proper device class and units

Architecture: See docs/adr/004-entity-design.md
Descriptor pattern: See docs/COMPARATIVE_ANALYSIS.md
"""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_DESCRIPTORS
from .coordinator import HeliothermModbusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up sensor platform from config entry.
    
    PATTERN: Automatic entity creation from SENSOR_DESCRIPTORS.
    
    This function:
    1. Gets coordinator from hass.data
    2. Iterates SENSOR_DESCRIPTORS
    3. Creates a HeliothermSensor for each descriptor
    4. Registers all entities with Home Assistant
    
    Home Assistant then:
    - Manages entity lifecycle (adding, removing, state tracking)
    - Notifies sensor of coordinator updates
    - Handles UI representation
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry for this integration instance
        async_add_entities: Callback to register entities
    """
    
    # Get coordinator from hass.data
    # Coordinator was created and stored in __init__.py
    try:
        coordinator: HeliothermModbusCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ]["coordinator"]
    except KeyError as err:
        _LOGGER.error(
            "Coordinator not found for config entry %s: %s",
            config_entry.entry_id,
            err,
        )
        return
    
    try:
        # PATTERN: Create entity for each descriptor
        # This is the "entity-per-descriptor" pattern
        entities = [
            HeliothermSensor(
                coordinator=coordinator,
                config_entry=config_entry,
                key=key,  # "supply_temperature", "return_temperature", etc.
                descriptor=descriptor,
            )
            for key, descriptor in SENSOR_DESCRIPTORS.items()
        ]
        
        # Register all entities with Home Assistant
        # Home Assistant now manages their lifecycle
        async_add_entities(entities)
        
        _LOGGER.debug(
            "Created %d sensor entities from SENSOR_DESCRIPTORS",
            len(entities),
        )
    except Exception as err:
        _LOGGER.error(
            "Failed to set up sensor platform: %s",
            err,
        )
        return


class HeliothermSensor(CoordinatorEntity, SensorEntity):
    """
    Single Heliotherm sensor entity.
    
    PATTERN: One entity per SENSOR_DESCRIPTOR.
    Inherits from CoordinatorEntity to auto-update when coordinator updates.
    
    Responsibilities:
    1. Read value from coordinator.data using key
    2. Apply scaling factor from descriptor
    3. Display in Home Assistant
    4. Implement native_value property for state management
    
    Architecture: See ADR-004: Entity Design
    """
    
    def __init__(
        self,
        coordinator: HeliothermModbusCoordinator,
        config_entry: ConfigEntry,
        key: str,
        descriptor,
    ):
        """
        Initialize sensor.
        
        Args:
            coordinator: The data coordinator
            config_entry: ConfigEntry
            key: Descriptor key (e.g., "supply_temperature")
            descriptor: SensorDescriptor with register, scale, units, etc.
        """
        
        # Initialize parent (CoordinatorEntity)
        # This handles automatic updates from coordinator
        super().__init__(coordinator)
        
        self.config_entry = config_entry
        self.key = key
        self.descriptor = descriptor
        
        # Build unique entity ID
        # Format: "sensor.heliotherm_{entry_id}_{key}"
        # Example: "sensor.heliotherm_abcd1234_supply_temperature"
        self._attr_unique_id = f"heliotherm_{config_entry.entry_id}_{key}"
        
        # Set entity name
        # Example: "Heliotherm Supply Temperature"
        self._attr_name = f"Heliotherm {descriptor.name}"
        
        # Set units from descriptor
        # Example: "°C" for temperature
        self._attr_native_unit_of_measurement = descriptor.unit
        
        # Set device class for Home Assistant to understand entity type
        # Example: "temperature" for temp sensors
        # Enables Home Assistant UI features (graphs, formatting, etc.)
        if descriptor.device_class:
            self._attr_device_class = descriptor.device_class
        
        # Set icon (override if needed)
        if descriptor.icon:
            self._attr_icon = descriptor.icon
        
        # Configure state class for statistics
        # MEASUREMENT = read-only value (no accumulation)
        # Total, total_increasing for counters/accumulators
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """
        Return the sensor's current value.
        
        PATTERN: Read from coordinator.data and apply scaling.
        
        Coordinator provides cached data dict like:
        {
            "supply_temperature": 22.5,
            "return_temperature": 20.1,
            ...
        }
        
        We read the value for this sensor's key, apply the scale factor,
        and return the result.
        
        Returns:
            Scaled sensor value, or None if unavailable
            
        Example:
            Raw data from coordinator: {"supply_temperature": 225}
            Descriptor scale: 0.1
            Returned value: 225 * 0.1 = 22.5°C
        """
        
        # Get data from coordinator
        # coordinator.data is the last successfully fetched dict
        # Returns empty dict if no data yet
        data = self.coordinator.data
        
        if not data:
            return None
        
        # Get raw value for this sensor
        raw_value = data.get(self.key)
        
        if raw_value is None:
            return None
        
        # Apply scaling factor
        # Example: raw=225, scale=0.1 → result=22.5
        scaled_value = raw_value * self.descriptor.scale
        
        return scaled_value

    @property
    def available(self) -> bool:
        """
        Return True if entity is available.
        
        PATTERN: Check if coordinator has recent successful data.
        Entities are unavailable if:
        1. Coordinator has never fetched data yet
        2. Last update failed
        3. Update is stale (time-based or last_update_success flag)
        
        Home Assistant uses this to:
        - Show "unavailable" state in UI
        - Not use stale data in automations
        - Show error indicators
        
        Returns:
            True if coordinator has valid data, False otherwise
        """
        
        # Check if we have any data from coordinator
        has_data = bool(self.coordinator.data)
        
        # Check if last update was successful
        # (DataUpdateCoordinator sets this automatically)
        last_update_success = self.coordinator.last_update_success
        
        return has_data and last_update_success

    @property
    def should_poll(self) -> bool:
        """
        Return False - this entity gets updates from coordinator.
        
        PATTERN: All entities listen to coordinator for updates.
        No per-entity polling needed (efficiency).
        
        When coordinator fetches new data:
        1. Coordinator calls async_update_data()
        2. Coordinator notifies all entities
        3. Entity updates its state automatically
        4. Home Assistant pushes to frontend
        
        Returns:
            False (rely on coordinator updates)
        """
        return False

    @property
    def device_info(self) -> dict[str, Any]:
        """
        Return device info for grouping in Home Assistant.
        
        Home Assistant uses this to:
        1. Group entities on device page
        2. Show device-level info
        3. Enable device-level automations
        
        Returns:
            Dictionary with device identification
        """
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_id)},
            "name": "Heliotherm Heat Pump",
            "manufacturer": "Heliotherm",
            "model": self.coordinator.device_model,
        }

    # ========================================================================
    # FUTURE: Custom sensors for computed values
    # ========================================================================
    # Example: You might want sensors that don't map directly to Modbus registers
    # For example, a "Delta T" sensor that computes (supply_temp - return_temp)
    #
    # To do this:
    # 1. Don't include in SENSOR_DESCRIPTIONS
    # 2. Create a custom class inheriting from HeliotermSensor
    # 3. Override native_value to compute the value
    #
    # class HeliotermDeltaTSensor(HeliotermSensor):
    #     @property
    #     def native_value(self) -> float | None:
    #         supply = self.coordinator.data.get("supply_temperature")
    #         return_temp = self.coordinator.data.get("return_temperature")
    #         if supply and return_temp:
    #             return supply - return_temp
    #         return None
