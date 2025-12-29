# ADR-004: Entity Design and Configuration

**Date**: 2025-12-28  
**Status**: Accepted  
**Participants**: Core Team

## Context

The component needs to expose many different parameters as entities (temperature, pressure, mode, etc.). Requirements:

1. **Declarative**: Define entities via data (not imperative code)
2. **Consistent**: All sensors should follow the same pattern
3. **Maintainable**: Easy to add new entities
4. **Home Assistant Compliant**: Use standard entity patterns
5. **Device Integration**: Entities should be grouped under a device

Current challenge: Manually creating 20+ entities in code is tedious and error-prone.

## Decision

We use **EntityDescription-based entity creation**:

1. **Define Entities Declaratively** in `const.py`:
   ```python
   SENSOR_DESCRIPTIONS = (
       SensorEntityDescription(
           key="supply_temperature",
           name="Supply Temperature",
           native_unit_of_measurement=UnitOfTemperature.CELSIUS,
           device_class=SensorDeviceClass.TEMPERATURE,
           state_class=SensorStateClass.MEASUREMENT,
           icon="mdi:thermometer",
       ),
       SensorEntityDescription(
           key="setpoint_temperature",
           name="Setpoint",
           native_unit_of_measurement=UnitOfTemperature.CELSIUS,
           device_class=SensorDeviceClass.TEMPERATURE,
       ),
       # ... more sensors
   )
   ```

2. **Create Entities Dynamically** in `sensor.py`:
   ```python
   async def async_setup_entry(hass, entry, async_add_entities):
       coordinator = hass.data[DOMAIN][entry.entry_id]
       
       entities = [
           HeliotermSensor(coordinator, description)
           for description in SENSOR_DESCRIPTIONS
       ]
       async_add_entities(entities)
   ```

3. **Generic Sensor Class**:
   ```python
   class HeliotermSensor(CoordinatorEntity, SensorEntity):
       entity_description: SensorEntityDescription
       
       def __init__(self, coordinator, description):
           self.coordinator = coordinator
           self.entity_description = description
           self._attr_unique_id = f"heliotherm_{description.key}"
       
       @property
       def native_value(self):
           return self.coordinator.data.get(self.entity_description.key)
   ```

## Rationale

**Why EntityDescription Pattern?**

1. **Less Code**: Metadata separate from entity logic
2. **Consistency**: All entities follow same pattern
3. **Home Assistant Standard**: This is the recommended approach
4. **Easy Testing**: Can test entity descriptions independently
5. **Localization**: Names can be externalized for translation

**Example: Adding a New Sensor**

Before (imperative):
```python
# Must write a new class for each sensor
class SupplyTemperatureSensor(CoordinatorEntity, SensorEntity):
    unique_id = "heliotherm_supply_temp"
    name = "Supply Temperature"
    ...

class SetpointTemperatureSensor(CoordinatorEntity, SensorEntity):
    unique_id = "heliotherm_setpoint_temp"
    name = "Setpoint"
    ...
```

After (declarative):
```python
# Just add to tuple
SENSOR_DESCRIPTIONS = (
    # ... existing sensors
    SensorEntityDescription(
        key="supply_temperature",
        name="Supply Temperature",
    ),
)
```

## Consequences

**Positive:**
- Minimal code per entity
- Easy to add new entities
- Consistent entity behavior
- Better readability
- Easier to maintain
- Follows Home Assistant patterns

**Negative:**
- EntityDescription API must be learned
- Less flexibility per entity (though rarely needed)
- Initial setup requires understanding the pattern

**Mitigation:**
- Provide well-commented examples
- Use type hints for IDE autocomplete
- Document the pattern in onboarding guide

## Entity Types

This pattern applies to all entity types:

```python
# Sensors (read-only)
SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(...),
)

# Binary Sensors (on/off)
BINARY_SENSOR_DESCRIPTIONS = (
    BinarySensorEntityDescription(...),
)

# Switches (controllable on/off)
SWITCH_DESCRIPTIONS = (
    SwitchEntityDescription(...),
)

# Climate (thermostat)
# Note: Climate uses custom approach (see climate.py)
```

## Device Integration

All entities are linked to a device:

```python
class HeliotermSensor(CoordinatorEntity, SensorEntity):
    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name="Heliotherm Heat Pump",
            manufacturer="Heliotherm",
            model=self.coordinator.device_model,
        )
```

This groups all entities under one device in Home Assistant UI.

## Entity Keys and Data Mapping

The `key` in EntityDescription must match data in `coordinator.data`:

```python
# In const.py - definition
SensorEntityDescription(key="supply_temperature", ...)

# In coordinator.py - data update
async def _async_update_data(self):
    return {
        "supply_temperature": await self.read_supply_temperature(),
        "setpoint_temperature": await self.read_setpoint_temperature(),
        # ... more data
    }

# In sensor.py - entity uses key
@property
def native_value(self):
    return self.coordinator.data.get(self.entity_description.key)
```

## Alternatives Considered

### 1. Imperative Entity Creation
**Approach**: Create each entity class manually  
**Pros**: 
- Maximum flexibility  
**Cons**: 
- Code duplication
- Hard to maintain
- Inconsistent behavior

### 2. YAML Configuration
**Approach**: Users define entities in YAML config  
**Pros**: 
- User customizable  
**Cons**: 
- Complex validation
- Hard to provide defaults
- Not standard for custom components

### 3. Dynamic Template Approach
**Approach**: Use Python metaprogramming to generate classes  
**Pros**: 
- Compact code  
**Cons**: 
- Hard to debug
- Unclear to readers
- Not recommended by HA

**We chose EntityDescription Pattern** because it's the Home Assistant standard and provides excellent balance of simplicity and flexibility.

## Related ADRs

- [ADR-001](001-coordinator-pattern.md): Entities subscribe to coordinator updates
- [ADR-002](002-read-only-vs-write-mode.md): Conditional entity creation based on mode

## References

- [Home Assistant EntityDescription Pattern](https://developers.home-assistant.io/docs/entity_description/)
- Code: `custom_components/heliotherm/const.py` (entity descriptions)
- Code: `custom_components/heliotherm/sensor.py` (sensor implementation)
- Code: `custom_components/heliotherm/switch.py` (switch implementation)
