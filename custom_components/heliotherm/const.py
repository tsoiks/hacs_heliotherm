"""
Constants and descriptors for Heliotherm integration.

This module defines all register and entity information using dataclass descriptors.
This is the SINGLE SOURCE OF TRUTH for:
- Register addresses and metadata
- Entity definitions (sensors, switches, numbers)
- Entity configurations (units, scales, icons)

Benefits of descriptor pattern:
- Type-safe register definitions (dataclass validation)
- Easy to add new entities (one descriptor entry)
- No code duplication across platforms
- Single place to verify register addresses
- Automatic entity creation via loops

See:
- docs/COMPARATIVE_ANALYSIS.md (why descriptors are better)
- docs/adr/004-entity-design.md (entity design decisions)
"""

from dataclasses import dataclass
from enum import Enum

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    UnitOfTemperature,
    UnitOfPower,
    UnitOfEnergy,
)
from homeassistant.components.sensor import SensorDeviceClass

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================

DOMAIN = "heliotherm"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 30
CONF_READ_ONLY = "read_only"
CONF_SLAVE_ID = "slave_id"


# ==============================================================================
# ENUM DEFINITIONS (Type-Safe)
# ==============================================================================

class RegisterType(str, Enum):
    """Type of Modbus register."""
    HOLDING = "holding"
    INPUT = "input"


class DataType(str, Enum):
    """Data type of register value."""
    INT16 = "int16"        # Single register, 16-bit signed integer
    FLOAT32 = "float32"    # Two registers, 32-bit IEEE 754 float
    UINT16 = "uint16"      # Single register, 16-bit unsigned integer


# ==============================================================================
# DATACLASS DESCRIPTORS (Type-Safe Entity Definitions)
# ==============================================================================
# 
# PATTERN: Sigenergy-Local-Modbus approach
#
# Each descriptor defines:
# - Register address
# - Data type and scale
# - Home Assistant metadata (name, units, device class)
# - Access mode (read-only or read-write)
#
# Descriptors are automatically iterated to create entities.
# Adding a new sensor = adding one descriptor to a dict.
#

@dataclass
class SensorDescriptor:
    """
    Descriptor for a read-only sensor entity.
    
    PATTERN: Single source of truth for sensor definition.
    Used to automatically create Home Assistant sensor entities.
    
    Attributes:
        register: Modbus register address (0x0000-0xFFFF)
        name: Human-readable display name
        data_type: Data type of register (INT16, FLOAT32, UINT16)
        scale: Multiplicative scale factor (register_value * scale)
        unit: Unit of measurement (e.g., "°C", "bar", "kW")
        device_class: Home Assistant device class (for UI icons)
        icon: Optional icon override (MDI format)
        register_type: Register type (HOLDING or INPUT)
        
    Example:
        SensorDescriptor(
            register=0x0100,
            name="Supply Temperature",
            data_type=DataType.FLOAT32,
            scale=1.0,
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )
    """
    register: int
    name: str
    data_type: DataType = DataType.INT16
    scale: float = 1.0
    unit: str | None = None
    device_class: str | None = None
    icon: str | None = None
    register_type: RegisterType = RegisterType.HOLDING


@dataclass
class SwitchDescriptor:
    """
    Descriptor for a writable switch/relay control.
    
    PATTERN: Defines both read-state and write-command registers.
    The 'writable' flag is checked by entities before allowing writes.
    
    Attributes:
        register: Register address for reading state
        write_register: Register for writing commands (defaults to register)
        name: Display name
        writable: Can this switch be written to?
        icon: Icon to display
        
    Example:
        SwitchDescriptor(
            register=0x0200,
            name="Circulation Pump",
            writable=True,
        )
    """
    register: int
    name: str
    writable: bool = True
    write_register: int | None = None
    icon: str | None = None

    @property
    def write_addr(self) -> int:
        """Get the register address for writing."""
        return self.write_register or self.register


@dataclass
class NumberDescriptor:
    """
    Descriptor for a numeric setpoint/parameter.
    
    Attributes:
        register: Register address
        name: Display name
        data_type: Data type of register (INT16, FLOAT32, UINT16)
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        scale: Scale factor
        step: UI step size
        unit: Unit of measurement
        writable: Can be written to
        icon: Icon to display
        
    Example:
        NumberDescriptor(
            register=0x0300,
            name="Target Temperature",
            data_type=DataType.FLOAT32,
            min_value=10.0,
            max_value=60.0,
            scale=1.0,
            unit=UnitOfTemperature.CELSIUS,
        )
    """
    register: int
    name: str
    min_value: float
    max_value: float
    data_type: DataType = DataType.INT16
    scale: float = 1.0
    step: float = 1.0
    unit: str | None = None
    writable: bool = True
    icon: str | None = None


