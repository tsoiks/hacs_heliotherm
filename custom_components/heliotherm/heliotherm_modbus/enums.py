"""Coded Modbus values of the Heliotherm heat pump.

The meaning of each code is taken from the official Heliotherm Modbus
documentation (RCG X register list, STAND 31.10.2019), except where a comment
says otherwise.
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["CompressorDemand"]


class CompressorDemand(IntEnum):
    """Register 41: the heat pump's current compressor demand.

    The official documentation defines 0, 10, 20 and 30; 40 (external
    demand) was observed on real devices by the community but is not in
    the PDFs. A value outside this enum decodes to ``None``.
    """

    NONE = 0
    COOLING = 10
    HEATING = 20
    DOMESTIC_HOT_WATER = 30
    EXTERNAL = 40
