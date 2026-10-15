"""The config flow: connection details are collected, validated, probed."""

from __future__ import annotations

from contextlib import ExitStack, asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import NumberSelector
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from custom_components.heliotherm.const import CONF_UNIT_ID, DOMAIN

from .conftest import HOST, INPUT_REGISTERS, UNIT_ID

USER_INPUT: dict[str, Any] = {
    CONF_HOST: HOST,
    CONF_PORT: 502,
    CONF_UNIT_ID: UNIT_ID,
}


def _mock_unit() -> MockModbusUnit:
    """A mock unit seeded like a heating heat pump."""
    connection = MockModbusConnection()
    unit = connection.for_unit(UNIT_ID)
    unit.input = dict(INPUT_REGISTERS)
    return unit


def _patched_temporary_unit(unit: MockModbusUnit) -> Any:
    """Patch the probe's temporary unit and setup's unit with the mock."""
    @asynccontextmanager
    async def fake_temporary_unit(hass, params, unit_id):
        yield unit

    @contextmanager
    def combined() -> Any:
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "custom_components.heliotherm.config_flow"
                    ".async_get_temporary_unit",
                    fake_temporary_unit,
                )
            )
            stack.enter_context(
                patch(
                    "custom_components.heliotherm.async_get_unit",
                    return_value=unit,
                )
            )
            yield

    return combined()


async def test_form(hass: Any, enable_custom_integrations: None) -> None:
    """The flow shows a form first."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert set(result["data_schema"].schema) == {CONF_HOST, CONF_PORT, CONF_UNIT_ID}


async def test_successful_flow(
    hass: Any, enable_custom_integrations: None
) -> None:
    """A heat pump that answers creates an entry."""
    with _patched_temporary_unit(_mock_unit()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == f"{HOST}_502_{UNIT_ID}"
    assert entry.title == f"Heliotherm ({HOST})"
    assert entry.data == USER_INPUT


async def test_probe_failure_shows_error(
    hass: Any, enable_custom_integrations: None
) -> None:
    """A heat pump that does not answer shows a connection error."""
    unit = _mock_unit()
    unit.fail_read(10, ModbusTimeoutError("no answer"), register_type="input")
    with _patched_temporary_unit(unit):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("user_input", "field"),
    [
        ({**USER_INPUT, CONF_HOST: ""}, CONF_HOST),
        ({**USER_INPUT, CONF_PORT: 0}, CONF_PORT),
        ({**USER_INPUT, CONF_UNIT_ID: -1}, CONF_UNIT_ID),
    ],
)
async def test_invalid_input_shows_error(
    hass: Any, enable_custom_integrations: None, user_input: dict, field: str
) -> None:
    """Out-of-range values are rejected before any probe."""
    with _patched_temporary_unit(_mock_unit()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=user_input
        )
    assert result["type"] == FlowResultType.FORM
    assert field in result["errors"], user_input


async def test_unit_id_selector_is_a_number_box(
    hass: Any, enable_custom_integrations: None
) -> None:
    """The unit ID renders as a plain number box, not a slider."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    schema = result["data_schema"].schema
    selector = schema[
        next(key for key in schema if key.schema == "unit_id")
    ]
    assert isinstance(selector, NumberSelector)
    assert selector.config["mode"] == "box"
    assert selector.config["min"] == 0
    assert selector.config["max"] == 255


async def test_unit_id_float_is_normalized(
    hass: Any, enable_custom_integrations: None
) -> None:
    """A whole-number float from the number box is stored as an int."""
    with _patched_temporary_unit(_mock_unit()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={**USER_INPUT, CONF_UNIT_ID: 1.0},
        )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data[CONF_UNIT_ID] == 1
    assert isinstance(entry.data[CONF_UNIT_ID], int)
    assert entry.unique_id == f"{HOST}_502_{UNIT_ID}"


async def test_duplicate_is_rejected(
    hass: Any, enable_custom_integrations: None
) -> None:
    """The same heat pump cannot be added twice."""
    with _patched_temporary_unit(_mock_unit()):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )
        await hass.async_block_till_done()
        assert first["type"] == FlowResultType.CREATE_ENTRY
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )
        await hass.async_block_till_done()
    assert second["type"] == FlowResultType.ABORT
    assert second["reason"] == "already_configured"
