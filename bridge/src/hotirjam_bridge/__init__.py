"""HOTIRJAM Bridge — transport-only package (Phase M1 design).

Does not import hotirjam_ai5 AI engines.
Does not place orders.
"""

from hotirjam_bridge.contracts import (
    BRIDGE_PROTOCOL_VERSION,
    Channel,
    ControlType,
    Envelope,
)
from hotirjam_bridge.sender import TickSenderRuntime

__all__ = [
    "BRIDGE_PROTOCOL_VERSION",
    "Channel",
    "ControlType",
    "Envelope",
    "TickSenderRuntime",
]

__version__ = "0.1.0-design"