# ==============================================================================
# SENSOR DESCRIPTORS (Read-Only)
# ==============================================================================
#
# Each sensor descriptor automatically creates a Home Assistant sensor entity.
# To add a new sensor: just add an entry to this dict.
#
# Register addresses from: docs/MODBUS_PROTOCOL.md
# Heliotherm Modbus documentation: docs/Modbus-Doku_DE.pdf
#

SENSOR_DESCRIPTORS: dict[str, SensorDescriptor] = {
    # =========================================================================
    # TEMPERATURE SENSORS (Registers 100-107)
    # =========================================================================
    # Register 100-101: Supply Temperature (Float32, IEEE 754)
    "supply_temperature": SensorDescriptor(
        register=0x0064,  # 100 decimal = 0x64
        name="Supply Temperature",
        data_type=DataType.FLOAT32,
        scale=1.0,  # Float32 values are in °C directly
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 102-103: Return Temperature (Float32, IEEE 754)
    "return_temperature": SensorDescriptor(
        register=0x0066,  # 102 decimal = 0x66
        name="Return Temperature",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 104: Setpoint Temperature (Int16, scale 0.1)
    "setpoint_temperature": SensorDescriptor(
        register=0x0068,  # 104 decimal = 0x68
        name="Setpoint Temperature",
        scale=0.1,
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-high",
        register_type=RegisterType.HOLDING,
    ),
    
    # Register 106-107: Outside Temperature (Float32, IEEE 754)
    "outside_temperature": SensorDescriptor(
        register=0x006A,  # 106 decimal = 0x6A
        name="Outside Temperature",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-lines",
        register_type=RegisterType.INPUT,
    ),
    
    # =========================================================================
    # STATUS/OPERATING MODE SENSORS (Registers 110-112)
    # =========================================================================
    # Register 110: Pump Status (Bool: 0=Off, 1=On)
    "pump_status": SensorDescriptor(
        register=0x006E,  # 110 decimal = 0x6E
        name="Pump Status",
        scale=1.0,
        unit=None,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:water-pump",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 111: Operating Mode (Int16: 0=Heat, 1=Cool, 2=Standby)
    "operating_mode": SensorDescriptor(
        register=0x006F,  # 111 decimal = 0x6F
        name="Operating Mode",
        scale=1.0,
        unit=None,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:cog",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 112: Device Status (Int16)
    "device_status": SensorDescriptor(
        register=0x0070,  # 112 decimal = 0x70
        name="Device Status",
        scale=1.0,
        unit=None,
        device_class=None,
        icon="mdi:information",
        register_type=RegisterType.INPUT,
    ),
    
    # =========================================================================
    # PRESSURE/POWER SENSORS (Registers 120-133)
    # =========================================================================
    # Register 120-121: System Pressure (Float32, IEEE 754, bar)
    "system_pressure": SensorDescriptor(
        register=0x0078,  # 120 decimal = 0x78
        name="System Pressure",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit="bar",
        device_class=SensorDeviceClass.PRESSURE,
        icon="mdi:gauge",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 130-131: Power Output (Float32, IEEE 754, kW)
    "power_output": SensorDescriptor(
        register=0x0082,  # 130 decimal = 0x82
        name="Power Output",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 132-133: COP - Coefficient of Performance (Float32, IEEE 754)
    "coefficient_of_performance": SensorDescriptor(
        register=0x0084,  # 132 decimal = 0x84
        name="Coefficient of Performance",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit=None,
        device_class=None,
        icon="mdi:speedometer",
        register_type=RegisterType.INPUT,
    ),
    
    # =========================================================================
    # ADDITIONAL DIAGNOSTIC SENSORS
    # =========================================================================
    # Register 140-141: Compressor Power Input (Float32, kW)
    "compressor_power_input": SensorDescriptor(
        register=0x008C,  # 140 decimal = 0x8C
        name="Compressor Power Input",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt-circle",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 142-143: Flow Rate (Float32, l/min)
    "flow_rate": SensorDescriptor(
        register=0x008E,  # 142 decimal = 0x8E
        name="Flow Rate",
        data_type=DataType.FLOAT32,
        scale=1.0,
        unit="l/min",
        device_class=None,
        icon="mdi:water-pump",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 150: Operating Hours (Int16, hours)
    "operating_hours": SensorDescriptor(
        register=0x0096,  # 150 decimal = 0x96
        name="Operating Hours",
        scale=1.0,
        unit="h",
        device_class=None,
        icon="mdi:clock",
        register_type=RegisterType.INPUT,
    ),
    
    # Register 151: Error Code (Int16)
    "error_code": SensorDescriptor(
        register=0x0097,  # 151 decimal = 0x97
        name="Error Code",
        scale=1.0,
        unit=None,
        device_class=None,
        icon="mdi:alert-circle",
        register_type=RegisterType.INPUT,
    ),
}


# ==============================================================================
# SWITCH DESCRIPTORS (Writable Controls)
# ==============================================================================
#
# Switches can be read-only or writable depending on coordinator.read_only
#
# See: docs/adr/002-read-only-vs-write-mode.md
#

SWITCH_DESCRIPTORS: dict[str, SwitchDescriptor] = {
    # =========================================================================
    # CONTROLLABLE SWITCHES (Registers 200-210)
    # =========================================================================
    # Register 200: Circulation Pump Enable/Disable
    "circulation_pump": SwitchDescriptor(
        register=0x00C8,  # 200 decimal = 0xC8
        name="Circulation Pump",
        writable=True,
        icon="mdi:water-pump",
    ),
    
    # Register 201: Auxiliary Heater Enable/Disable
    "auxiliary_heater": SwitchDescriptor(
        register=0x00C9,  # 201 decimal = 0xC9
        name="Auxiliary Heater",
        writable=True,
        icon="mdi:heat-wave",
    ),
    
    # Register 202: Compressor Enable/Disable
    "compressor_enable": SwitchDescriptor(
        register=0x00CA,  # 202 decimal = 0xCA
        name="Compressor Enable",
        writable=True,
        icon="mdi:cog",
    ),
    
    # Register 203: Hot Water Circulation Pump
    "hot_water_pump": SwitchDescriptor(
        register=0x00CB,  # 203 decimal = 0xCB
        name="Hot Water Circulation Pump",
        writable=True,
        icon="mdi:water-pump",
    ),
}


# ==============================================================================
# NUMBER DESCRIPTORS (Numeric Controls/Setpoints)
# ==============================================================================
#
# For numeric parameters like target temperature, setpoints, etc.
#

NUMBER_DESCRIPTORS: dict[str, NumberDescriptor] = {
    # =========================================================================
    # NUMERIC SETPOINTS & PARAMETERS (Registers 300-315)
    # =========================================================================
    # Register 300-301: Target Supply Temperature (Float32, °C)
    "target_supply_temperature": NumberDescriptor(
        register=0x012C,  # 300 decimal = 0x12C
        name="Target Supply Temperature",
        data_type=DataType.FLOAT32,
        min_value=10.0,
        max_value=60.0,
        scale=1.0,
        step=0.5,
        unit=UnitOfTemperature.CELSIUS,
        writable=True,
        icon="mdi:thermometer-high",
    ),
    
    # Register 302: Target Room Temperature (Int16, scale 0.1, °C)
    "target_room_temperature": NumberDescriptor(
        register=0x012E,  # 302 decimal = 0x12E
        name="Target Room Temperature",
        min_value=10.0,
        max_value=30.0,
        scale=0.1,
        step=0.5,
        unit=UnitOfTemperature.CELSIUS,
        writable=True,
        icon="mdi:home-thermometer",
    ),
    
    # Register 304: Target DHW Temperature (Int16, scale 0.1, °C)
    "target_dhw_temperature": NumberDescriptor(
        register=0x0130,  # 304 decimal = 0x130
        name="Target DHW Temperature",
        min_value=30.0,
        max_value=65.0,
        scale=0.1,
        step=1.0,
        unit=UnitOfTemperature.CELSIUS,
        writable=True,
        icon="mdi:water-boiler",
    ),
    
    # Register 306: Compressor Frequency Target (Int16, Hz)
    "compressor_frequency_target": NumberDescriptor(
        register=0x0132,  # 306 decimal = 0x132
        name="Compressor Frequency Target",
        min_value=0.0,
        max_value=120.0,
        scale=1.0,
        step=1.0,
        unit="Hz",
        writable=True,
        icon="mdi:speedometer",
    ),
    
    # Register 308-309: Maximum Pressure Setpoint (Float32, bar)
    "max_pressure_setpoint": NumberDescriptor(
        register=0x0134,  # 308 decimal = 0x134
        name="Maximum Pressure Setpoint",
        data_type=DataType.FLOAT32,
        min_value=1.0,
        max_value=35.0,
        scale=1.0,
        step=0.5,
        unit="bar",
        writable=True,
        icon="mdi:gauge-full",
    ),
    
    # Register 310-311: Minimum Pressure Setpoint (Float32, bar)
    "min_pressure_setpoint": NumberDescriptor(
        register=0x0136,  # 310 decimal = 0x136
        name="Minimum Pressure Setpoint",
        data_type=DataType.FLOAT32,
        min_value=1.0,
        max_value=35.0,
        scale=1.0,
        step=0.5,
        unit="bar",
        writable=True,
        icon="mdi:gauge-empty",
    ),
}
