"""Initiative Engine — present auction-control observation (H-5 / H-6).

Independent. Never predicts. Never trades. Never chooses Dominant Side from
Objective. Objective is optional confidence context only.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from hotirjam_ai5.initiative.candle_strength import analyze_candle_strength
from hotirjam_ai5.initiative.evidence import build_evidence
from hotirjam_ai5.initiative.impulse_detector import detect_impulse
from hotirjam_ai5.initiative.initiative_models import InitiativeInputs, InitiativeState
from hotirjam_ai5.initiative.initiative_scorer import (
    advance_lifecycle,
    assemble_snapshot,
    dominant_intensity,
    select_dominant_side,
)
from hotirjam_ai5.initiative.initiative_snapshot import InitiativeSnapshot
from hotirjam_ai5.initiative.momentum_detector import detect_momentum

CHECKPOINT_VERSION = 1


def evaluate_initiative(
    inputs: InitiativeInputs,
    *,
    previous_state: InitiativeState = InitiativeState.NONE,
) -> InitiativeSnapshot:
    """Observe auction control from market evidence.

    Pure for identical inputs + previous_state. Objective never selects side.
    """
    if not math.isfinite(inputs.tick_size) or inputs.tick_size <= 0.0:
        return InitiativeSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Invalid tick size",
            state=previous_state
            if previous_state is InitiativeState.EXPIRED
            else InitiativeState.NONE,
        )
    if not inputs.candles:
        next_state = advance_lifecycle(
            previous_state,
            side=select_dominant_side(0.0, 0.0),
            intensity=0.0,
            buyer=0.0,
            seller=0.0,
        )
        return InitiativeSnapshot.empty(
            timestamp=inputs.timestamp,
            reason="Empty candle input",
            state=next_state,
        )

    impulse = detect_impulse(inputs.candles, tick_size=inputs.tick_size)
    momentum = detect_momentum(inputs.candles, tick_size=inputs.tick_size)
    candles = analyze_candle_strength(inputs.candles)
    evidence, buyer, seller, reasons = build_evidence(
        impulse=impulse,
        momentum=momentum,
        candles=candles,
        ohlc=inputs.candles,
        tick_size=inputs.tick_size,
        objectives=inputs.objectives,
    )
    side = select_dominant_side(buyer, seller)
    intensity = dominant_intensity(side, buyer, seller)
    state = advance_lifecycle(
        previous_state,
        side=side,
        intensity=intensity,
        buyer=buyer,
        seller=seller,
    )
    return assemble_snapshot(
        buyer=buyer,
        seller=seller,
        side=side,
        state=state,
        evidence=evidence,
        reasons=reasons,
        timestamp=inputs.timestamp,
    )


class InitiativeEngine:
    """Stateful Initiative Engine with lifecycle continuity and checkpointing."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        checkpoint_path: Path | None = None,
    ) -> None:
        self._clock = clock or time.time
        self._checkpoint_path = checkpoint_path
        self._previous_state = InitiativeState.NONE
        self._latest = InitiativeSnapshot.empty(timestamp=self._clock())
        if checkpoint_path is not None and checkpoint_path.exists():
            self.restore(checkpoint_path)

    def evaluate(self, inputs: InitiativeInputs) -> InitiativeSnapshot:
        self._latest = evaluate_initiative(
            inputs, previous_state=self._previous_state
        )
        self._previous_state = self._latest.initiative_state
        if self._checkpoint_path is not None:
            self.checkpoint(self._checkpoint_path)
        return self._latest

    def snapshot(self) -> InitiativeSnapshot:
        return self._latest

    @property
    def previous_state(self) -> InitiativeState:
        return self._previous_state

    def checkpoint(self, path: Path | None = None) -> None:
        _t0 = time.perf_counter()
        assemble_ms = 0.0
        serialize_ms = 0.0
        write_ms = 0.0
        flush_ms = 0.0
        fsync_ms = 0.0
        os_replace_ms = 0.0
        try:
            target = path or self._checkpoint_path
            if target is None:
                raise ValueError("checkpoint path is required")
            target.parent.mkdir(parents=True, exist_ok=True)
            _a0 = time.perf_counter()
            payload = {
                "checkpoint_version": CHECKPOINT_VERSION,
                "previous_state": self._previous_state.value,
                "latest": {
                    "buyer_initiative": self._latest.buyer_initiative,
                    "seller_initiative": self._latest.seller_initiative,
                    "dominant_side": self._latest.dominant_side.value,
                    "initiative_state": self._latest.initiative_state.value,
                    "confidence": self._latest.confidence,
                    "evidence": {
                        "force": self._latest.evidence.force,
                        "motion": self._latest.evidence.motion,
                        "pressure": self._latest.evidence.pressure,
                        "liquidity": self._latest.evidence.liquidity,
                        "energy": self._latest.evidence.energy,
                        "context": self._latest.evidence.context,
                    },
                    "reasons": list(self._latest.reasons),
                    "timestamp": self._latest.timestamp,
                },
            }
            assemble_ms = (time.perf_counter() - _a0) * 1000.0
            # Byte-identical to json.dump(..., sort_keys=True, separators=(",", ":")).
            _s0 = time.perf_counter()
            document = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            serialize_ms = (time.perf_counter() - _s0) * 1000.0
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    _w0 = time.perf_counter()
                    handle.write(document)
                    write_ms = (time.perf_counter() - _w0) * 1000.0
                    _fl0 = time.perf_counter()
                    handle.flush()
                    flush_ms = (time.perf_counter() - _fl0) * 1000.0
                    _fs0 = time.perf_counter()
                    os.fsync(handle.fileno())
                    fsync_ms = (time.perf_counter() - _fs0) * 1000.0
                _r0 = time.perf_counter()
                os.replace(temporary_name, target)
                os_replace_ms = (time.perf_counter() - _r0) * 1000.0
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        finally:
            try:
                from hotirjam_ai5.live_validator.loop_timing import (
                    add_checkpoint_exclusive,
                    add_initiative_checkpoint_ms,
                )

                add_initiative_checkpoint_ms((time.perf_counter() - _t0) * 1000.0)
                add_checkpoint_exclusive(
                    assemble_ms=assemble_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms,
                    flush_ms=flush_ms,
                    fsync_ms=fsync_ms,
                    os_replace_ms=os_replace_ms,
                )
            except Exception:
                pass

    def restore(self, path: Path | None = None) -> None:
        from hotirjam_ai5.initiative.initiative_models import (
            InitiativeEvidence,
            InitiativeSide,
        )

        source = path or self._checkpoint_path
        if source is None:
            raise ValueError("checkpoint path is required")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("checkpoint_version") != CHECKPOINT_VERSION:
            raise ValueError("unsupported initiative checkpoint version")
        latest = payload["latest"]
        evidence = latest["evidence"]
        self._previous_state = InitiativeState(payload["previous_state"])
        self._latest = InitiativeSnapshot(
            buyer_initiative=float(latest["buyer_initiative"]),
            seller_initiative=float(latest["seller_initiative"]),
            dominant_side=InitiativeSide(latest["dominant_side"]),
            initiative_state=InitiativeState(latest["initiative_state"]),
            confidence=float(latest["confidence"]),
            evidence=InitiativeEvidence(
                force=float(evidence["force"]),
                motion=float(evidence["motion"]),
                pressure=float(evidence["pressure"]),
                liquidity=float(evidence["liquidity"]),
                energy=float(evidence["energy"]),
                context=float(evidence["context"]),
            ),
            reasons=tuple(str(item) for item in latest["reasons"]),
            timestamp=float(latest["timestamp"]),
        )
