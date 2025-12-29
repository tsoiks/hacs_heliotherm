# ADR-001: Use Coordinator Pattern for Data Management

**Date**: 2025-12-28  
**Status**: Accepted  
**Participants**: Core Team

## Context

The Heliotherm component needs to communicate with a Modbus TCP server to read heat pump parameters. Initial challenges include:

1. **Multiple entities** (sensors, switches, climate) all need the same data
2. **Frequent polling** could lead to many simultaneous Modbus requests
3. **Error handling** must be consistent across all components
4. **Data freshness** - consumers need up-to-date information, but not excessively so
5. **Home Assistant integration** - need to follow established patterns

Home Assistant provides `DataUpdateCoordinator` as a standard pattern for handling these challenges.

## Decision

We will use the `DataUpdateCoordinator` pattern for all data management:

1. **Single Coordinator Instance** per integration entry
   - Manages Modbus TCP client lifecycle
   - Executes periodic data updates
   - Maintains cached data

2. **Entities Subscribe to Coordinator**
   - `SensorEntity`, `SwitchEntity`, `ClimateEntity` classes inherit from `CoordinatorEntity`
   - Entities automatically receive updates when coordinator refreshes data
   - No direct Modbus communication from entities

3. **Centralized Error Handling**
   - Coordinator handles connection errors, timeouts, Modbus exceptions
   - Errors are raised as `UpdateFailed` exception
   - Home Assistant handles the retry logic (exponential backoff, etc.)

## Rationale

**Why Coordinator Pattern?**

1. **Efficiency**: One Modbus client, one poll cycle, all entities updated together
2. **Consistency**: All entities see the same data snapshot
3. **Reliability**: Centralized error handling and retry logic
4. **Home Assistant Standard**: Follows established best practice; familiar to HA maintainers
5. **Simplicity**: Entities are passive subscribers, not active requesters

**Example Flow:**
```
Timer Event (every 30s)
    ↓
Coordinator._async_update_data()
    ↓
Modbus Client Read Registers
    ↓
Coordinator.data = {temp: 20.5, mode: "heat", ...}
    ↓
All CoordinatorEntity subscribers notified
    ↓
Entity.async_update_listeners() called
    ↓
Home Assistant detects state changes
    ↓
Automations triggered, UI updated
```

## Consequences

**Positive:**
- Single source of truth for device data
- Automatic retry logic on transient failures
- Simplified entity code (no communication logic)
- Built-in Home Assistant support for coordinator pattern
- Easier to debug (central point for logging)
- Scales well with many entities

**Negative:**
- All entities depend on one coordinator
- If coordinator fails, all entities become unavailable
- Update lag: entities only refresh on coordinator cycles (not immediately responsive)
- Complex coordinator setup code (must handle initialization, errors, etc.)

**Mitigation:**
- Ensure robust error handling in coordinator
- Provide fast `refresh()` option for write operations
- Add logging/monitoring for coordinator health

## Alternatives Considered

### 1. Individual Entity Updates
**Approach**: Each entity calls Modbus client directly  
**Pros**: 
- Entities are independent
- More responsive (no polling lag)  
**Cons**: 
- Multiple simultaneous Modbus calls (network overhead)
- Inconsistent data (entities read at different times)
- Duplicate error handling in each entity
- Poor Home Assistant integration

### 2. Async Event Bus
**Approach**: Entities subscribe to Modbus client via event bus  
**Pros**: 
- Decoupled communication  
**Cons**: 
- More complex code
- Harder to debug
- Still doesn't solve duplication of requests
- Not a standard HA pattern

### 3. Request Queue
**Approach**: Queue all requests, process in order  
**Pros**: 
- Ordered execution  
**Cons**: 
- Increased latency
- Complex state management
- Overhead for small operations

**We chose Coordinator Pattern** because it's the Home Assistant standard, solves all our problems, and simplifies entity code.

## Related ADRs

- [ADR-002](002-read-only-vs-write-mode.md): Coordinator supports both read and write modes
- [ADR-003](003-modbus-abstraction.md): Modbus communication details are abstracted in coordinator

## References

- [Home Assistant DataUpdateCoordinator Documentation](https://developers.home-assistant.io/docs/integration_fetching_data)
- [Modbus Integration (HA)](https://github.com/home-assistant/core/tree/dev/homeassistant/components/modbus)
- Code: `custom_components/heliotherm/coordinator.py`
