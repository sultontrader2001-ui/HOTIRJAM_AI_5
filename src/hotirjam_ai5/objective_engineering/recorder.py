"""Observe ObjectiveSnapshot stream; emit samples, changes, anomalies."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from hotirjam_ai5.objective.objective_snapshot import (
    ObjectivePersistenceState,
    ObjectiveSnapshot,
)
from hotirjam_ai5.objective_engineering.anomalies import (
    AnomalyCode,
    check_flicker,
    check_impossible_transition,
    check_invalid_none,
    check_side_coupling,
    check_unexpected_replacement,
    side_label,
)
from hotirjam_ai5.objective_engineering.models import (
    ObjectiveAnomaly,
    ObjectiveChangeEvent,
    ObjectiveEngineeringSample,
    ReasonClass,
)
from hotirjam_ai5.objective_engineering.reasons import (
    identity_changed,
    infer_side_reason,
    side_fields,
    state_changed,
)


def _state_value(state: ObjectivePersistenceState | None) -> str | None:
    return None if state is None else str(state.value)


@dataclass
class ObjectiveEngineeringRecorder:
    """Stateful observer over consecutive ObjectiveSnapshot values.

    Never mutates the engine. Optional writers for NDJSON evidence.
    """

    samples_path: Path | None = None
    changes_path: Path | None = None
    anomalies_path: Path | None = None
    anomaly_stream: TextIO | None = field(default_factory=lambda: sys.stderr)
    flicker_window: int = 3
    _sample_id: int = 0
    _change_id: int = 0
    _anomaly_id: int = 0
    _prev: ObjectiveSnapshot | None = None
    _high_history: list[float | None] = field(default_factory=list)
    _low_history: list[float | None] = field(default_factory=list)
    samples: list[ObjectiveEngineeringSample] = field(default_factory=list)
    changes: list[ObjectiveChangeEvent] = field(default_factory=list)
    anomalies: list[ObjectiveAnomaly] = field(default_factory=list)

    @property
    def sample_count(self) -> int:
        return self._sample_id

    def observe(self, snapshot: ObjectiveSnapshot) -> list[ObjectiveAnomaly]:
        """Ingest one snapshot; return anomalies found on this step."""
        self._sample_id += 1
        prev = self._prev

        if prev is None:
            high_reason = infer_side_reason(
                previous_price=None,
                previous_distance=None,
                previous_state=None,
                current_price=snapshot.nearest_high_price,
                current_distance=snapshot.nearest_high_distance_ticks,
                current_state=snapshot.high_state,
            )
            low_reason = infer_side_reason(
                previous_price=None,
                previous_distance=None,
                previous_state=None,
                current_price=snapshot.nearest_low_price,
                current_distance=snapshot.nearest_low_distance_ticks,
                current_state=snapshot.low_state,
            )
            high_changed = snapshot.nearest_high_price is not None or snapshot.high_state is not None
            low_changed = snapshot.nearest_low_price is not None or snapshot.low_state is not None
            # First sample: only "changed" if something is present.
            sample = self._build_sample(
                snapshot,
                high_reason=high_reason,
                low_reason=low_reason,
                high_changed=bool(high_changed and snapshot.nearest_high_price is not None),
                low_changed=bool(low_changed and snapshot.nearest_low_price is not None),
            )
            found = self._detect_anomalies(
                prev=None,
                current=snapshot,
                high_reason=high_reason,
                low_reason=low_reason,
                sample_id=sample.sample_id,
            )
            self._emit_sample(sample)
            if sample.high_changed:
                self._emit_change(
                    self._change_from_side(
                        sample,
                        side="HIGH",
                        from_price=None,
                        from_state=None,
                        from_distance=None,
                        to_price=snapshot.nearest_high_price,
                        to_state=snapshot.high_state,
                        to_distance=snapshot.nearest_high_distance_ticks,
                        reason=high_reason,
                    )
                )
            if sample.low_changed:
                self._emit_change(
                    self._change_from_side(
                        sample,
                        side="LOW",
                        from_price=None,
                        from_state=None,
                        from_distance=None,
                        to_price=snapshot.nearest_low_price,
                        to_state=snapshot.low_state,
                        to_distance=snapshot.nearest_low_distance_ticks,
                        reason=low_reason,
                    )
                )
            self._append_history(snapshot)
            self._prev = snapshot
            return found

        hp, hd, _, hs = side_fields(prev, high=True)
        hc, hcd, _, hcs = side_fields(snapshot, high=True)
        lp, ld, _, ls = side_fields(prev, high=False)
        lc, lcd, _, lcs = side_fields(snapshot, high=False)

        high_reason = infer_side_reason(
            previous_price=hp,
            previous_distance=hd,
            previous_state=hs,
            current_price=hc,
            current_distance=hcd,
            current_state=hcs,
        )
        low_reason = infer_side_reason(
            previous_price=lp,
            previous_distance=ld,
            previous_state=ls,
            current_price=lc,
            current_distance=lcd,
            current_state=lcs,
        )
        high_changed = identity_changed(hp, hc) or state_changed(hs, hcs)
        low_changed = identity_changed(lp, lc) or state_changed(ls, lcs)

        sample = self._build_sample(
            snapshot,
            high_reason=high_reason,
            low_reason=low_reason,
            high_changed=high_changed,
            low_changed=low_changed,
        )
        found = self._detect_anomalies(
            prev=prev,
            current=snapshot,
            high_reason=high_reason,
            low_reason=low_reason,
            sample_id=sample.sample_id,
        )
        self._emit_sample(sample)
        if high_changed:
            self._emit_change(
                self._change_from_side(
                    sample,
                    side="HIGH",
                    from_price=hp,
                    from_state=hs,
                    from_distance=hd,
                    to_price=hc,
                    to_state=hcs,
                    to_distance=hcd,
                    reason=high_reason,
                )
            )
        if low_changed:
            self._emit_change(
                self._change_from_side(
                    sample,
                    side="LOW",
                    from_price=lp,
                    from_state=ls,
                    from_distance=ld,
                    to_price=lc,
                    to_state=lcs,
                    to_distance=lcd,
                    reason=low_reason,
                )
            )
        self._append_history(snapshot)
        self._prev = snapshot
        return found

    def observe_frame(self, frame: Any) -> list[ObjectiveAnomaly]:
        """Observe ``frame.objective`` (ValidatorFrame-compatible)."""
        objective = getattr(frame, "objective", None)
        if objective is None:
            return []
        return self.observe(objective)

    def _build_sample(
        self,
        snapshot: ObjectiveSnapshot,
        *,
        high_reason: ReasonClass,
        low_reason: ReasonClass,
        high_changed: bool,
        low_changed: bool,
    ) -> ObjectiveEngineeringSample:
        sample = ObjectiveEngineeringSample(
            sample_id=self._sample_id,
            timestamp=float(snapshot.timestamp),
            current_price=snapshot.current_price,
            high_price=snapshot.nearest_high_price,
            high_distance_ticks=snapshot.nearest_high_distance_ticks,
            high_strength=snapshot.nearest_high_strength,
            high_state=_state_value(snapshot.high_state),
            high_reason=str(high_reason.value),
            low_price=snapshot.nearest_low_price,
            low_distance_ticks=snapshot.nearest_low_distance_ticks,
            low_strength=snapshot.nearest_low_strength,
            low_state=_state_value(snapshot.low_state),
            low_reason=str(low_reason.value),
            high_changed=high_changed,
            low_changed=low_changed,
        )
        self.samples.append(sample)
        return sample

    def _change_from_side(
        self,
        sample: ObjectiveEngineeringSample,
        *,
        side: str,
        from_price: float | None,
        from_state: ObjectivePersistenceState | None,
        from_distance: float | None,
        to_price: float | None,
        to_state: ObjectivePersistenceState | None,
        to_distance: float | None,
        reason: ReasonClass,
    ) -> ObjectiveChangeEvent:
        self._change_id += 1
        return ObjectiveChangeEvent(
            change_id=self._change_id,
            sample_id=sample.sample_id,
            timestamp=sample.timestamp,
            side=side,
            from_price=from_price,
            to_price=to_price,
            from_state=_state_value(from_state),
            to_state=_state_value(to_state),
            from_distance_ticks=from_distance,
            to_distance_ticks=to_distance,
            reason=str(reason.value),
            current_price=sample.current_price,
        )

    def _detect_anomalies(
        self,
        *,
        prev: ObjectiveSnapshot | None,
        current: ObjectiveSnapshot,
        high_reason: ReasonClass,
        low_reason: ReasonClass,
        sample_id: int,
    ) -> list[ObjectiveAnomaly]:
        found: list[ObjectiveAnomaly] = []

        def add(
            code: AnomalyCode,
            *,
            side: str | None,
            detail: str,
        ) -> None:
            self._anomaly_id += 1
            anomaly = ObjectiveAnomaly(
                anomaly_id=self._anomaly_id,
                sample_id=sample_id,
                timestamp=float(current.timestamp),
                code=str(code.value),
                side=side,
                detail=detail,
                current_price=current.current_price,
            )
            self.anomalies.append(anomaly)
            found.append(anomaly)
            self._emit_anomaly(anomaly)

        for high, reason in ((True, high_reason), (False, low_reason)):
            price, _dist, _str, state = side_fields(current, high=high)
            side = str(side_label(high).value)
            invalid = check_invalid_none(price=price, state=state)
            if invalid:
                add(AnomalyCode.INVALID_NONE, side=side, detail=invalid)
            if prev is not None:
                pp, _pd, _ps, pst = side_fields(prev, high=high)
                impossible = check_impossible_transition(
                    previous_price=pp,
                    previous_state=pst,
                    current_price=price,
                    current_state=state,
                )
                if impossible:
                    add(AnomalyCode.IMPOSSIBLE_TRANSITION, side=side, detail=impossible)
            unexpected = check_unexpected_replacement(
                current_state=state,
                reason=reason,
            )
            if unexpected:
                add(AnomalyCode.UNEXPECTED_REPLACEMENT, side=side, detail=unexpected)

        if prev is not None:
            coupling = check_side_coupling(
                high_prev_price=prev.nearest_high_price,
                high_price=current.nearest_high_price,
                high_prev_state=prev.high_state,
                high_state=current.high_state,
                low_prev_price=prev.nearest_low_price,
                low_price=current.nearest_low_price,
                low_prev_state=prev.low_state,
                low_state=current.low_state,
            )
            if coupling:
                add(AnomalyCode.SIDE_COUPLING, side=None, detail=coupling)

            for high, history in (
                (True, self._high_history),
                (False, self._low_history),
            ):
                price, _d, _s, state = side_fields(current, high=high)
                flicker = check_flicker(
                    history=history,
                    current_price=price,
                    current_state=state,
                    window=self.flicker_window,
                )
                if flicker:
                    add(
                        AnomalyCode.UNEXPLAINED_FLICKER,
                        side=str(side_label(high).value),
                        detail=flicker,
                    )

        return found

    def _append_history(self, snapshot: ObjectiveSnapshot) -> None:
        self._high_history.append(snapshot.nearest_high_price)
        self._low_history.append(snapshot.nearest_low_price)
        # Bound memory for long sessions.
        max_len = max(32, self.flicker_window + 8)
        if len(self._high_history) > max_len:
            self._high_history = self._high_history[-max_len:]
        if len(self._low_history) > max_len:
            self._low_history = self._low_history[-max_len:]

    def _emit_sample(self, sample: ObjectiveEngineeringSample) -> None:
        self._append_json(self.samples_path, sample.as_dict())

    def _emit_change(self, change: ObjectiveChangeEvent) -> None:
        self.changes.append(change)
        self._append_json(self.changes_path, change.as_dict())

    def _emit_anomaly(self, anomaly: ObjectiveAnomaly) -> None:
        self._append_json(self.anomalies_path, anomaly.as_dict())
        stream = self.anomaly_stream
        if stream is not None:
            stream.write(anomaly.highlight_line() + "\n")
            stream.flush()

    @staticmethod
    def _append_json(path: Path | None, payload: dict[str, Any]) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            handle.write("\n")
