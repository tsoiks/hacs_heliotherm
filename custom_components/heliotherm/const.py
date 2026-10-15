"""Constants for the Heliotherm integration."""

from homeassistant.const import CONF_SCAN_INTERVAL

DOMAIN = "heliotherm"
MANUFACTURER = "Heliotherm"
MODEL = "Heat pump (RCG)"

DEFAULT_NAME = "Heliotherm"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 30

CONF_UNIT_ID = "unit_id"

__all__ = [
    "CONF_UNIT_ID",
    "CONF_SCAN_INTERVAL",
    "DEFAULT_NAME",
    "DEFAULT_PORT",
    "DEFAULT_SCAN_INTERVAL",
    "DEFAULT_UNIT_ID",
    "DOMAIN",
    "MANUFACTURER",
    "MODEL",
]
