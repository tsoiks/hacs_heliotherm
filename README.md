# Heliotherm for Home Assistant

A Home Assistant integration for Heliotherm heat pumps, speaking Modbus TCP
through the heat pump's Remote Control Gateway (RCG).

The integration is built on Home Assistant's new `modbus` support: it asks
the `modbus` integration for a unit on a shared connection, so it never
competes with another integration for the same bus.

## Requirements

- A Heliotherm heat pump with a Remote Control Gateway (RCG)
- Modbus TCP enabled on the RCG (its web interface: Service login →
  Grundbedienung/Grundeinstellung → Modbus → TCP → on, then restart)
- Home Assistant 2026.9 or newer

## Installation

### HACS

1. Add this repository to HACS as a custom repository
2. Install the "Heliotherm" integration
3. Restart Home Assistant
4. Settings → Devices & Services → Add Integration → Heliotherm

### Manual

Copy `custom_components/heliotherm` into the `custom_components`
directory of your Home Assistant configuration and restart.

## Entities

The integration is read-only and exposes the heat pump's complete input
register map:

- **Sensors** (33): all temperatures (outside, supply, return, buffer,
  source, refrigerant circuit), pressures (low/high), flow rate, compressor
  speed setpoint, COP, expansion valve, compressor demand, electric and
  thermal power, lifetime energy counters (heating / hot water / total),
  and operating hour counters
- **Binary sensors** (8): heating circuit pump, buffer charge pump,
  compressor, fault, four-way valve (defrost), source pump or fan,
  domestic hot water priority, passive cooling valve

Values for sensors that are not installed decode to "unknown". Register 32
(EVU) is intentionally not exposed — its semantics are contradictory in the
official documents.

The poll interval can be changed in the integration's options (default:
30 seconds).

## Status and validation

The register map comes from the official Heliotherm Modbus documentation
(RCG X register list, STAND 31.10.2019). The v1 read map, the decode
scales, and the 32-bit word order (high word first) were validated by a
read-only live test against a real heat pump (RCG 2.3.1.0). Use at your
own risk; report findings via issues.

Write support (operating mode, setpoints) is planned as an explicit opt-in
mode in a later release.

## Optional: ready-made dashboard

A small, curated dashboard for the integration lives in
[`dashboards/heat-pump.yaml`](dashboards/heat-pump.yaml): status, the four
key temperatures, hourly power and daily energy charts, and a compact
diagnostics section. It uses only built-in cards — no additional
downloads.

To use it:

1. Replace every `heliotherm_XXX` in the file with your entity prefix
   (derived from the device name — an RCG at `192.168.0.100` gives
   `heliotherm_192_168_0_100`; copy it from any entity ID on the device page)
2. Settings → Dashboards → **+ Add dashboard** → **Start from scratch**
3. Open the new dashboard → three-dot menu → **Edit in YAML** → paste the
   file → **Save**
4. Optionally make it your default dashboard via your profile menu

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install homeassistant modbus-connection pytest \
  pytest-homeassistant-custom-component ruff
pytest tests/
ruff check custom_components tests
```

The device library is vendored under
`custom_components/heliotherm/heliotherm_modbus` and is Home
Assistant-agnostic: it is built on the `modbus-connection` modelling
framework and can be exercised with that library's mock backend, which the
test suite does.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
