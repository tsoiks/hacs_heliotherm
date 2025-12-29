# Heliotherm Home Assistant Component

A production-grade Home Assistant custom component for integrating Heliotherm heat pump systems via Modbus TCP protocol. Designed for monitoring and controlling heat pump parameters with safety-first defaults.

**Status**: Production-ready | **License**: Apache 2.0 | **Python**: 3.9+

> ⚠️ **AI-Generated Code**: This component was generated using AI assistance. It has not been validated against live Heliotherm hardware.
>
> **Use at Your Own Risk**: This component modifies critical heat pump parameters in write mode. Users are responsible for verifying functionality in their environment before production use. Test thoroughly in read-only mode first.

## Quick Start

### Installation

**Via HACS (Recommended)**
1. Open Home Assistant → HACS → Integrations
2. Add custom repository: `https://github.com/tsoiks/hacs_heliotherm`
3. Search "Heliotherm" and click Install
4. Restart Home Assistant
5. Go to Settings → Devices & Services → Create Integration → Heliotherm

**Manual Installation**
```bash
# Copy component to Home Assistant
cp -r custom_components/heliotherm ~/.homeassistant/custom_components/

# Restart Home Assistant
```

### Basic Configuration

Add to your `configuration.yaml`:

```yaml
heliotherm:
  host: 192.168.1.100       # IP address of Modbus server
  port: 502                  # Modbus TCP port (default: 502)
  slave_id: 1                # Modbus slave ID (default: 1)
  read_only: true            # Set to false for control mode (default: true)
  scan_interval: 30          # Seconds between updates (default: 30)
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `host` | string | ✓ | — | IP address or hostname of Modbus TCP server |
| `port` | integer | — | 502 | Modbus TCP port |
| `slave_id` | integer | — | 1 | Modbus slave ID |
| `read_only` | boolean | — | true | Enable write operations if false (control mode) |
| `scan_interval` | integer | — | 30 | Data refresh interval in seconds |

### Operating Modes

**Read-Only Mode** (default, safe)
- Sensors only (temperature, pressure, mode, etc.)
- No write operations or control capability
- Recommended for monitoring-only setups

**Write Mode** (read_only: false)
- All sensors plus switches and climate controls
- Allows adjusting setpoints and toggling equipment
- Requires careful configuration validation

## Features

✅ **Monitoring**: Real-time heat pump parameters (temperature, pressure, power)  
✅ **Control**: Optional write mode for setpoints and equipment control  
✅ **Reliable**: Centralized data coordinator with timeout protection and error recovery  
✅ **Extensible**: Descriptor-based entity definitions (add new sensors easily)  
✅ **Safe**: Read-only mode by default; write operations require explicit config  
✅ **Standards-compliant**: Follows Home Assistant best practices  

## Architecture Overview

This component uses production-grade patterns inspired by Sigenergy-Local-Modbus:

### Coordinator Pattern (ADR-001)
Single centralized coordinator manages all Modbus communication:
- **Connection pooling**: One reusable ModbusClient connection
- **Periodic polling**: Data fetched every 30 seconds (configurable)
- **Error resilience**: Timeout protection, data caching, automatic retries
- **Event-driven**: All entities notified when data updates

```
Coordinator (every 30s)
  ↓
  Read all registers from heat pump
  ↓
  Cache data in coordinator.data
  ↓
  Notify all subscribed entities
  ↓
  Home Assistant updates UI
```

### Descriptor-Based Entities (ADR-004)
Entities defined declaratively in `const.py`:

```python
# Single source of truth for entity definitions
SENSOR_DESCRIPTORS = {
    "supply_temperature": SensorDescriptor(
        register=0x0100,
        name="Supply Temperature",
        scale=0.1,
        unit="°C",
        device_class="temperature",
    ),
    # Add new sensors: just add one line above, entity creation is automatic
}
```

**Benefits:**
- Adding new sensors is 1-line change in `const.py`
- Type-safe register definitions
- No duplicate configuration across files
- Entity creation via simple loop in `sensor.py`

### Read-Only vs. Write Mode (ADR-002)
Configuration option controls exposed capabilities:

```yaml
heliotherm:
  read_only: true   # Sensors only
  # OR
  read_only: false  # Sensors + switches + climate entity
```

Implementation: Flag checked at setup time; entities conditionally created.

## Project Structure

```
custom_components/heliotherm/
├── __init__.py                # Integration setup and lifecycle
├── const.py                   # Configuration, register mappings, entity descriptors
├── coordinator.py             # Modbus communication, data caching, error handling
├── sensor.py                  # Read-only sensor entities (auto-created from descriptors)
├── switch.py                  # Control switch entities (only in write mode)
├── exceptions.py              # Custom exception types
└── manifest.json              # Component metadata

docs/
├── DEVELOPMENT_GUIDE.md       # How to extend and maintain the code
├── MODBUS_PROTOCOL.md         # Heliotherm register specification
└── adr/                       # Architecture Decision Records
    ├── 001-coordinator-pattern.md
    ├── 002-read-only-vs-write-mode.md
    ├── 003-modbus-abstraction.md
    └── 004-entity-design.md

