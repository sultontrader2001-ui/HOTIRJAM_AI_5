"""Persistent, event-driven structural hierarchy for Objective diagnostics.

The rolling swing tuples are an ingestion surface only.  Once observed, a
swing's identity, ancestry, and classification evidence live in this registry
until an explicit structural lifecycle transition occurs.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Mapping

from hotirjam_ai5.objective.objective_models import ConfirmedSwing
from hotirjam_ai5.objective_diagnostics.candidate_report import (
    evaluate_eligibility,
    sort_candidates,
)
from hotirjam_ai5.objective_diagnostics.hierarchy_builder import HierarchyNode
from hotirjam_ai5.objective_diagnostics.models import (
    CandidateCategory,
    LifecycleState,
    ObjectiveAuditReport,
    ObjectiveDiagnosticsInputs,
    SwingDiagnostic,
    SwingSide,
)
from hotirjam_ai5.objective_diagnostics.significance_diagnostics import (
    classify_category,
    compute_persistence,
    compute_prominence_ticks,
)


CHECKPOINT_VERSION = 1
CLASSIFICATION_VERSION = 1
_ZONE_TICKS = 2.0


@dataclass(frozen=True, slots=True)
class StructuralSwingRecord:
    """Permanent structural facts and frozen classification for one swing."""

    swing_id: int
    fingerprint: str
    side: SwingSide
    price: float
    strength: float
    confirmed_at: float | None
    parent_id: int | None
    depth: int
    category: CandidateCategory
    prominence: float
    persistence_score: float
    classification_version: int
    lifecycle: LifecycleState
    created_sequence: int
    last_transition_sequence: int

    def as_swing(self) -> ConfirmedSwing:
        return ConfirmedSwing(
            price=self.price,
            strength=self.strength,
            confirmed_at=self.confirmed_at,
        )


@dataclass(frozen=True, slots=True)
class StructuralTransition:
    """One append-only, replayable mutation in the hierarchy."""

    sequence: int
    timestamp: float
    cause: str
    swing_id: int
    old_state: Mapping[str, object] | None
    new_state: Mapping[str, object] | None
    evidence: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StructuralHierarchySnapshot:
    """Immutable structural state consumed by the Objective audit adapter."""

    hierarchy_version: int
    checkpoint_version: int
    records: tuple[StructuralSwingRecord, ...]
    transition_count: int


def _fingerprint(side: SwingSide, swing: ConfirmedSwing) -> str:
    """Stable source identity for a confirmed swing across replay/restart."""
    confirmed = "none" if swing.confirmed_at is None else float(swing.confirmed_at).hex()
    return "|".join(
        (
            side.value,
            confirmed,
            float(swing.price).hex(),
            float(swing.strength).hex(),
        )
    )


def _state(record: StructuralSwingRecord) -> dict[str, object]:
    return {
        "swing_id": record.swing_id,
        "side": record.side.value,
        "price": record.price,
        "strength": record.strength,
        "confirmed_at": record.confirmed_at,
        "parent_id": record.parent_id,
        "depth": record.depth,
        "category": record.category.value,
        "prominence": record.prominence,
        "persistence_score": record.persistence_score,
        "classification_version": record.classification_version,
        "lifecycle": record.lifecycle.value,
    }


class PersistentStructuralHierarchy:
    """State owner for stable structural identity, ancestry, and lifecycle."""

    def __init__(self, *, checkpoint_path: Path | None = None) -> None:
        self._checkpoint_path = checkpoint_path
        self._records: dict[int, StructuralSwingRecord] = {}
        self._fingerprints: dict[str, int] = {}
        self._frontiers: dict[SwingSide, list[int]] = {
            SwingSide.HIGH: [],
            SwingSide.LOW: [],
        }
        self._journal: list[StructuralTransition] = []
        self._next_swing_id = 1
        self._version = 0
        if checkpoint_path is not None and checkpoint_path.exists():
            self.restore(checkpoint_path)

    @property
    def hierarchy_version(self) -> int:
        return self._version

    @property
    def checkpoint_version(self) -> int:
        return CHECKPOINT_VERSION

    @property
    def registry_size(self) -> int:
        return len(self._records)

    @property
    def journal(self) -> tuple[StructuralTransition, ...]:
        return tuple(self._journal)

    def snapshot(self) -> StructuralHierarchySnapshot:
        return StructuralHierarchySnapshot(
            hierarchy_version=self._version,
            checkpoint_version=CHECKPOINT_VERSION,
            records=tuple(self._records[key] for key in sorted(self._records)),
            transition_count=len(self._journal),
        )

    def evaluate(self, inputs: ObjectiveDiagnosticsInputs) -> ObjectiveAuditReport:
        """Ingest new swing events, apply lifecycle events, and adapt a report."""
        if inputs.tick_size <= 0.0:
            return ObjectiveAuditReport(
                timestamp=inputs.timestamp,
                current_price=inputs.current_price,
                tick_size=inputs.tick_size,
                highs=(),
                lows=(),
                summary_lines=("Invalid tick size — diagnostics skipped",),
                hierarchy_version=self._version,
                registry_size=len(self._records),
                transition_count=len(self._journal),
                checkpoint_version=CHECKPOINT_VERSION,
            )

        before = self._version
        new_ids = self._ingest(inputs)
        if new_ids:
            self._classify_new(new_ids, inputs)
            self._apply_supersession(new_ids, inputs)
        self._apply_breaches(inputs)
        if self._version != before and self._checkpoint_path is not None:
            self.checkpoint(self._checkpoint_path)
        return self._to_report(inputs)

    def archive(
        self,
        swing_id: int,
        *,
        timestamp: float,
        evidence: Mapping[str, object] | None = None,
    ) -> None:
        """Archive a terminal node while retaining it as a structural anchor."""
        record = self._records[swing_id]
        if record.lifecycle is LifecycleState.ACTIVE:
            raise ValueError("ACTIVE structural nodes cannot be archived")
        if record.lifecycle is LifecycleState.ARCHIVED:
            return
        self._transition_lifecycle(
            swing_id,
            LifecycleState.ARCHIVED,
            timestamp=timestamp,
            cause="STRUCTURAL_ARCHIVED",
            evidence=evidence or {},
        )
        if self._checkpoint_path is not None:
            self.checkpoint(self._checkpoint_path)

    def checkpoint(self, path: Path | None = None) -> None:
        """Atomically persist registry, graph, lifecycle, and transition journal."""
        target = path or self._checkpoint_path
        if target is None:
            raise ValueError("checkpoint path is required")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "hierarchy_version": self._version,
            "next_swing_id": self._next_swing_id,
            "records": [self._record_payload(r) for r in self.snapshot().records],
            "frontiers": {
                side.value: list(ids) for side, ids in self._frontiers.items()
            },
            "journal": [self._transition_payload(t) for t in self._journal],
        }
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def restore(self, path: Path | None = None) -> None:
        """Restore an exact hierarchy checkpoint without rebuilding history."""
        source = path or self._checkpoint_path
        if source is None:
            raise ValueError("checkpoint path is required")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("checkpoint_version") != CHECKPOINT_VERSION:
            raise ValueError("unsupported structural hierarchy checkpoint version")

        records = {
            item["swing_id"]: self._record_from_payload(item)
            for item in payload["records"]
        }
        fingerprints = {r.fingerprint: r.swing_id for r in records.values()}
        journal = [
            StructuralTransition(
                sequence=item["sequence"],
                timestamp=item["timestamp"],
                cause=item["cause"],
                swing_id=item["swing_id"],
                old_state=item["old_state"],
                new_state=item["new_state"],
                evidence=item["evidence"],
            )
            for item in payload["journal"]
        ]
        self._records = records
        self._fingerprints = fingerprints
        self._frontiers = {
            SwingSide.HIGH: list(payload["frontiers"][SwingSide.HIGH.value]),
            SwingSide.LOW: list(payload["frontiers"][SwingSide.LOW.value]),
        }
        self._journal = journal
        self._next_swing_id = payload["next_swing_id"]
        self._version = payload["hierarchy_version"]

    def _ingest(self, inputs: ObjectiveDiagnosticsInputs) -> list[int]:
        incoming = [
            (SwingSide.HIGH, swing) for swing in inputs.confirmed_highs
        ] + [
            (SwingSide.LOW, swing) for swing in inputs.confirmed_lows
        ]
        incoming.sort(
            key=lambda item: (
                item[1].confirmed_at
                if item[1].confirmed_at is not None
                else float("-inf"),
                0 if item[0] is SwingSide.HIGH else 1,
                _fingerprint(*item),
            )
        )
        new_ids: list[int] = []
        for side, swing in incoming:
            fingerprint = _fingerprint(side, swing)
            if fingerprint in self._fingerprints:
                continue
            swing_id = self._next_swing_id
            self._next_swing_id += 1
            parent_id, depth = self._assign_parent(side, swing.price)
            record = StructuralSwingRecord(
                swing_id=swing_id,
                fingerprint=fingerprint,
                side=side,
                price=swing.price,
                strength=swing.strength,
                confirmed_at=swing.confirmed_at,
                parent_id=parent_id,
                depth=depth,
                category=CandidateCategory.MICRO,
                prominence=0.0,
                persistence_score=0.0,
                classification_version=CLASSIFICATION_VERSION,
                lifecycle=LifecycleState.ACTIVE,
                created_sequence=self._version + 1,
                last_transition_sequence=self._version + 1,
            )
            self._records[swing_id] = record
            self._fingerprints[fingerprint] = swing_id
            self._frontiers[side].append(swing_id)
            new_ids.append(swing_id)
        return new_ids

    def _assign_parent(self, side: SwingSide, price: float) -> tuple[int | None, int]:
        frontier = self._frontiers[side]
        if side is SwingSide.HIGH:
            while frontier and self._records[frontier[-1]].price <= price:
                frontier.pop()
        else:
            while frontier and self._records[frontier[-1]].price >= price:
                frontier.pop()
        parent_id = frontier[-1] if frontier else None
        depth = self._records[parent_id].depth + 1 if parent_id is not None else 0
        return parent_id, depth

    def _classify_new(
        self, new_ids: list[int], inputs: ObjectiveDiagnosticsInputs
    ) -> None:
        nodes = self._nodes()
        by_id = {node.swing_id: node for node in nodes}
        for swing_id in new_ids:
            record = self._records[swing_id]
            node = by_id[swing_id]
            prominence = compute_prominence_ticks(
                node, nodes, tick_size=inputs.tick_size
            )
            persistence = compute_persistence(node, prominence)
            category = classify_category(
                depth=record.depth,
                prominence_ticks=prominence,
                persistence=persistence,
            )
            classified = StructuralSwingRecord(
                swing_id=record.swing_id,
                fingerprint=record.fingerprint,
                side=record.side,
                price=record.price,
                strength=record.strength,
                confirmed_at=record.confirmed_at,
                parent_id=record.parent_id,
                depth=record.depth,
                category=category,
                prominence=prominence,
                persistence_score=persistence,
                classification_version=CLASSIFICATION_VERSION,
                lifecycle=record.lifecycle,
                created_sequence=record.created_sequence,
                last_transition_sequence=self._version + 1,
            )
            self._records[swing_id] = classified
            self._append_transition(
                timestamp=inputs.timestamp,
                cause="SWING_CONFIRMED",
                swing_id=swing_id,
                old_state=None,
                new_state=_state(classified),
                evidence={
                    "parent_id": classified.parent_id,
                    "classification_version": CLASSIFICATION_VERSION,
                },
            )

    def _apply_supersession(
        self, new_ids: list[int], inputs: ObjectiveDiagnosticsInputs
    ) -> None:
        zone = _ZONE_TICKS * inputs.tick_size
        for new_id in new_ids:
            new = self._records[new_id]
            if new.confirmed_at is None:
                continue
            for old_id in sorted(self._records):
                if old_id == new_id:
                    continue
                old = self._records[old_id]
                if (
                    old.side is not new.side
                    or old.lifecycle is not LifecycleState.ACTIVE
                    or old.confirmed_at is None
                    or old.confirmed_at >= new.confirmed_at
                    or abs(old.price - new.price) > zone
                ):
                    continue
                self._transition_lifecycle(
                    old_id,
                    LifecycleState.SUPERSEDED,
                    timestamp=inputs.timestamp,
                    cause="SWING_SUPERSEDED",
                    evidence={"superseding_swing_id": new_id, "zone_ticks": _ZONE_TICKS},
                )

    def _apply_breaches(self, inputs: ObjectiveDiagnosticsInputs) -> None:
        extreme_high = (
            inputs.session_high
            if inputs.session_high is not None
            else inputs.current_price
        )
        extreme_low = (
            inputs.session_low if inputs.session_low is not None else inputs.current_price
        )
        for swing_id in sorted(self._records):
            record = self._records[swing_id]
            breached = (
                record.side is SwingSide.HIGH and extreme_high > record.price
            ) or (
                record.side is SwingSide.LOW and extreme_low < record.price
            )
            if breached and record.lifecycle is not LifecycleState.BREACHED:
                if record.lifecycle is LifecycleState.ARCHIVED:
                    continue
                self._transition_lifecycle(
                    swing_id,
                    LifecycleState.BREACHED,
                    timestamp=inputs.timestamp,
                    cause="PRICE_BREACH",
                    evidence={
                        "current_price": inputs.current_price,
                        "extreme_high": extreme_high,
                        "extreme_low": extreme_low,
                    },
                )

    def _transition_lifecycle(
        self,
        swing_id: int,
        lifecycle: LifecycleState,
        *,
        timestamp: float,
        cause: str,
        evidence: Mapping[str, object],
    ) -> None:
        old = self._records[swing_id]
        if old.lifecycle is lifecycle:
            return
        updated = StructuralSwingRecord(
            swing_id=old.swing_id,
            fingerprint=old.fingerprint,
            side=old.side,
            price=old.price,
            strength=old.strength,
            confirmed_at=old.confirmed_at,
            parent_id=old.parent_id,
            depth=old.depth,
            category=old.category,
            prominence=old.prominence,
            persistence_score=old.persistence_score,
            classification_version=old.classification_version,
            lifecycle=lifecycle,
            created_sequence=old.created_sequence,
            last_transition_sequence=self._version + 1,
        )
        self._records[swing_id] = updated
        self._append_transition(
            timestamp=timestamp,
            cause=cause,
            swing_id=swing_id,
            old_state=_state(old),
            new_state=_state(updated),
            evidence=evidence,
        )

    def _append_transition(
        self,
        *,
        timestamp: float,
        cause: str,
        swing_id: int,
        old_state: Mapping[str, object] | None,
        new_state: Mapping[str, object] | None,
        evidence: Mapping[str, object],
    ) -> None:
        self._version += 1
        self._journal.append(
            StructuralTransition(
                sequence=self._version,
                timestamp=timestamp,
                cause=cause,
                swing_id=swing_id,
                old_state=old_state,
                new_state=new_state,
                evidence=dict(evidence),
            )
        )

    def _nodes(self) -> tuple[HierarchyNode, ...]:
        return tuple(
            HierarchyNode(
                swing_id=record.swing_id,
                side=record.side,
                swing=record.as_swing(),
                parent_swing_id=record.parent_id,
                depth=record.depth,
            )
            for record in self.snapshot().records
        )

    def _to_report(self, inputs: ObjectiveDiagnosticsInputs) -> ObjectiveAuditReport:
        diagnostics: list[SwingDiagnostic] = []
        for record in self.snapshot().records:
            distance = abs(record.price - inputs.current_price) / inputs.tick_size
            eligible, reasons = evaluate_eligibility(
                side=record.side,
                price=record.price,
                current_price=inputs.current_price,
                lifecycle=record.lifecycle,
                category=record.category,
                depth=record.depth,
                prominence=record.prominence,
                parent_swing_id=record.parent_id,
            )
            diagnostics.append(
                SwingDiagnostic(
                    swing_id=record.swing_id,
                    side=record.side,
                    price=record.price,
                    confirmed_at=record.confirmed_at,
                    distance_ticks=distance,
                    current_strength=record.strength,
                    parent_swing_id=record.parent_id,
                    hierarchy_depth=record.depth,
                    persistence=record.persistence_score,
                    prominence=record.prominence,
                    lifecycle=record.lifecycle,
                    category=record.category,
                    eligible=eligible,
                    rejection_reasons=reasons,
                )
            )
        highs = sort_candidates(
            [item for item in diagnostics if item.side is SwingSide.HIGH]
        )
        lows = sort_candidates(
            [item for item in diagnostics if item.side is SwingSide.LOW]
        )
        return ObjectiveAuditReport(
            timestamp=inputs.timestamp,
            current_price=inputs.current_price,
            tick_size=inputs.tick_size,
            highs=tuple(highs),
            lows=tuple(lows),
            summary_lines=(),
            hierarchy_version=self._version,
            registry_size=len(self._records),
            transition_count=len(self._journal),
            checkpoint_version=CHECKPOINT_VERSION,
        )

    @staticmethod
    def _record_payload(record: StructuralSwingRecord) -> dict[str, object]:
        payload = asdict(record)
        payload["side"] = record.side.value
        payload["category"] = record.category.value
        payload["lifecycle"] = record.lifecycle.value
        return payload

    @staticmethod
    def _record_from_payload(item: Mapping[str, object]) -> StructuralSwingRecord:
        return StructuralSwingRecord(
            swing_id=int(item["swing_id"]),
            fingerprint=str(item["fingerprint"]),
            side=SwingSide(str(item["side"])),
            price=float(item["price"]),
            strength=float(item["strength"]),
            confirmed_at=(
                None
                if item["confirmed_at"] is None
                else float(item["confirmed_at"])
            ),
            parent_id=(
                None if item["parent_id"] is None else int(item["parent_id"])
            ),
            depth=int(item["depth"]),
            category=CandidateCategory(str(item["category"])),
            prominence=float(item["prominence"]),
            persistence_score=float(item["persistence_score"]),
            classification_version=int(item["classification_version"]),
            lifecycle=LifecycleState(str(item["lifecycle"])),
            created_sequence=int(item["created_sequence"]),
            last_transition_sequence=int(item["last_transition_sequence"]),
        )

    @staticmethod
    def _transition_payload(
        transition: StructuralTransition,
    ) -> dict[str, object]:
        return {
            "sequence": transition.sequence,
            "timestamp": transition.timestamp,
            "cause": transition.cause,
            "swing_id": transition.swing_id,
            "old_state": transition.old_state,
            "new_state": transition.new_state,
            "evidence": transition.evidence,
        }


_ACTIVE_HIERARCHY: ContextVar[PersistentStructuralHierarchy | None] = ContextVar(
    "hotirjam_objective_structural_hierarchy", default=None
)


@contextmanager
def use_structural_hierarchy(
    hierarchy: PersistentStructuralHierarchy,
) -> Iterator[None]:
    """Bind one hierarchy to unchanged Objective Engine audit calls."""
    token = _ACTIVE_HIERARCHY.set(hierarchy)
    try:
        yield
    finally:
        _ACTIVE_HIERARCHY.reset(token)


def active_structural_hierarchy() -> PersistentStructuralHierarchy | None:
    return _ACTIVE_HIERARCHY.get()
