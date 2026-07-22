"""Mission Control — read-only operator UI shell (H-7.1).

Presentation only. Never evaluates engines, never mutates runtime.
"""

from hotirjam_ai5.mission_control.app import MissionControlApp, main
from hotirjam_ai5.mission_control.catalog import MODULE_CATALOG, ModuleGroup
from hotirjam_ai5.mission_control.models import MissionWindow
from hotirjam_ai5.mission_control.runtime_bundle import RuntimeBundle
from hotirjam_ai5.mission_control.shell import MissionControlShell

__all__ = [
    "MODULE_CATALOG",
    "MissionControlApp",
    "MissionControlShell",
    "MissionWindow",
    "ModuleGroup",
    "RuntimeBundle",
    "main",
]
