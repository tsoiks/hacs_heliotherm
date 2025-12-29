"""
Custom exceptions for Heliotherm integration.

TODO: Add custom exceptions as needed for better error handling
"""


class HeliotermException(Exception):
    """Base exception for Heliotherm integration."""

    pass


class HeliotermConnectionError(HeliotermException):
    """Failed to connect to Modbus server."""

    pass


class HeliotermModbusError(HeliotermException):
    """Modbus protocol error."""

    pass


class HeliotermInvalidValue(HeliotermException):
    """Invalid value for write operation (out of range, etc)."""

    pass
