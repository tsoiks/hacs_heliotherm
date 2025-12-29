"""
Switch platform for Heliotherm integration (write mode only).

Switches are controllable on/off entities:
- Pump enable/disable
- Auxiliary heater enable/disable
- etc.

Switches are only created when NOT in read_only mode.

Each switch descriptor automatically becomes a switch entity that:
1. Reads current state from coordinator
2. Allows user to toggle via Home Assistant UI
3. Writes new value via coordinator
4. Updates state after write succeeds

Architecture: See docs/adr/002-read-only-vs-write-mode.md
Descriptor pattern: See docs/COMPARATIVE_ANALYSIS.md
"""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_DESCRIPTORS
from .coordinator import HeliothermModbusCoordinator

_LOGGER = logging.getLogger(__name__)




async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up switch platform from config entry.
    
    PATTERN: Automatic entity creation from SWITCH_DESCRIPTORS.
    Only runs if NOT in read-only mode.
    
    This function:
    1. Gets coordinator from hass.data
    2. Checks if read-only mode is enabled
    3. If write mode allowed, iterates SWITCH_DESCRIPTORS
    4. Creates a HeliothermSwitch for each descriptor
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
    
    # PATTERN: Only set up switches if write mode is enabled
    # See ADR-002: Read-Only vs. Write Mode
    if coordinator.read_only:
        _LOGGER.info(
            "Heliotherm in read-only mode - switch entities disabled"
        )
        return
    
    try:
        # PATTERN: Create entity for each descriptor
        entities = [
            HeliothermSwitch(
                coordinator=coordinator,
                config_entry=config_entry,
                key=key,
                descriptor=descriptor,
            )
            for key, descriptor in SWITCH_DESCRIPTORS.items()
        ]
        
        async_add_entities(entities)
        
        _LOGGER.debug(
            "Created %d switch entities from SWITCH_DESCRIPTORS",
            len(entities),
        )
    except Exception as err:
        _LOGGER.error(
            "Failed to set up switch platform: %s",
            err,
        )
        return


class HeliothermSwitch(CoordinatorEntity, SwitchEntity):
    """
    Single Heliotherm switch entity.
    
    PATTERN: One entity per SWITCH_DESCRIPTOR.
    Only available in write (non-read-only) mode.
    
    Allows user to toggle a device control via Home Assistant UI.
    When toggled, writes new value to Modbus register.
    
    Workflow:
    1. User toggles switch in Home Assistant UI
    2. async_turn_on() or async_turn_off() called
    3. Coordinator writes to Modbus register
    4. Coordinator auto-refreshes to show new state
    5. Entities notified, UI updates
    
    Architecture: See ADR-002: Read-Only vs. Write Mode
    """
    
    def __init__(
        self,
        coordinator: HeliothermModbusCoordinator,
        config_entry: ConfigEntry,
        key: str,
        descriptor,
    ):
        """
        Initialize switch.
        
        Args:
            coordinator: The data coordinator
            config_entry: ConfigEntry
            key: Descriptor key (e.g., "circulation_pump")
            descriptor: SwitchDescriptor with register and name
        """
        
        super().__init__(coordinator)
        
        self.config_entry = config_entry
        self.key = key
        self.descriptor = descriptor
        
        # Build unique entity ID
        self._attr_unique_id = f"heliotherm_{config_entry.entry_id}_{key}"
        
        # Set entity name
        self._attr_name = f"Heliotherm {descriptor.name}"
        
        # Set icon for UI
        if descriptor.icon:
            self._attr_icon = descriptor.icon
    
    @property
    def is_on(self) -> bool | None:
        """
        Return True if switch is on, False if off.
        
        PATTERN: Read state from coordinator data.
        
        Coordinator provides cached data dict like:
        {
            "circulation_pump": True,  # or False
            "auxiliary_heater": False,
        }
        
        Returns:
            True = on, False = off, None = unknown
        """
        
        data = self.coordinator.data
        
        if not data:
            _LOGGER.debug("No data from coordinator")
            return None
        
        value = data.get(self.key)
        
        if value is None:
            _LOGGER.debug(
                "Key '%s' not in coordinator data",
                self.key,
            )
            return None
        
        return bool(value)
    
    @property
    def available(self) -> bool:
        """
        Return True if switch is available for control.
        
        Switch unavailable if:
        1. Coordinator has no data yet
        2. Last update failed
        3. Key not in coordinator data
        
        Returns:
            True if switch can be controlled, False otherwise
        """
        
        has_data = bool(self.coordinator.data)
        last_success = self.coordinator.last_update_success
        key_exists = self.key in (self.coordinator.data or {})
        
        return has_data and last_success and key_exists
    
    @property
    def should_poll(self) -> bool:
        """
        Return False - switch gets updates from coordinator.
        
        No per-entity polling needed. Coordinator handles all updates.
        
        Returns:
            False (rely on coordinator updates)
        """
        return False
    
    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for grouping in Home Assistant."""
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_id)},
            "name": "Heliotherm Heat Pump",
            "manufacturer": "Heliotherm",
            "model": self.coordinator.device_model,
        }
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """
        Turn on the switch.
        
        PATTERN: Write to Modbus register via coordinator.
        
        Coordinator's async_write_register method:
        1. Checks read_only flag (should be allowed here)
        2. Connects to Modbus if needed
        3. Writes register value (usually 1 for on)
        4. Auto-refreshes coordinator data
        5. All entities notified of update
        
        Raises:
            UpdateFailed: If write operation fails
        """
        
        try:
            _LOGGER.debug("Turning on switch: %s", self.key)
            
            # Write register to Modbus device
            # Register address from descriptor
            # Value 1 = on (typical for boolean registers)
            success = await self.coordinator.async_write_register(
                register=self.descriptor.register,
                value=1,
            )
            
            if not success:
                _LOGGER.error(
                    "Failed to turn on switch: %s",
                    self.key,
                )
                return
            
            _LOGGER.info(
                "Successfully turned on switch: %s",
                self.key,
            )
        
        except Exception as err:
            _LOGGER.error(
                "Error turning on switch %s: %s",
                self.key,
                err,
            )
            raise
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """
        Turn off the switch.
        
        PATTERN: Write to Modbus register via coordinator.
        
        Similar to async_turn_on but writes 0 (off) instead of 1 (on).
        
        Raises:
            UpdateFailed: If write operation fails
        """
        
        try:
            _LOGGER.debug("Turning off switch: %s", self.key)
            
            # Write register to Modbus device
            # Value 0 = off (typical for boolean registers)
            success = await self.coordinator.async_write_register(
                register=self.descriptor.register,
                value=0,
            )
            
            if not success:
                _LOGGER.error(
                    "Failed to turn off switch: %s",
                    self.key,
                )
                raise RuntimeError(f"Failed to turn off switch {self.key}")
            
            _LOGGER.info(
                "Successfully turned off switch: %s",
                self.key,
            )
        
        except Exception as err:
            _LOGGER.error(
                "Error turning off switch %s: %s",
                self.key,
                err,
            )
            raise
