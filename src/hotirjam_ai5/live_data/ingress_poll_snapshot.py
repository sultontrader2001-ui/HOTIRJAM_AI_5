"""TEMPORARY — last LiveTickIngress.poll() observation (Feed WAITING triage).

Diagnostics only. Remove after Gate A vs Gate B is resolved.
Does not alter tail, parser, or controller behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngressPollSnapshot:
    """Read-only result of one ingress poll for A/B discrimination."""

    tail_lines: int
    accepted_count: int
    skipped_count: int
    accepted_delta: int
    skipped_delta: int
    file_offset: int | None
    file_size: int | None

    @property
    def gate(self) -> str:
        """A = zero tail lines; B = lines all rejected; OK = at least one accepted."""
        if self.tail_lines == 0:
            return "A_ZERO_TAIL_LINES"
        if self.accepted_delta == 0:
            return "B_ALL_REJECTED"
        return "OK"
