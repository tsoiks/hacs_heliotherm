"""
Number platform for Heliotherm integration.

This module creates Home Assistant number entities from NUMBER_DESCRIPTORS.
Each descriptor automatically becomes a number entity that:
1. Reads the current value from the coordinator's cached data
2. Updates when coordinator refreshes
3. Applies scaling factors
4. Allows user to set new values via Home Assistant UI
5. Writes new values back to device via coordinator

Architecture: See docs/adr/004-entity-design.md
Descriptor pattern: See docs/COMPARATIVE_ANALYSIS.md
"""

import logging
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUMBER_DESCRIPTORS
from .coordinator import HeliothermModbusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up number platform from config entry.
    
    PATTERN: Automatic entity creation from NUMBER_DESCRIPTORS.
    Only creates writable numbers if NOT in read-only mode.
    
    This function:
    1. Gets coordinator from hass.data
    2. Checks if read-only mode is enabled
    3. Iterates NUMBER_DESCRIPTORS
    4. Creates a HeliothermNumber for each descriptor
    5. Registers all entities with Home Assistant
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry for this integration instance
        async_add_entities: Callback to register entities
    """
    
    # Get coordinator from hass.data
    coordinator: HeliothermModbusCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    
    # PATTERN: Only set up writable numbers if write mode is enabled
    # See ADR-002: Read-Only vs. Write Mode
    if coordinator.read_only:
        _LOGGER.info(
            "Heliotherm in read-only mode - number entities disabled"
        )
        return
    
    try:
        # PATTERN: Create entity for each descriptor
        entities = [
            HeliothermNumber(
                coordinator=coordinator,
                config_entry=config_entry,
                key=key,
                descriptor=descriptor,
            )
            for key, descriptor in NUMBER_DESCRIPTORS.items()
        ]
        
        async_add_entities(entities)
        
        _LOGGER.debug(
            "Created %d number entities from NUMBER_DESCRIPTORS",
            len(entities),
        )
    except Exception as err:
        _LOGGER.error(
            "Failed to set up number platform: %s",
            err,
        )
        return


class HeliothermNumber(CoordinatorEntity, NumberEntity):
    """
    Single Heliotherm number entity (setpoint/parameter).
    
    PATTERN: One entity per NUMBER_DESCRIPTOR.
    Inherits from CoordinatorEntity to auto-update when coordinator updates.
    
    Responsibilities:
    1. Read current value from coordinator.data using key
    2. Display in Home Assistant number UI
    3. Allow user to set new value
    4. Write new value back to device via coordinator
    5. Apply scaling factors in both directions
    
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
        Initialize number entity.
        
        Args:
            coordinator: The data coordinator
            config_entry: ConfigEntry
            key: Descriptor key (e.g., "target_supply_temperature")
            descriptor: NumberDescriptor with register, min/max, scale, units, etc.
        """
        
        # Initialize parent (CoordinatorEntity)
        # This handles automatic updates from coordinator
        super().__init__(coordinator)
        
        self.config_entry = config_entry
        self.key = key
        self.descriptor = descriptor
        
        # Build unique entity ID
        # Format: "number.heliotherm_{entry_id}_{key}"
        self._attr_unique_id = f"heliotherm_{config_entry.entry_id}_{key}"
        
        # Set entity name
        self._attr_name = f"Heliotherm {descriptor.name}"
        
        # Set units from descriptor
        self._attr_native_unit_of_measurement = descriptor.unit
        
        # Set min/max values (already scaled)
        self._attr_native_min_value = descriptor.min_value
        self._attr_native_max_value = descriptor.max_value
        
        # Set step size for UI slider
        self._attr_native_step = descriptor.step
        
        # Set mode: SLIDER for continuous, BOX for text input
        self._attr_mode = NumberMode.SLIDER
        
        # Set icon if provided
        if descriptor.icon:
            self._attr_icon = descriptor.icon

    @property
    def native_value(self) -> float | None:
        """
        Return the number's current value.
        
        PATTERN: Read from coordinator.data and apply scaling.
        
        Coordinator provides cached data dict like:
        {
            "target_supply_temperature": 45.0,
            "target_room_temperature": 21.5,
            ...
        }
        
        Returns:
            Scaled number value, or None if unavailable
        """
        
        # Get data from coordinator
        data = self.coordinator.data
        
        if not data:
            _LOGGER.debug("No data available from coordinator")
            return None
        
        # Get raw value for this number
        raw_value = data.get(self.key)
        
        if raw_value is None:
            _LOGGER.debug(
                "Key '%s' not in coordinator data",
                self.key,
            )
            return None
        
        # Apply scaling factor
        scaled_value = raw_value * self.descriptor.scale
        
        _LOGGER.debug(
            "Number %s: raw=%s, scale=%s, result=%s",
            self.key,
            raw_value,
            self.descriptor.scale,
            scaled_value,
        )
        
        return scaled_value

    async def async_set_native_value(self, value: float) -> None:
        """
        Set a new value.
        
        PATTERN: Called when user changes value in Home Assistant.
        
        Responsibilities:
        1. Validate value is in range (Home Assistant already does this)
        2. Convert from user value to register value (inverse scale)
        3. Write to device via coordinator
        4. Handle errors gracefully
        5. Optionally refresh coordinator data
        
        Args:
            value: The new value (already in native units)
            
        Raises:
            ValueError: If write to device fails
        """
        
        # Check write access
        if not self.descriptor.writable:
            _LOGGER.error(
                "Cannot set %s: not writable",
                self.key,
            )
            raise ValueError(f"Number {self.key} is not writable")
        
        # Convert from user value to register value
        # User value is already scaled, so divide by scale to get raw value
        raw_value = int(value / self.descriptor.scale)
        
        _LOGGER.debug(
            "Setting %s to %s (raw: %s)",
            self.key,
            value,
            raw_value,
        )
        
        try:
            # Write to device
            success = await self.coordinator.async_write_register(
                self.descriptor.register,
                raw_value,
            )
            
            if not success:
                raise ValueError(
                    f"Failed to write register 0x{self.descriptor.register:04X}"
                )
            
            _LOGGER.info(
                "Successfully set %s to %s",
                self.key,
                value,
            )
            
        except Exception as err:
            _LOGGER.error(
                "Error setting %s: %s",
                self.key,
                err,
            )
            raise

    @property
    def available(self) -> bool:
        """
        Return True if entity is available.
        
        PATTERN: Check if coordinator has recent successful data.
        
        Returns:
            True if coordinator has valid data, False otherwise
        """
        
        has_data = bool(self.coordinator.data)
        last_update_success = self.coordinator.last_update_success
        
        return has_data and last_update_success

    @property
    def should_poll(self) -> bool:
        """
        Return False - this entity gets updates from coordinator.
        
        PATTERN: All entities listen to coordinator for updates.
        No per-entity polling needed (efficiency).
        
        Returns:
            False (rely on coordinator updates)
        """
        return False

    @property
    def device_info(self) -> dict[str, Any]:
        """
        Return device info for grouping in Home Assistant.
        
        Returns:
            Dictionary with device identification
        """
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_id)},
            "name": "Heliotherm Heat Pump",
            "manufacturer": "Heliotherm",
            "model": self.coordinator.device_model,
        }
