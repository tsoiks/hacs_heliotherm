# Development Guide: Heliotherm Component

This guide helps you understand, extend, and maintain the Heliotherm component codebase. It covers architecture, common tasks, testing, and best practices.

**Audience**: Developers, maintainers, and contributors  
**Prerequisites**: Python 3.9+, basic Git knowledge, Home Assistant development concepts

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [How to Extend the Code](#how-to-extend-the-code)
5. [How to Maintain the Code](#how-to-maintain-the-code)
6. [Testing](#testing)
7. [Code Quality](#code-quality)
8. [Debugging](#debugging)
9. [Design Decisions](#design-decisions)

---

## Architecture Overview

The Heliotherm component uses three core architectural patterns:

### 1. Coordinator Pattern (ADR-001)

**What**: Centralized data management via `DataUpdateCoordinator`

**Why**: 
- Prevents duplicate Modbus requests
- Ensures all entities see consistent data
- Centralizes error handling
- Provides automatic retry logic

**How it works**:
```
Coordinator polls every 30 seconds
    ↓
Reads all registers from heat pump
    ↓
Stores data in coordinator.data dict
    ↓
Notifies all subscribed entities
    ↓
Home Assistant updates UI
```

**Code location**: `custom_components/heliotherm/coordinator.py`

**Key features**:
- Connection pooling: One AsyncModbusTcpClient reused across calls
- Timeout protection: 5-second timeout on all operations
- Data caching: Falls back to last-known-good values on error
- Error recovery: Automatic retry with exponential backoff

**For more details**: [ADR-001: Coordinator Pattern](docs/adr/001-coordinator-pattern.md)

### 2. Descriptor-Based Entities (ADR-004)

**What**: Entities defined declaratively in `const.py` via dataclasses

**Why**:
- Single source of truth for entity definitions
- Type-safe register addresses and configurations
- Easy to add new entities (one line per entity)
- Automatic entity creation via loops

**How it works**:
```python
# const.py: Define once
SENSOR_DESCRIPTORS = {
    "supply_temperature": SensorDescriptor(
        register=0x0100,
        name="Supply Temperature",
        scale=0.1,
        unit="°C",
        device_class="temperature",
    ),
}

# sensor.py: Automatic loop
for key, descriptor in SENSOR_DESCRIPTORS.items():
    entities.append(HeliothermSensor(coordinator, key, descriptor))
```

**Code location**: 
- Descriptors: `custom_components/heliotherm/const.py`
- Entity creation: `custom_components/heliotherm/sensor.py`, `switch.py`

**Benefits**:
- Adding a sensor is a 5-line change in const.py
- No changes needed to entity platform code
- Scales to 100+ registers without code bloat

**For more details**: [ADR-004: Entity Design](docs/adr/004-entity-design.md)

### 3. Read-Only vs. Write Mode (ADR-002)

**What**: Configuration-based capability control via `read_only` flag

**Why**:
- Different users need different security levels
- Monitoring-only users shouldn't be able to send commands
- Safe by default (read_only: true is default)

**How it works**:
```yaml
# User configuration
heliotherm:
  read_only: true    # Sensors only (safe default)
  # OR
  read_only: false   # Sensors + switches + control
```

```python
# Implementation in __init__.py
if not read_only:
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SWITCH, Platform.NUMBER]
    )
```

**Code location**: `custom_components/heliotherm/__init__.py`

**For more details**: [ADR-002: Read-Only vs. Write Mode](docs/adr/002-read-only-vs-write-mode.md)

---

## Project Structure

```
custom_components/heliotherm/
├── __init__.py
│   └─ Integration setup, coordinator creation, platform forwarding
│      Key functions: async_setup_entry(), async_unload_entry()
│
├── const.py
│   └─ Configuration schema, register definitions, entity descriptors
│      Key constants: DOMAIN, SENSOR_DESCRIPTORS, SWITCH_DESCRIPTORS
│      Key classes: SensorDescriptor, SwitchDescriptor
│
├── coordinator.py
│   └─ Modbus communication, data caching, error handling
│      Key class: HeliothermModbusCoordinator(DataUpdateCoordinator)
│      Key methods: _async_update_data(), async_read_register(), async_write_register()
│
├── sensor.py
│   └─ Read-only sensor entity creation
│      Key function: async_setup_entry() (iterates SENSOR_DESCRIPTORS)
│      Key class: HeliothermSensor (extends CoordinatorEntity, SensorEntity)
│
├── switch.py
│   └─ Control switch entity creation (write mode only)
│      Key function: async_setup_entry() (iterates SWITCH_DESCRIPTORS)
│      Key class: HeliothermSwitch (extends CoordinatorEntity, SwitchEntity)
│
├── exceptions.py
│   └─ Custom exception types
│      Key classes: HeliotermException, UpdateFailed
│
└── manifest.json
    └─ Component metadata (name, version, dependencies, etc.)
```

### File Dependencies

```
__init__.py
  ├─ imports from const (DOMAIN, configuration)
  ├─ imports from coordinator (HeliothermModbusCoordinator)
  └─ forwards setup to sensor.py and switch.py

const.py
  └─ imported by: __init__.py, coordinator.py, sensor.py, switch.py

coordinator.py
  ├─ imports from const (register definitions)
  └─ imported by: __init__.py, sensor.py, switch.py

sensor.py & switch.py
  ├─ import from const (descriptors)
  ├─ import from coordinator (CoordinatorEntity)
  └─ access hass.data[DOMAIN][entry_id]["coordinator"]
```

---

## Development Setup

### Prerequisites

- Python 3.9 or higher
- git
- A code editor (VS Code recommended)

### Step 1: Clone and Navigate

```bash
git clone https://github.com/tsoiks/hacs_heliotherm.git
cd hacs_heliotherm
```

### Step 2: Create Virtual Environment

```bash
# Create
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements-dev.txt
```

This installs:
- `pytest`: Testing framework
- `pymodbus`: Modbus protocol library
- `black`: Code formatter
- `pylint`: Code linter
- `mypy`: Type checker
- `home-assistant`: Home Assistant core (for development)

### Step 4: Verify Setup

```bash
# Run tests
pytest tests/

# Run linters
black --check custom_components/heliotherm/
pylint custom_components/heliotherm/
mypy custom_components/heliotherm/
```

All should pass without errors.

---

## How to Extend the Code

### Task 1: Add a New Sensor

**Scenario**: You want to monitor a new parameter (e.g., compressor frequency)

**Steps**:

1. **Add descriptor to const.py**
   ```python
   # In SENSOR_DESCRIPTORS dict
   "compressor_frequency": SensorDescriptor(
       register=0x0150,              # Register address from protocol docs
       name="Compressor Frequency",
       scale=0.1,                    # Raw value × 0.1 = display value
       unit="Hz",
       device_class="frequency",     # Optional, for Home Assistant UI
   ),
   ```

2. **Add to coordinator's read list (if not already included)**
   ```python
   # In coordinator.py _async_update_data()
   # Usually already loops through all SENSOR_DESCRIPTORS, so no change needed
   # But verify the register is being read
   ```

3. **Test it**
   ```bash
   # Write a test in tests/test_sensor.py
   pytest tests/test_sensor.py::test_compressor_frequency -v
   ```

4. **Done!** The sensor is automatically created by `sensor.py` loop

**Key principle**: Add descriptor → Entity creation is automatic. No code changes to `sensor.py` needed.

### Task 2: Add a New Control (Switch)

**Scenario**: You want to control a pump that's on/off switchable

**Steps**:

1. **Add descriptor to const.py**
   ```python
   # In SWITCH_DESCRIPTORS dict
   "pump_enabled": SwitchDescriptor(
       register=0x0300,
       name="Pump Enabled",
       icon="mdi:pump",             # Optional icon
   ),
   ```

2. **Add read operation to coordinator.py**
   ```python
   # In _async_update_data() method
   # Add code to read the switch state
   switch_state = await self.async_read_register(0x0300)
   data["pump_enabled"] = bool(switch_state)
   ```

3. **Handle write operation in coordinator.py** (if needed)
   ```python
   # If async_write_register() doesn't handle your register, extend it:
   async def async_turn_on_pump(self):
       """Turn on the pump."""
       await self.async_write_register(0x0300, 1)
       # Refresh data after write
       await self.async_request_refresh()
   ```

4. **Update switch.py** (usually not needed)
   ```python
   # The generic HeliothermSwitch class handles most cases
   # Only needed if special logic is required (validation, etc.)
   ```

5. **Test it**
   ```bash
   pytest tests/test_sensor.py::test_pump_switch -v
   ```

### Task 3: Add a New Register Data Type

**Scenario**: Registers currently support int16 and float32, but you need uint32

**Steps**:

1. **Add to DataType enum in const.py**
   ```python
   class DataType(str, Enum):
       INT16 = "int16"
       FLOAT32 = "float32"
       UINT32 = "uint32"         # NEW
   ```

2. **Add parsing function to coordinator.py**
   ```python
   def _parse_uint32(self, registers: list[int]) -> int:
       """Parse two 16-bit registers as unsigned 32-bit integer."""
       # Combine two 16-bit values into one 32-bit value
       high = registers[0] & 0xFFFF
       low = registers[1] & 0xFFFF
       return (high << 16) | low
   ```

3. **Update register reading in coordinator.py**
   ```python
   # In _async_update_data()
   if data_type == DataType.UINT32:
       raw = await self.async_read_register(address, count=2)
       value = self._parse_uint32(raw)
   ```

4. **Add tests**
   ```bash
   pytest tests/test_coordinator.py::test_parse_uint32 -v
   ```

### Task 4: Modify Configuration Options

**Scenario**: Add a new config option for timeout duration

**Steps**:

1. **Add constant to const.py**
   ```python
   CONF_TIMEOUT = "timeout"
   DEFAULT_TIMEOUT = 5.0
   ```

2. **Update config schema in const.py**
   ```python
   # In CONFIG_SCHEMA
   vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_float,
   ```

3. **Use in coordinator.py**
   ```python
   # In __init__
   self.timeout = config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
   
   # In async_read_register()
   await asyncio.wait_for(
       client.read_holding_registers(...),
       timeout=self.timeout,
   )
   ```

4. **Update README.md** with new option
5. **Add tests**

---

## How to Maintain the Code

### Code Review Checklist

When reviewing pull requests, verify:

- [ ] New code follows existing patterns (descriptors, coordinator, etc.)
- [ ] All new functions have docstrings
- [ ] Type hints are present (mypy passes)
- [ ] Tests are included for new functionality
- [ ] Code is formatted with black
- [ ] Linting passes (pylint)
- [ ] No breaking changes to public APIs
- [ ] Documentation is updated (README, ADRs if needed)

### Updating for Home Assistant API Changes

When Home Assistant releases a breaking API change:

1. **Update imports** if entity base classes change
2. **Run tests**: `pytest tests/ -v`
3. **Test in Home Assistant**: Load component and verify entities appear
4. **Update manifest.json** if `homeassistant` version requirement changes
5. **Document changes** in commit message

### Handling Bug Reports

**Process**:

1. Reproduce the bug locally
2. Add a test that fails (demonstrates the bug)
3. Fix the code
4. Verify test passes
5. Add regression test to prevent reoccurrence

**Example**:
```python
# Test that demonstrates bug
def test_coordinator_timeout_on_slow_device():
    """Bug: Slow device causes coordinator to hang."""
    # Should timeout after 5 seconds, not hang forever
    coordinator = HeliothermModbusCoordinator(...)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            coordinator._async_update_data(),
            timeout=6.0,
        )
```

### Performance Optimization

Common bottlenecks:

1. **Many simultaneous register reads**
   - Solution: Use register ranges where possible
   - Example: Read 0x0100-0x010F (16 registers) instead of 16 separate reads

2. **Slow Modbus device**
   - Solution: Increase scan_interval in config
   - Solution: Use data caching for graceful degradation (already implemented)

3. **Frequent data updates causing UI flicker**
   - Solution: Increase scan_interval
   - Solution: Add state_class="measurement" to sensor descriptors for value smoothing

---

## Testing

### Testing Philosophy

- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test coordinator, setup, and entity creation
- **Mocking**: Mock Modbus client to avoid requiring real device

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_coordinator.py

# Run specific test function
pytest tests/test_coordinator.py::test_update_data -v

# Run with coverage report
pytest tests/ --cov=custom_components/heliotherm --cov-report=html
```

### Writing Tests

**Test structure**:
```python
# tests/test_new_feature.py
import pytest
from unittest.mock import MagicMock, patch

from custom_components.heliotherm.const import DOMAIN
from custom_components.heliotherm.coordinator import HeliothermModbusCoordinator

@pytest.fixture
def coordinator_fixture():
    """Create a test coordinator with mocked Modbus client."""
    with patch("custom_components.heliotherm.coordinator.AsyncModbusTcpClient"):
        coordinator = HeliothermModbusCoordinator(
            hass=MagicMock(),
            config_entry=MagicMock(data={
                "host": "192.168.1.100",
                "port": 502,
            }),
        )
    return coordinator

def test_new_feature(coordinator_fixture):
    """Test new feature."""
    coordinator = coordinator_fixture
    # Test code here
    assert coordinator is not None
```

### Test Coverage

Aim for >80% code coverage:
```bash
pytest tests/ --cov=custom_components/heliotherm --cov-report=term-missing
```

This shows which lines aren't tested.

---

## Code Quality

### Formatting with black

```bash
# Format all files
black custom_components/heliotherm/

# Format specific file
black custom_components/heliotherm/sensor.py

# Check without modifying
black --check custom_components/heliotherm/
```

**Style**: Line length 88 characters, double quotes for strings

### Linting with pylint

```bash
# Lint all files
pylint custom_components/heliotherm/

# Lint specific file
pylint custom_components/heliotherm/coordinator.py

# Generate detailed report
pylint custom_components/heliotherm/ --output-format=html > report.html
```

**Focus on**: Error, Warning, and Convention messages

### Type Checking with mypy

```bash
# Check all types
mypy custom_components/heliotherm/

# Strict mode (recommended)
mypy --strict custom_components/heliotherm/

# Show what's missing
mypy custom_components/heliotherm/ --no-implicit-reexport --warn-unused-ignores
```

**Focus on**: Avoiding `Any` types, adding explicit return types

### Pre-Commit Hook (Optional)

```bash
# Create .git/hooks/pre-commit
#!/bin/bash
set -e
black --check custom_components/heliotherm/
pylint custom_components/heliotherm/
mypy custom_components/heliotherm/
pytest tests/
```

Then make executable:
```bash
chmod +x .git/hooks/pre-commit
```

Now commits will fail if code quality checks don't pass.

---

## Debugging

### Enable Debug Logging

**In Home Assistant**:
```yaml
# configuration.yaml
logger:
  logs:
    custom_components.heliotherm: debug
    custom_components.heliotherm.coordinator: debug
```

Then restart Home Assistant and check logs: Settings → System → Logs

**In Development**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("heliotherm.coordinator").setLevel(logging.DEBUG)
```

### Common Issues

**Issue**: Coordinator never updates  
**Debug**:
```python
# In coordinator.py _async_update_data()
_LOGGER.debug("Update cycle started")
_LOGGER.debug(f"Read register 0x0100: {value}")
_LOGGER.debug(f"Final data: {data}")
```

**Issue**: Register values are wrong  
**Debug**:
```python
# Check raw vs. scaled values
raw = await self.async_read_register(address)
scaled = raw * descriptor.scale
_LOGGER.debug(f"Raw: {raw}, Scaled: {scaled}")
```

**Issue**: Entity not appearing  
**Debug**:
```python
# In sensor.py async_setup_entry()
_LOGGER.debug(f"Creating entities from {len(SENSOR_DESCRIPTORS)} descriptors")
for key, descriptor in SENSOR_DESCRIPTORS.items():
    _LOGGER.debug(f"Creating sensor: {key}")
```

### Using Python Debugger (pdb)

```python
# In any file
import pdb; pdb.set_trace()

# Execution pauses, can inspect variables:
# (Pdb) print(variable_name)
# (Pdb) continue
# (Pdb) next
# (Pdb) step
```

### Debugging in VS Code

Create `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "justMyCode": true
        }
    ]
}
```

Then: Run → Start Debugging (F5)

---

## Design Decisions

### Why Coordinator Pattern?

**Question**: Why not let each entity read directly from Modbus?

**Answer**: See [ADR-001: Coordinator Pattern](docs/adr/001-coordinator-pattern.md)

**Summary**:
- Single connection prevents network overhead
- Consistent data across entities
- Centralized error handling
- Home Assistant standard pattern

### Why Descriptor-Based Entities?

**Question**: Why not hardcode sensors in code?

**Answer**: See [ADR-004: Entity Design](docs/adr/004-entity-design.md)

**Summary**:
- Adding 100 sensors = 100 lines in const.py, not 1000 lines of code
- Single source of truth prevents bugs
- Type-safe register definitions
- Easy for others to contribute new sensors

### Why Read-Only Default?

**Question**: Why not allow write operations by default?

**Answer**: See [ADR-002: Read-Only vs. Write Mode](docs/adr/002-read-only-vs-write-mode.md)

**Summary**:
- Safe by default (fail-safe principle)
- Users must explicitly opt-in to control
- Prevents accidental device changes
- Still allows control for users who need it

### Why Modbus Abstraction?

**Question**: Why not use raw register numbers everywhere?

**Answer**: See [ADR-003: Modbus Abstraction](docs/adr/003-modbus-abstraction.md)

**Summary**:
- Register addresses easy to look up (semantic names)
- Changes to firmware versions easier to handle
- Testing easier with abstract register layer
- Data type conversions in one place

---

## Quick Reference

### Common Commands

```bash
# Format code
black custom_components/heliotherm/

# Run tests
pytest tests/ -v

# Check types
mypy custom_components/heliotherm/

# Lint
pylint custom_components/heliotherm/

# Do everything
black custom_components/heliotherm/ && \
mypy custom_components/heliotherm/ && \
pylint custom_components/heliotherm/ && \
pytest tests/ -v
```

### File Locations

| Task | File |
|------|------|
| Add sensor/switch | `const.py` (descriptor) + `coordinator.py` (if read logic needed) |
| Change configuration | `const.py` (schema) + `__init__.py` (usage) |
| Modify Modbus communication | `coordinator.py` |
| Change entity creation logic | `sensor.py` or `switch.py` |
| Add custom exceptions | `exceptions.py` |
| Add tests | `tests/test_*.py` |

### Key Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `HeliothermModbusCoordinator` | `coordinator.py` | Data management, Modbus communication |
| `HeliothermSensor` | `sensor.py` | Temperature, pressure, and other read-only values |
| `HeliothermSwitch` | `switch.py` | Controllable on/off devices (write mode only) |
| `SensorDescriptor` | `const.py` | Dataclass defining sensor entity metadata |
| `SwitchDescriptor` | `const.py` | Dataclass defining switch entity metadata |

---

## Contributing

Before submitting changes:

1. **Run all checks locally**
   ```bash
   black custom_components/heliotherm/ && \
   mypy custom_components/heliotherm/ && \
   pylint custom_components/heliotherm/ && \
   pytest tests/ -v
   ```

2. **Write descriptive commits**
   ```
   feat: Add compressor frequency sensor
   
   - Add SensorDescriptor to SENSOR_DESCRIPTORS
   - Register address 0x0150, scale 0.1
   - Device class: frequency
   - Add test for new sensor
   ```

3. **Create pull request** with description of changes
4. **Respond to review feedback** promptly

---

## Resources

- **[Architecture Decision Records](docs/adr/)** - Design decisions and rationale
- **[Modbus Protocol Guide](docs/MODBUS_PROTOCOL.md)** - Heliotherm register specification
- **[Home Assistant Development Docs](https://developers.home-assistant.io/)** - HA framework docs
- **[Python Type Hints](https://docs.python.org/3/library/typing.html)** - Type annotation reference

---

**Last Updated**: December 2025  
**For Questions**: Create an issue or discussion on GitHub
