"""
Heliotherm integration for Home Assistant.

This module initializes the Heliotherm integration and handles setup/teardown.

Key responsibilities:
1. Extract user configuration
2. Create HeliothermModbusCoordinator for Modbus communication
3. Perform first data fetch to verify connection (early error detection)
4. Store coordinator in hass.data for entity platforms to use
5. Forward setup to entity platforms (sensor, switch, etc.)
6. Handle unload and cleanup on shutdown

Architecture:
- Uses DataUpdateCoordinator pattern (ADR-001)
- Supports read-only and write modes (ADR-002)
- Uses descriptor-based entity creation (ADR-004)

Setup Flow:
1. User creates config entry via config_flow
2. Home Assistant calls async_setup_entry()
3. We create coordinator and verify connection
4. Coordinator cached in hass.data
5. Entity platforms (sensor.py, switch.py) access coordinator
6. Each platform creates entities from descriptors
7. Home Assistant manages entity lifecycle
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import HeliothermModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Entity platforms to set up
# SENSOR: Always enabled (read-only temperature, pressure, power, etc.)
# NUMBER: Only enabled if write mode (setpoints, parameters, etc.)
# SWITCH: Only enabled if write mode (pump control, etc.)
PLATFORMS = [Platform.SENSOR]
WRITE_MODE_PLATFORMS = [Platform.NUMBER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Set up Heliotherm from a config entry.
    
    This is the main entry point when Home Assistant loads the integration.
    Called when:
    - User creates a new config entry via config flow
    - Home Assistant starts with existing config entry
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry with user configuration (host, port, mode, etc.)
    
    Returns:
        True if setup successful, False otherwise
    
    Flow:
    1. Extract configuration from config_entry.data
    2. Create HeliothermModbusCoordinator
    3. Perform first data fetch (verify connection early)
    4. Store coordinator in hass.data[DOMAIN][entry_id]
    5. Forward setup to entity platforms
    6. If write mode, also setup switch platform
    
    Raises:
        ConfigEntryNotReady: If connection fails (Home Assistant will retry)
    """
    
    _LOGGER.debug(
        "Setting up Heliotherm: %s",
        config_entry.data,
    )
    
    # Extract configuration early to prevent NameError if coordinator creation fails
    host = config_entry.data.get("host")
    port = config_entry.data.get("port", 502)
    
    try:
        # Create coordinator
        # This manages all Modbus communication and data caching
        # See: ADR-001: Coordinator Pattern
        coordinator = HeliothermModbusCoordinator(
            hass=hass,
            config_entry=config_entry,
        )
        
        # Perform first data fetch with timeout
        # This verifies the device is reachable early
        # Home Assistant will retry async_setup_entry if this fails
        import asyncio
        try:
            await asyncio.wait_for(
                coordinator.async_config_entry_first_refresh(),
                timeout=10.0,
            )
        except asyncio.TimeoutError as timeout_err:
            _LOGGER.error(
                "Timeout connecting to Heliotherm at %s:%s (>10 seconds)",
                host,
                port,
            )
            raise ConfigEntryNotReady(
                "Device is not responding"
            ) from timeout_err
        
    except Exception as err:
        _LOGGER.error(
            "Failed to connect to Heliotherm at %s:%s: %s",
            host,
            port,
            err,
        )
        raise ConfigEntryNotReady(
            f"Cannot connect to Heliotherm: {err}"
        ) from err
    
    # Store coordinator in hass.data
    # Entity platforms (sensor.py, switch.py) retrieve it via:
    # coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "coordinator": coordinator,
    }
    
    # Forward setup to entity platforms
    # Home Assistant calls async_setup_entry() in each platform module
    await hass.config_entries.async_forward_entry_setups(
        config_entry,
        PLATFORMS,
    )
    
    # If write mode enabled, also setup switch platform
    # See: ADR-002: Read-Only vs. Write Mode
    if not coordinator.read_only:
        _LOGGER.warning(
            "Heliotherm write mode enabled - switch controls available"
        )
        await hass.config_entries.async_forward_entry_setups(
            config_entry,
            WRITE_MODE_PLATFORMS,
        )
    else:
        _LOGGER.info(
            "Heliotherm read-only mode - no write operations allowed"
        )
    
    # Register unload listener for cleanup on shutdown/reload
    config_entry.async_on_unload(
        coordinator.async_shutdown
    )
    
    _LOGGER.info("Heliotherm setup completed successfully for %s:%s", host, port)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """
    Unload a config entry.
    
    Called when:
    - User deletes the config entry
    - Home Assistant is shutting down
    - Integration is being disabled
    - User modifies config (triggers reload)
    
    Responsibilities:
    - Unload entity platforms
    - Close Modbus connection
    - Clean up stored data
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry being unloaded
    
    Returns:
        True if successful, False otherwise
    """
    
    _LOGGER.debug("Unloading Heliotherm config entry")
    
    # Platforms to unload
    platforms_to_unload = PLATFORMS.copy()
    
    # If write mode was enabled, unload those platforms too
    coordinator: HeliothermModbusCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    
    if not coordinator.read_only:
        platforms_to_unload.extend(WRITE_MODE_PLATFORMS)
    
    # Unload all entity platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry,
        platforms_to_unload,
    )
    
    if unload_ok:
        # Clean up stored data
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
    
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """
    Reload a config entry.
    
    Called when user modifies configuration in config flow.
    Unloads and then reloads the entire entry.
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry being reloaded
    """
    
    _LOGGER.debug("Reloading Heliotherm config entry")
    
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
