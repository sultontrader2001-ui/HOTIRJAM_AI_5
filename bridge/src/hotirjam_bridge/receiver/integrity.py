"""Canonical NDJSON payload lines + integrity checks (Receiver).

No AI imports. Preserves payload object fidelity via stable JSON encoding.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_payload_line(payload: dict[str, Any]) -> str:
    """Encode payload as one NDJSON line (exact journal form).

    Uses compact separators and UTF-8 text. Key order follows the dict
    (json.loads preserves order — same object Sender wrapped).
    """
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"


def line_sha256(line: str | bytes) -> str:
    data = line.encode("utf-8") if isinstance(line, str) else line
    return hashlib.sha256(data).hexdigest()


def assert_payload_line_matches(
    payload: dict[str, Any],
    written_line: str | bytes,
) -> str:
    """Prove written journal bytes match canonical encoding of ``payload``.

    Returns the SHA-256 hex digest of the written line.
    Raises ``ValueError`` on mismatch.
    """
    expected = canonical_payload_line(payload)
    if isinstance(written_line, bytes):
        actual = written_line.decode("utf-8")
    else:
        actual = written_line
    if not actual.endswith("\n"):
        actual = actual + "\n"
    if actual != expected:
        raise ValueError(
            "payload line mismatch: "
            f"expected_sha={line_sha256(expected)} actual_sha={line_sha256(actual)}"
        )
    # Semantic check as well
    parsed = json.loads(actual)
    if parsed != payload:
        raise ValueError("payload JSON semantic mismatch after write")
    return line_sha256(actual)