tests/
├── test_coordinator.py        # Coordinator tests
├── test_init.py              # Setup and integration tests
└── test_sensor.py            # Entity tests
```

## For Developers

### Setting Up Development Environment

**Prerequisites**
- Python 3.9 or higher
- pip and venv

**Setup Steps**

```bash
# 1. Clone the repository
git clone https://github.com/tsoiks/hacs_heliotherm.git
cd hacs_heliotherm

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# OR
venv\Scripts\activate            # Windows

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Verify setup by running tests
pytest tests/

# 5. Run linters to check code quality
black custom_components/heliotherm/
pylint custom_components/heliotherm/
mypy custom_components/heliotherm/
```

### Quick Development Workflow

```bash
# Make code changes
# ... edit files ...

# Format code
black custom_components/heliotherm/

# Run tests
pytest tests/ -v

# Check types
mypy custom_components/heliotherm/

# Lint code
pylint custom_components/heliotherm/

# Create pull request with your changes
```

### Common Development Tasks

**Add a new sensor**
1. Open `custom_components/heliotherm/const.py`
2. Add descriptor to `SENSOR_DESCRIPTORS`:
   ```python
   "new_sensor": SensorDescriptor(
       register=0x0200,
       name="New Sensor",
       unit="unit",
   ),
   ```
3. Done! Entity created automatically in `sensor.py`

**Add a new switch (write mode)**
1. Open `custom_components/heliotherm/const.py`
2. Add descriptor to `SWITCH_DESCRIPTORS`:
   ```python
   "new_switch": SwitchDescriptor(
       register=0x0300,
       name="New Switch",
   ),
   ```
3. Update `coordinator.py` to handle the write operation
4. Done! Switch automatically created in `switch.py`

**Run specific tests**
```bash
pytest tests/test_coordinator.py -v
pytest tests/test_sensor.py::test_sensor_value -v
```

**Debug coordinator communication**
```python
# In coordinator.py, enable debug logging
import logging
logging.getLogger("heliotherm.coordinator").setLevel(logging.DEBUG)
```

For detailed developer documentation, see [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md).

## Key Concepts

### Coordinator Pattern
Central hub for all device communication. Prevents duplicate API calls, ensures consistent data across entities, handles errors uniformly. See [ADR-001](docs/adr/001-coordinator-pattern.md).

### Entity Descriptors
Type-safe, declarative entity definitions in `const.py`. Single source of truth for register addresses, units, scaling, and Home Assistant metadata. See [ADR-004](docs/adr/004-entity-design.md).

### Modbus Abstraction
Register operations abstracted in `coordinator.py` with timeout protection, connection pooling, and error recovery. See [ADR-003](docs/adr/003-modbus-abstraction.md).

### Read-Only Safety
Safe default (read_only: true) ensures monitoring-only installations cannot accidentally send write commands. See [ADR-002](docs/adr/002-read-only-vs-write-mode.md).

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=custom_components/heliotherm --cov-report=html

# Run specific test file
pytest tests/test_coordinator.py -v

# Run tests matching pattern
pytest tests/ -k "temperature" -v
```

Tests use pytest fixtures and mocking to avoid requiring a real Modbus device.

## Code Quality

This project enforces code quality standards:

**Code Formatting** (black)
```bash
black custom_components/heliotherm/
```

**Linting** (pylint)
```bash
pylint custom_components/heliotherm/
```

**Type Checking** (mypy)
```bash
mypy custom_components/heliotherm/
```

**Run All Checks**
```bash
black --check custom_components/heliotherm/ && \
pylint custom_components/heliotherm/ && \
mypy custom_components/heliotherm/ && \
pytest tests/
```

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/description`)
3. Make your changes and add tests
4. Run linters and tests locally
5. Commit with descriptive messages
6. Push to your fork and open a pull request

**Before contributing**, review:
- [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for development practices
- [docs/adr/](docs/adr/) for architectural decisions
- Existing code for patterns and style

## Troubleshooting

**Connection Timeout**
- Verify heat pump IP address is correct
- Check network connectivity: `ping 192.168.1.100`
- Ensure Modbus TCP is enabled on heat pump
- Check firewall isn't blocking port 502

**Entities Not Appearing**
- Check Home Assistant logs: `Settings → System → Logs`
- Verify `read_only: false` if expecting switches/controls
- Restart Home Assistant after config changes

**Write Operations Not Working**
- Confirm `read_only: false` in configuration
- Check Home Assistant logs for permission errors
- Verify heat pump accepts commands on that register

For detailed logs, enable debug mode:
```yaml
logger:
  logs:
    custom_components.heliotherm: debug
```

## Resources

- **[Home Assistant Integration Documentation](https://developers.home-assistant.io/)** - HA development guide
- **[Modbus Protocol Guide](docs/MODBUS_PROTOCOL.md)** - Heliotherm register reference
- **[Architecture Decision Records](docs/adr/)** - Design rationale and decisions
- **[Heliotherm Documentation](docs/Modbus-Doku_DE.pdf)** - Original manufacturer documentation

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/tsoiks/hacs_heliotherm/issues)
- **Questions**: Create an issue with label `question`
- **Feature Requests**: Create an issue with label `enhancement`

---

**Last Updated**: December 2025 | **Version**: 1.0.0
