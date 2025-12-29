# ADR-003: Modbus Register Abstraction

**Date**: 2025-12-28  
**Status**: Accepted  
**Participants**: Core Team

## Context

The component communicates with Heliotherm heat pumps via Modbus TCP protocol. Key challenges:

1. **Register Knowledge**: Different parameters live at different register addresses
2. **Data Types**: Some values are integers, others floats; some are in Celsius, others in tenths
3. **Versioning**: Different Modbus firmware versions might have different register layouts
4. **Testing**: Hard to test without a real device or mock Modbus server
5. **Documentation**: Modbus register specs are in external documentation (PDF)
6. **Code Clarity**: Raw register numbers throughout code are confusing

Example:
```
Register 100: Supply temperature (format: IEEE 754 float)
Register 102: Setpoint temperature (format: integer, 0.1°C resolution)
Register 200: On/off switch (values: 0=off, 1=on)
```

## Decision

We implement a **centralized register abstraction layer**:

1. **Register Mapping** in `const.py`:
   ```python
   # Semantic naming, not raw addresses
   REGISTER_SUPPLY_TEMP = 100      # °C as IEEE 754 float
   REGISTER_SETPOINT_TEMP = 102    # 0.1°C resolution as int16
   REGISTER_PUMP_ENABLED = 200     # Boolean: 0=off, 1=on
   ```

2. **Register Metadata**:
   ```python
   REGISTER_INFO = {
       "supply_temp": {
           "address": 100,
           "type": "float32",  # IEEE 754
           "unit": "celsius",
           "access": "read",
           "description": "Supply temperature from heat pump",
       },
       "setpoint_temp": {
           "address": 102,
           "type": "int16",
           "scale": 0.1,
           "unit": "celsius",
           "access": "read_write",
           "valid_range": [5, 30],
           "description": "Thermostat setpoint",
       },
   }
   ```

3. **Parse/Format Functions** in `coordinator.py`:
   ```python
   def _parse_float(self, data: List[int]) -> float:
       """Convert Modbus bytes to IEEE 754 float."""
       import struct
       return struct.unpack('>f', bytes(data))[0]
   
   def _parse_temp_scaled(self, data: List[int]) -> float:
       """Convert scaled integer to temperature."""
       return data[0] * 0.1  # 0.1°C resolution
   
   def _format_temp_scaled(self, temp: float) -> int:
       """Convert temperature to scaled integer."""
       return int(temp * 10)  # 10x for 0.1°C resolution
   ```

4. **Type-Safe Operations**:
   ```python
   async def read_supply_temperature(self) -> float:
       """Read supply temp using abstraction."""
       raw = await self.modbus_client.read_holding_registers(
           address=REGISTER_SUPPLY_TEMP,
           count=2,
       )
       return self._parse_float(raw)
   
   async def write_setpoint(self, temp: float) -> None:
       """Write setpoint using abstraction."""
       value = self._format_temp_scaled(temp)
       await self.modbus_client.write_register(
           address=REGISTER_SETPOINT_TEMP,
           value=value,
       )
   ```

## Rationale

**Why Abstraction?**

1. **Readability**: `read_supply_temperature()` vs. `read_registers(100, 2)`
2. **Maintainability**: Register address change? Update in one place
3. **Type Safety**: Parsing logic is centralized, not scattered
4. **Documentation**: Register info is self-documenting
5. **Testing**: Mock register reads/writes at abstraction level
6. **Firmware Updates**: Easy to add version-specific register handling

**Example: What Changes?**

Old approach (no abstraction):
```python
# Scattered throughout code
data = await self.modbus_client.read_holding_registers(100, 2)
supply_temp = struct.unpack('>f', bytes(data))[0]
```

New approach (with abstraction):
```python
# Clear, centralized
supply_temp = await self.coordinator.read_supply_temperature()
```

## Consequences

**Positive:**
- Code is more readable and maintainable
- Register information is documented in one place
- Parsing logic is centralized and tested
- Easy to add new registers
- Firmware version handling is possible
- Better error messages (semantic names)

**Negative:**
- Initial setup takes more time
- Register info file must be kept in sync with Modbus spec
- Abstraction adds slight performance overhead (negligible)
- More code to maintain

**Mitigation:**
- Document register sources (reference Modbus-Doku_DE.pdf)
- Include version info in register metadata
- Add validation tests for register mappings
- Use enums for well-known values

## Alternatives Considered

### 1. Raw Modbus Access
**Approach**: No abstraction, use register addresses directly  
**Pros**: 
- Minimal code  
**Cons**: 
- Scattered logic
- Hard to maintain
- Prone to bugs

### 2. Dynamic Register Discovery
**Approach**: Query device for register information  
**Pros**: 
- No manual mapping needed  
**Cons**: 
- Not all devices support this
- Adds complexity
- Slower initialization

### 3. ORM-Style Mapping
**Approach**: Object-relational mapping for registers (similar to database ORMs)  
**Pros**: 
- Very powerful  
**Cons**: 
- Overkill for this use case
- Performance overhead
- Learning curve

**We chose Register Abstraction** because it provides clarity and maintainability with acceptable complexity.

## Implementation Details

### Register Metadata Format

```python
REGISTER_INFO = {
    "parameter_name": {
        "address": 100,                    # Modbus register address
        "type": "float32|int16|int32",    # Data type
        "scale": 0.1,                      # Optional: multiply by this
        "offset": 0,                       # Optional: add this
        "unit": "celsius|percent|enum",   # Unit of measurement
        "access": "read|write|read_write", # Access mode
        "valid_range": [min, max],        # Optional: validation range
        "description": "...",              # Human-readable description
        "version": ">= 2.5",              # Optional: firmware version
    },
}
```

### Parsing Strategy

```python
def _parse_value(self, data: List[int], info: Dict) -> Any:
    """Generic parser using register info."""
    parsed = self._parse_by_type(data, info["type"])
    
    if "scale" in info:
        parsed *= info["scale"]
    
    if "offset" in info:
        parsed += info["offset"]
    
    return parsed
```

## Related ADRs

- [ADR-001](001-coordinator-pattern.md): Coordinator uses this abstraction
- [ADR-002](002-read-only-vs-write-mode.md): Write operations use abstraction for validation

## References

- Code: `custom_components/heliotherm/const.py` (register definitions)
- Code: `custom_components/heliotherm/coordinator.py` (parse/format functions)
- Docs: `docs/MODBUS_PROTOCOL.md` (register mapping details)
- Source: `docs/Modbus-Doku_DE.pdf` (Heliotherm Modbus specification)
