# ADR-002: Read-Only vs. Write Mode Configuration

**Date**: 2025-12-28  
**Status**: Accepted  
**Participants**: Core Team

## Context

Different users have different security and control requirements:

1. **Some users** want read-only monitoring (no risk of accidentally changing settings)
2. **Other users** need to control the heat pump (adjust temperatures, change modes)
3. **Integration complexity** varies:
   - Read-only: Simple sensors
   - Write mode: Sensors + switches + climate entity + validation
4. **Safety concern**: Write operations require careful validation to prevent invalid state

The question: How should we support both modes without code duplication?

## Decision

We implement a **configuration-based mode selection** via the `read_only` config option:

```yaml
heliotherm:
  host: 192.168.1.100
  read_only: true   # or false for write mode
```

**Entity Creation Logic:**
```python
# Always created
- SensorEntity (temperature, pressure, mode, etc.)

# Only if read_only = false
- SwitchEntity (on/off controls)
- ClimateEntity (thermostat)
- Service calls for advanced operations
```

**Implementation:**
1. Configuration is validated at setup time
2. A flag `hass.data[DOMAIN]["write_enabled"]` is set based on config
3. Each entity setup function checks this flag
4. Coordinator supports both read and write operations (writes are no-op if disabled)

## Rationale

**Why Configuration-Based Modes?**

1. **Single Codebase**: One set of classes handles both modes
2. **User Choice**: Different users, different needs
3. **Safety by Default**: `read_only: true` is the default
4. **Future-Proof**: Easy to add write-only mode later if needed
5. **Testing**: Both modes can be tested in same environment

**Example Implementation:**
```python
# In __init__.py
async def async_setup_entry(hass, entry):
    read_only = entry.data.get(CONF_READ_ONLY, True)
    hass.data[DOMAIN]["write_enabled"] = not read_only
    
    # Setup always happens
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    # Optional setup based on mode
    if not read_only:
        await hass.config_entries.async_forward_entry_setups(
            entry, ["switch", "climate"]
        )
```

## Consequences

**Positive:**
- Users can choose appropriate security level
- Single code path for shared logic (coordinator, sensors)
- Safe default (read-only)
- No runtime overhead for read-only users
- Clear separation of concerns

**Negative:**
- More code paths to test
- Configuration documentation is critical
- Users might enable write mode by mistake
- Validation logic adds complexity

**Mitigation:**
- Clear warnings in logs when write mode is enabled
- Comprehensive input validation in coordinator
- Good test coverage for both modes
- Configuration schema with helper text

## Alternatives Considered

### 1. Separate Components
**Approach**: `heliotherm_readonly` and `heliotherm_readwrite` components  
**Pros**: 
- Clear separation  
**Cons**: 
- Code duplication
- Confusing for users
- Maintenance burden

### 2. Always Support Both
**Approach**: Write entities always available, no config option  
**Pros**: 
- Most flexible  
**Cons**: 
- Safety issue (users might accidentally control device)
- More complex validation
- Potential for misuse

### 3. Role-Based Entities
**Approach**: Users select which specific entities are writable  
**Pros**: 
- Fine-grained control  
**Cons**: 
- Complex configuration schema
- Harder to understand
- Validation becomes entity-specific

**We chose Configuration-Based Modes** because it balances flexibility, safety, and simplicity.

## Related ADRs

- [ADR-001](001-coordinator-pattern.md): Coordinator manages both read and write operations
- [ADR-003](003-modbus-abstraction.md): Write validation happens in coordinator

## References

- Code: `custom_components/heliotherm/__init__.py` (mode setup)
- Code: `custom_components/heliotherm/switch.py` (write entities)
- Configuration schema in `const.py`
