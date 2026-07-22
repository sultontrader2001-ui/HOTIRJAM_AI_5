"""H-8.0 Observation layer — live market observation & certification.

Read-only consumer of published snapshots / ValidatorFrame.
Never trades. Never sends orders. Never modifies RuntimeHub, AI, or Decision.
"""

from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.observation.report import CertificationReport, build_certification_report
from hotirjam_ai5.observation.session import ObservationSession

__all__ = [
    "CertificationReport",
    "ObservationCycle",
    "ObservationSession",
    "build_certification_report",
    "main",
]


def __getattr__(name: str):
    if name == "main":
        from hotirjam_ai5.observation.app import main as _main

        return _main
    raise AttributeError(name)
