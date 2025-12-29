"""
Data coordinator for Heliotherm Modbus communication.

The coordinator is the central hub for all Modbus communication:
- Manages single ModbusClient connection (connection pooling)
- Periodically fetches device data
- Handles all error conditions gracefully
- Implements timeout protection
- Caches data for resilience
- Provides async methods for reads and writes

All entities subscribe to the coordinator for updates.
When coordinator's data changes, all entities are notified.

Architecture: See docs/adr/001-coordinator-pattern.md
Production patterns: See docs/COMPARATIVE_ANALYSIS.md
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class HeliothermModbusCoordinator(DataUpdateCoordinator):
    """
    Coordinator for Heliotherm Modbus TCP communication.
    
    Key responsibilities:
    1. Maintain single ModbusClient connection (connection pooling)
    2. Periodically fetch all device data via _async_update_data()
    3. Handle errors gracefully with data caching
    4. Provide timeout protection on all operations
    5. Implement async write operations
    6. Log all operations for debugging
    
    Entities subscribe to this coordinator and are automatically notified
    when new data is available.
    
    Example usage:
        coordinator = HeliothermModbusCoordinator(hass, config_entry)
        await coordinator.async_config_entry_first_refresh()
        
        # Entities access data
        temp = coordinator.data.get("supply_temperature")
        
        # Entities can trigger refresh after write
        await coordinator.async_request_refresh()
    """

    def __init__(self, hass: HomeAssistant, config_entry):
        """
        Initialize the coordinator.
        
        Args:
            hass: Home Assistant instance
            config_entry: ConfigEntry with host, port, read_only flag
            
        Raises:
            ValueError: If configuration is invalid (host, port, etc.)
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Heliotherm Modbus",
            update_interval=SCAN_INTERVAL,
        )
        
        self.hass = hass
        self.config_entry = config_entry
        
        # Configuration - validate before storing
        self.host = config_entry.data.get("host")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError(
                f"Invalid host configuration: {self.host}"
            )
        
        self.port = config_entry.data.get("port", 502)
        if not isinstance(self.port, int) or self.port < 1 or self.port > 65535:
            raise ValueError(
                f"Invalid port configuration: {self.port}. Must be 1-65535."
            )
        
        self.read_only = config_entry.data.get("read_only", True)
        
        # Device information - used for device grouping in Home Assistant
        # Generates unique ID from host and port
        self.device_id = f"heliotherm_{self.host}_{self.port}"
        # Model can be set from config or will be queried from device
        self.device_model = config_entry.data.get(
            "device_model",
            "Heliotherm Heat Pump"
        )
        
        # PATTERN: Single connection instance (connection pooling)
        self.client: AsyncModbusTcpClient | None = None
        self._connect_lock = asyncio.Lock()
        
        # PATTERN: Cache last-known-good data for resilience
        self.last_valid_data: dict[str, Any] = {}

    async def async_connect(self) -> bool:
        """
        Establish or verify Modbus connection.
        
        PATTERN: Async lock prevents simultaneous connection attempts.
        Uses connection pooling: reuses existing connection if valid.
        
        Returns:
            True if connected, False if connection failed
            
        Raises:
            UpdateFailed: If connection cannot be established
        """
        async with self._connect_lock:
            # Return if already connected
            if self.client and self.client.connected:
                _LOGGER.debug("Already connected to Heliotherm")
                return True
            
            try:
                _LOGGER.debug(
                    "Connecting to Heliotherm at %s:%s",
                    self.host,
                    self.port,
                )
                
                # Create new client
                self.client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=5,
                )
                
                # PATTERN: Timeout protection on connection
                connected = await asyncio.wait_for(
                    self.client.connect(),
                    timeout=5.0,
                )
                
                if not connected:
                    raise ConnectionError("Failed to establish connection")
                
                _LOGGER.info(
                    "Connected to Heliotherm at %s:%s",
                    self.host,
                    self.port,
                )
                return True
                
            except asyncio.TimeoutError:
                self.client = None
                _LOGGER.error("Heliotherm connection timeout")
                raise UpdateFailed("Connection timeout")
                
            except Exception as err:
                self.client = None
                _LOGGER.error("Failed to connect to Heliotherm: %s", err)
                raise UpdateFailed(f"Connection failed: {err}") from err

    async def async_disconnect(self) -> None:
        """Safely disconnect from Modbus."""
        if self.client:
            try:
                self.client.close()
            except Exception as err:
                _LOGGER.warning("Error closing connection: %s", err)
            finally:
                self.client = None

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Fetch fresh data from Heliotherm device.
        
        PATTERN: Called periodically by Home Assistant's DataUpdateCoordinator.
        Fetches all configured register values and returns as dict.
        Reads from SENSOR_DESCRIPTORS, SWITCH_DESCRIPTORS, and NUMBER_DESCRIPTORS.
        
        Returns:
            Dictionary of {key: value} pairs
            Uses last_valid_data if fetch fails (graceful degradation)
            
        Raises:
            UpdateFailed: If data cannot be fetched
            Home Assistant automatically handles retries with backoff
            
        Example return value:
            {
                "supply_temperature": 22.5,
                "return_temperature": 20.1,
                "power_output": 8.5,
                "system_pressure": 2.5,
                "circulation_pump": 1,
            }
        """
        try:
            from .const import (
                SENSOR_DESCRIPTORS,
                SWITCH_DESCRIPTORS,
                NUMBER_DESCRIPTORS,
                DataType,
                RegisterType,
            )
            import struct
            
            # Ensure connection is established
            await self.async_connect()
            
            data: dict[str, Any] = {}
            
            # PATTERN: Read all sensor registers
            for key, descriptor in SENSOR_DESCRIPTORS.items():
                try:
                    # Determine how many registers to read based on data type
                    register_count = 2 if descriptor.data_type == DataType.FLOAT32 else 1
                    
                    registers = await self.async_read_register(
                        descriptor.register,
                        count=register_count,
                    )
                    
                    if registers is None:
                        _LOGGER.warning(
                            "Failed to read sensor %s at register 0x%04X",
                            key,
                            descriptor.register,
                        )
                        continue
                    
                    # Handle Float32 (2 registers) vs Int16 (1 register)
                    if register_count == 2 and isinstance(registers, list):
                        # Convert 2 Int16 registers to Float32
                        # High word in first register, low word in second
                        try:
                            high = registers[0]
                            low = registers[1]
                            raw_bytes = struct.pack('>HH', high, low)
                            value = struct.unpack('>f', raw_bytes)[0]
                        except (struct.error, ValueError) as err:
                            _LOGGER.warning(
                                "Failed to parse Float32 at register 0x%04X: %s",
                                descriptor.register,
                                err,
                            )
                            continue
                    elif isinstance(registers, list):
                        value = registers[0]
                    else:
                        value = registers
                    
                    # Apply scale factor
                    data[key] = value * descriptor.scale
                    
                except Exception as err:
                    _LOGGER.warning(
                        "Error reading sensor %s: %s",
                        key,
                        err,
                    )
                    continue
            
            # PATTERN: Read all switch registers
            for key, descriptor in SWITCH_DESCRIPTORS.items():
                try:
                    registers = await self.async_read_register(
                        descriptor.register,
                        count=1,
                    )
                    
                    if registers is None:
                        _LOGGER.warning(
                            "Failed to read switch %s at register 0x%04X",
                            key,
                            descriptor.register,
                        )
                        continue
                    
                    value = registers if isinstance(registers, int) else registers[0]
                    data[key] = bool(value)
                    
                except Exception as err:
                    _LOGGER.warning(
                        "Error reading switch %s: %s",
                        key,
                        err,
                    )
                    continue
            
            # PATTERN: Read all number descriptors
            for key, descriptor in NUMBER_DESCRIPTORS.items():
                try:
                    # Determine register count based on data type
                    register_count = 2 if descriptor.data_type == DataType.FLOAT32 else 1
                    
                    registers = await self.async_read_register(
                        descriptor.register,
                        count=register_count,
                    )
                    
                    if registers is None:
                        _LOGGER.warning(
                            "Failed to read number %s at register 0x%04X",
                            key,
                            descriptor.register,
                        )
                        continue
                    
                    # Handle Float32 vs Int16
                    if register_count == 2 and isinstance(registers, list):
                        try:
                            high = registers[0]
                            low = registers[1]
                            raw_bytes = struct.pack('>HH', high, low)
                            value = struct.unpack('>f', raw_bytes)[0]
                        except (struct.error, ValueError) as err:
                            _LOGGER.warning(
                                "Failed to parse Float32 at register 0x%04X: %s",
                                descriptor.register,
                                err,
                            )
                            continue
                    elif isinstance(registers, list):
                        value = registers[0]
                    else:
                        value = registers
                    
                    # Apply scale factor
                    data[key] = value * descriptor.scale
                    
                except Exception as err:
                    _LOGGER.warning(
                        "Error reading number %s: %s",
                        key,
                        err,
                    )
                    continue
            
            # PATTERN: Cache successful data for resilience
            if data:
                self.last_valid_data = data
            
            _LOGGER.debug("Updated Heliotherm data: %d registers", len(data))
            return data or self.last_valid_data
            
        except ModbusException as err:
            _LOGGER.error("Modbus error reading data: %s", err)
            raise UpdateFailed(f"Modbus error: {err}") from err
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout reading Heliotherm data")
            raise UpdateFailed("Read timeout") from None
            
        except Exception as err:
            _LOGGER.error("Unexpected error reading Heliotherm: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_read_register(
        self,
        register: int,
        count: int = 1,
        slave_id: int = 1,
    ) -> int | list[int] | None:
        """
        Read one or more holding registers.
        
        PATTERN: Low-level register read with timeout and error handling.
        
        Args:
            register: Register address (0x0000-0xFFFF)
            count: Number of registers to read (default: 1)
            slave_id: Modbus slave ID (default: 1)
            
        Returns:
            Single register value (count=1) or list of values
            None if read failed
            
        Example:
            # Read single register (temperature)
            temp = await coordinator.async_read_register(0x0100)
            if temp is not None:
                celsius = temp * 0.1  # Apply scale
                
            # Read multiple registers (32-bit value)
            data = await coordinator.async_read_register(0x0100, count=2)
        """
        try:
            await self.async_connect()
            
            # PATTERN: Timeout protection for Modbus operation
            result = await asyncio.wait_for(
                self.client.read_holding_registers(
                    address=register,
                    count=count,
                    slave=slave_id,
                ),
                timeout=5.0,
            )
            
            if result.isError():
                _LOGGER.warning(
                    "Failed to read register 0x%04X: %s",
                    register,
                    result,
                )
                return None
            
            # Return single value or list
            if count == 1:
                return result.registers[0] if result.registers else None
            else:
                return result.registers
            
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout reading register 0x%04X", register)
            return None
            
        except ModbusException as err:
            _LOGGER.warning(
                "Modbus error reading register 0x%04X: %s",
                register,
                err,
            )
            return None
            
        except Exception as err:
            _LOGGER.error(
                "Unexpected error reading register 0x%04X: %s",
                register,
                err,
            )
            return None

    async def async_write_register(
        self,
        register: int,
        value: int,
        slave_id: int = 1,
    ) -> bool:
        """
        Write a holding register.
        
        PATTERN: Write with read-only mode check and refresh.
        Only callable if component is NOT in read-only mode.
        
        Args:
            register: Register address
            value: Value to write
            slave_id: Modbus slave ID
            
        Returns:
            True if write succeeded, False otherwise
            
        Raises:
            ValueError: If component is in read-only mode
            
        Example:
            # Entities should check read_only before calling:
            if not self.coordinator.read_only:
                success = await self.coordinator.async_write_register(
                    register=0x0400,
                    value=1,  # Turn on
                )
                if success:
                    # Refresh data to show updated state
                    await self.coordinator.async_request_refresh()
        """
        if self.read_only:
            raise ValueError(
                "Cannot write register: component is in read-only mode"
            )
        
        try:
            await self.async_connect()
            
            _LOGGER.debug(
                "Writing register 0x%04X = %d",
                register,
                value,
            )
            
            # PATTERN: Timeout protection on write
            result = await asyncio.wait_for(
                self.client.write_register(
                    address=register,
                    value=value,
                    slave=slave_id,
                ),
                timeout=5.0,
            )
            
            if result.isError():
                _LOGGER.error(
                    "Failed to write register 0x%04X = %d: %s",
                    register,
                    value,
                    result,
                )
                return False
            
            _LOGGER.info(
                "Successfully wrote register 0x%04X = %d",
                register,
                value,
            )
            
            # PATTERN: Refresh coordinator data after write
            # This ensures entities see the updated value
            await self.async_request_refresh()
            
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout writing register 0x%04X",
                register,
            )
            return False
            
        except ModbusException as err:
            _LOGGER.error(
                "Modbus error writing register 0x%04X: %s",
                register,
                err,
            )
            return False
            
        except Exception as err:
            _LOGGER.error(
                "Unexpected error writing register 0x%04X: %s",
                register,
                err,
            )
            return False

    async def async_shutdown(self) -> None:
        """Clean up resources on shutdown."""
        await self.async_disconnect()

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to Modbus device."""
        return self.client is not None and self.client.connected
