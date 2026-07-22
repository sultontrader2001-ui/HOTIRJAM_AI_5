"""Persistent, event-driven structural hierarchy for Objective diagnostics.

The rolling swing tuples are an ingestion surface only.  Once observed, a
swing's identity, ancestry, and classification evidence live in this registry
until an explicit structural lifecycle transition occurs.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
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


CHECKPOINT_VERSION = 2
CLASSIFICATION_VERSION = 1


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
    challenge_started_at: float | None
    challenge_extreme_price: float | None
    challenge_evidence: tuple[str, ...]
    transition_cause: str
    transition_time: float
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
        "challenge_started_at": record.challenge_started_at,
        "challenge_extreme_price": record.challenge_extreme_price,
        "challenge_evidence": list(record.challenge_evidence),
        "transition_cause": record.transition_cause,
        "transition_time": record.transition_time,
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
        # Incremental JSON fragments (sort_keys=True). Avoids full re-serialize.
        self._record_json: dict[int, str] = {}
        self._journal_json: list[str] = []
        self._displaced_by_new: dict[int, tuple[int, ...]] = {}
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
            self._activate_new(new_ids, inputs)
            self._resolve_challenges(new_ids, inputs)
            self._apply_supersession(new_ids, inputs)
        self._apply_challenges(inputs)
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
        if record.lifecycle not in {
            LifecycleState.CONFIRMED_BROKEN,
            LifecycleState.SUPERSEDED,
            LifecycleState.ARCHIVED,
        }:
            raise ValueError("only terminal structural nodes can be archived")
        if record.lifecycle is LifecycleState.ARCHIVED:
            return
        archive_evidence = dict(evidence or {})
        closing_id = archive_evidence.get("epoch_closing_swing_id")
        if not isinstance(closing_id, int) or closing_id not in self._records:
            raise ValueError("archive requires a valid epoch_closing_swing_id")
        closing = self._records[closing_id]
        if closing.parent_id is not None:
            raise ValueError("epoch-closing swing must be a structural root")
        if (
            record.confirmed_at is not None
            and closing.confirmed_at is not None
            and closing.confirmed_at <= record.confirmed_at
        ):
            raise ValueError("epoch-closing swing must follow the archived node")
        self._transition_lifecycle(
            swing_id,
            LifecycleState.ARCHIVED,
            timestamp=timestamp,
            cause="STRUCTURAL_EPOCH_CLOSED",
            evidence=archive_evidence,
        )
        if self._checkpoint_path is not None:
            self.checkpoint(self._checkpoint_path)

    def checkpoint(self, path: Path | None = None) -> None:
        """Atomically persist registry, graph, lifecycle, and transition journal."""
        _t0 = time.perf_counter()
        collect_ms = 0.0
        build_ms = 0.0
        serialize_ms = 0.0
        write_ms = 0.0
        flush_ms = 0.0
        payload: dict[str, object] | None = None
        document: str | None = None
        written_path: Path | None = None
        try:
            _c0 = time.perf_counter()
            target = path or self._checkpoint_path
            if target is None:
                raise ValueError("checkpoint path is required")
            target.parent.mkdir(parents=True, exist_ok=True)
            collect_ms = (time.perf_counter() - _c0) * 1000.0

            _b0 = time.perf_counter()
            self._ensure_json_caches()
            document = self._assemble_checkpoint_document()
            # Lightweight payload for footprint diagnostics (no nested rebuild).
            payload = {
                "checkpoint_version": CHECKPOINT_VERSION,
                "hierarchy_version": self._version,
                "next_swing_id": self._next_swing_id,
                "records": self._records,
                "frontiers": self._frontiers,
                "journal": self._journal,
            }
            build_ms = (time.perf_counter() - _b0) * 1000.0

            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    _s0 = time.perf_counter()
                    handle.write(document)
                    serialize_ms = (time.perf_counter() - _s0) * 1000.0

                    _f0 = time.perf_counter()
                    handle.flush()
                    os.fsync(handle.fileno())
                    flush_ms = (time.perf_counter() - _f0) * 1000.0

                _w0 = time.perf_counter()
                os.replace(temporary_name, target)
                write_ms = (time.perf_counter() - _w0) * 1000.0
                written_path = target
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        finally:
            try:
                from hotirjam_ai5.live_validator.loop_timing import (
                    SectionSize,
                    add_hierarchy_breakdown,
                    add_hierarchy_checkpoint_ms,
                    set_hierarchy_footprint,
                )

                add_hierarchy_checkpoint_ms((time.perf_counter() - _t0) * 1000.0)
                add_hierarchy_breakdown(
                    collect_ms=collect_ms,
                    build_ms=build_ms,
                    serialize_ms=serialize_ms,
                    write_ms=write_ms,
                    flush_ms=flush_ms,
                )
                # Footprint after timing so existing stage totals stay unchanged.
                if payload is not None and document is not None:
                    json_size_bytes = len(document.encode("utf-8"))
                    if written_path is not None and written_path.exists():
                        json_size_bytes = written_path.stat().st_size
                    frontiers_json = self._frontiers_json()
                    section_sizes = (
                        SectionSize(
                            "journal",
                            sum(len(part) for part in self._journal_json),
                        ),
                        SectionSize(
                            "records",
                            sum(len(self._record_json[sid]) for sid in self._records),
                        ),
                        SectionSize("frontiers", len(frontiers_json)),
                        SectionSize("hierarchy_version", 24),
                        SectionSize("next_swing_id", 24),
                        SectionSize("checkpoint_version", 24),
                    )
                    set_hierarchy_footprint(
                        payload=payload,
                        json_size_bytes=json_size_bytes,
                        section_sizes=section_sizes,
                    )
            except Exception:
                pass

    def restore(self, path: Path | None = None) -> None:
        """Restore an exact hierarchy checkpoint without rebuilding history."""
        source = path or self._checkpoint_path
        if source is None:
            raise ValueError("checkpoint path is required")
        payload = json.loads(source.read_text(encoding="utf-8"))
        checkpoint_version = payload.get("checkpoint_version")
        if checkpoint_version not in {1, CHECKPOINT_VERSION}:
            raise ValueError("unsupported structural hierarchy checkpoint version")

        records = {
            item["swing_id"]: self._record_from_payload(
                item, checkpoint_version=checkpoint_version
            )
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
        self._displaced_by_new = {}
        self._next_swing_id = payload["next_swing_id"]
        self._version = payload["hierarchy_version"]
        self._rebuild_json_caches()
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
            parent_id, depth, displaced_ids = self._assign_parent(side, swing.price)
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
                lifecycle=LifecycleState.NEW,
                challenge_started_at=None,
                challenge_extreme_price=None,
                challenge_evidence=(),
                transition_cause="SWING_CONFIRMED",
                transition_time=inputs.timestamp,
                created_sequence=self._version + 1,
                last_transition_sequence=self._version + 1,
            )
            self._put_record(record)
            self._fingerprints[fingerprint] = swing_id
            self._frontiers[side].append(swing_id)
            self._displaced_by_new[swing_id] = displaced_ids
            new_ids.append(swing_id)
        return new_ids

    def _assign_parent(
        self, side: SwingSide, price: float
    ) -> tuple[int | None, int, tuple[int, ...]]:
        frontier = self._frontiers[side]
        displaced: list[int] = []
        if side is SwingSide.HIGH:
            while frontier and self._records[frontier[-1]].price <= price:
                displaced.append(frontier.pop())
        else:
            while frontier and self._records[frontier[-1]].price >= price:
                displaced.append(frontier.pop())
        parent_id = frontier[-1] if frontier else None
        depth = self._records[parent_id].depth + 1 if parent_id is not None else 0
        return parent_id, depth, tuple(displaced)

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
                challenge_started_at=record.challenge_started_at,
                challenge_extreme_price=record.challenge_extreme_price,
                challenge_evidence=record.challenge_evidence,
                transition_cause=record.transition_cause,
                transition_time=record.transition_time,
                created_sequence=record.created_sequence,
                last_transition_sequence=self._version + 1,
            )
            self._put_record(classified)
            self._append_transition(
                timestamp=inputs.timestamp,
                cause="SWING_CONFIRMED",
                swing_id=swing_id,
                old_state=None,
                new_state=_state(classified),
                evidence={
                    "parent_id": classified.parent_id,
                    "classification_version": CLASSIFICATION_VERSION,
                    "displaced_swing_ids": list(
                        self._displaced_by_new.get(swing_id, ())
                    ),
                },
            )

    def _activate_new(
        self, new_ids: list[int], inputs: ObjectiveDiagnosticsInputs
    ) -> None:
        for swing_id in new_ids:
            self._transition_lifecycle(
                swing_id,
                LifecycleState.ACTIVE,
                timestamp=inputs.timestamp,
                cause="OBJECTIVE_STRUCTURE_ACTIVATED",
                evidence={"classification_version": CLASSIFICATION_VERSION},
            )

    def _apply_supersession(
        self, new_ids: list[int], inputs: ObjectiveDiagnosticsInputs
    ) -> None:
        for new_id in new_ids:
            new = self._records[new_id]
            if (
                new.category is not CandidateCategory.MAJOR
                or new.parent_id is not None
            ):
                continue
            for old_id in self._displaced_by_new.get(new_id, ()):
                # Initial checkpoint hydration classifies one complete existing
                # landscape; only a later event may replace its governing node.
                if old_id in new_ids:
                    continue
                old = self._records[old_id]
                if (
                    old.category is not CandidateCategory.MAJOR
                    or old.lifecycle
                    not in {LifecycleState.ACTIVE, LifecycleState.CHALLENGED}
                ):
                    continue
                self._transition_lifecycle(
                    old_id,
                    LifecycleState.SUPERSEDED,
                    timestamp=inputs.timestamp,
                    cause="HIERARCHY_GOVERNING_REPLACEMENT",
                    evidence={
                        "superseding_swing_id": new_id,
                        "displaced_from_frontier": True,
                    },
                )

    def _resolve_challenges(
        self, new_ids: list[int], inputs: ObjectiveDiagnosticsInputs
    ) -> None:
        """Resolve challenges only from newly confirmed opposite-side structure."""
        challenged_ids = [
            swing_id
            for swing_id, record in sorted(self._records.items())
            if record.lifecycle is LifecycleState.CHALLENGED
        ]
        for challenged_id in challenged_ids:
            challenged = self._records[challenged_id]
            for evidence_id in new_ids:
                evidence_record = self._records[evidence_id]
                if evidence_record.side is challenged.side:
                    continue
                if challenged.side is SwingSide.HIGH:
                    accepted = (
                        evidence_record.price > challenged.price
                        and inputs.current_price > challenged.price
                    )
                    reclaimed = (
                        evidence_record.price < challenged.price
                        and inputs.current_price < challenged.price
                    )
                else:
                    accepted = (
                        evidence_record.price < challenged.price
                        and inputs.current_price < challenged.price
                    )
                    reclaimed = (
                        evidence_record.price > challenged.price
                        and inputs.current_price > challenged.price
                    )
                if accepted:
                    self._transition_lifecycle(
                        challenged_id,
                        LifecycleState.CONFIRMED_BROKEN,
                        timestamp=inputs.timestamp,
                        cause="FAR_SIDE_ACCEPTANCE_CONFIRMED",
                        evidence={
                            "acceptance_swing_id": evidence_id,
                            "acceptance_price": evidence_record.price,
                            "current_price": inputs.current_price,
                        },
                    )
                    break
                if reclaimed:
                    self._transition_lifecycle(
                        challenged_id,
                        LifecycleState.ACTIVE,
                        timestamp=inputs.timestamp,
                        cause="RECLAIM_CONFIRMED",
                        evidence={
                            "reclaim_swing_id": evidence_id,
                            "reclaim_price": evidence_record.price,
                            "current_price": inputs.current_price,
                        },
                    )
                    break

    def _apply_challenges(self, inputs: ObjectiveDiagnosticsInputs) -> None:
        """A trade-through challenges an objective; it never kills it."""
        for swing_id in sorted(self._records):
            record = self._records[swing_id]
            penetrated = (
                record.side is SwingSide.HIGH
                and inputs.current_price > record.price
            ) or (
                record.side is SwingSide.LOW
                and inputs.current_price < record.price
            )
            if not penetrated:
                continue
            if record.lifecycle is LifecycleState.ACTIVE:
                self._transition_lifecycle(
                    swing_id,
                    LifecycleState.CHALLENGED,
                    timestamp=inputs.timestamp,
                    cause="PRICE_TRADE_THROUGH",
                    evidence={
                        "penetration_price": inputs.current_price,
                        "current_price": inputs.current_price,
                    },
                )
            elif record.lifecycle is LifecycleState.CHALLENGED:
                previous_extreme = record.challenge_extreme_price
                extends = previous_extreme is None or (
                    record.side is SwingSide.HIGH
                    and inputs.current_price > previous_extreme
                ) or (
                    record.side is SwingSide.LOW
                    and inputs.current_price < previous_extreme
                )
                if extends:
                    self._extend_challenge(
                        swing_id,
                        timestamp=inputs.timestamp,
                        penetration_price=inputs.current_price,
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
        challenge_started_at = old.challenge_started_at
        challenge_extreme_price = old.challenge_extreme_price
        challenge_evidence = old.challenge_evidence
        if lifecycle is LifecycleState.CHALLENGED:
            penetration = float(evidence["penetration_price"])
            challenge_started_at = timestamp
            challenge_extreme_price = penetration
            challenge_evidence = (
                f"Trade-through at {penetration}",
                f"Objective price {old.price}",
            )
        elif cause == "RECLAIM_CONFIRMED":
            challenge_evidence = challenge_evidence + (
                f"Reclaim swing {evidence['reclaim_swing_id']} at "
                f"{evidence['reclaim_price']}",
            )
        elif cause == "FAR_SIDE_ACCEPTANCE_CONFIRMED":
            challenge_evidence = challenge_evidence + (
                f"Acceptance swing {evidence['acceptance_swing_id']} at "
                f"{evidence['acceptance_price']}",
            )
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
            challenge_started_at=challenge_started_at,
            challenge_extreme_price=challenge_extreme_price,
            challenge_evidence=challenge_evidence,
            transition_cause=cause,
            transition_time=timestamp,
            created_sequence=old.created_sequence,
            last_transition_sequence=self._version + 1,
        )
        self._put_record(updated)
        self._append_transition(
            timestamp=timestamp,
            cause=cause,
            swing_id=swing_id,
            old_state=_state(old),
            new_state=_state(updated),
            evidence=evidence,
        )

    def _extend_challenge(
        self, swing_id: int, *, timestamp: float, penetration_price: float
    ) -> None:
        old = self._records[swing_id]
        evidence_lines = old.challenge_evidence + (
            f"Extended to {penetration_price}",
        )
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
            lifecycle=old.lifecycle,
            challenge_started_at=old.challenge_started_at,
            challenge_extreme_price=penetration_price,
            challenge_evidence=evidence_lines,
            transition_cause="CHALLENGE_EXTENDED",
            transition_time=timestamp,
            created_sequence=old.created_sequence,
            last_transition_sequence=self._version + 1,
        )
        self._put_record(updated)
        self._append_transition(
            timestamp=timestamp,
            cause="CHALLENGE_EXTENDED",
            swing_id=swing_id,
            old_state=_state(old),
            new_state=_state(updated),
            evidence={"penetration_price": penetration_price},
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
        transition = StructuralTransition(
            sequence=self._version,
            timestamp=timestamp,
            cause=cause,
            swing_id=swing_id,
            old_state=old_state,
            new_state=new_state,
            evidence=dict(evidence),
        )
        self._journal.append(transition)
        self._journal_json.append(self._encode_json(self._transition_payload(transition)))

    def _put_record(self, record: StructuralSwingRecord) -> None:
        """Store a registry record and refresh its cached JSON fragment."""
        self._records[record.swing_id] = record
        self._record_json[record.swing_id] = self._encode_json(
            self._record_payload(record)
        )

    def _ensure_json_caches(self) -> None:
        """Fill any missing fragment caches (safety for restore/edge paths)."""
        if len(self._record_json) != len(self._records):
            for swing_id, record in self._records.items():
                if swing_id not in self._record_json:
                    self._record_json[swing_id] = self._encode_json(
                        self._record_payload(record)
                    )
        if len(self._journal_json) != len(self._journal):
            self._journal_json = [
                self._encode_json(self._transition_payload(item))
                for item in self._journal
            ]

    def _rebuild_json_caches(self) -> None:
        """Rebuild all JSON fragments after restore."""
        self._record_json = {
            swing_id: self._encode_json(self._record_payload(record))
            for swing_id, record in self._records.items()
        }
        self._journal_json = [
            self._encode_json(self._transition_payload(item))
            for item in self._journal
        ]

    def _frontiers_json(self) -> str:
        frontiers = {
            side.value: list(ids) for side, ids in self._frontiers.items()
        }
        return self._encode_json(frontiers)

    def _assemble_checkpoint_document(self) -> str:
        """Assemble checkpoint JSON identical to json.dumps(..., sort_keys=True).

        Top-level keys are emitted in alphabetical order matching sort_keys.
        Record and journal fragments were already encoded with sort_keys=True.
        """
        records_json = ",".join(
            self._record_json[swing_id] for swing_id in sorted(self._records)
        )
        journal_json = ",".join(self._journal_json)
        frontiers_json = self._frontiers_json()
        return (
            "{"
            f'"checkpoint_version":{CHECKPOINT_VERSION},'
            f'"frontiers":{frontiers_json},'
            f'"hierarchy_version":{self._version},'
            f'"journal":[{journal_json}],'
            f'"next_swing_id":{self._next_swing_id},'
            f'"records":[{records_json}]'
            "}"
        )

    def _classic_checkpoint_document(self) -> str:
        """Reference serializer used only to prove byte-identical output."""
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
        return self._encode_json(payload)

    @staticmethod
    def _encode_json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

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
                    challenge_state=self._challenge_state(record),
                    challenge_evidence=record.challenge_evidence,
                    transition_cause=record.transition_cause,
                    transition_time=record.transition_time,
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
    def _challenge_state(record: StructuralSwingRecord) -> str:
        if record.lifecycle is LifecycleState.CHALLENGED:
            return "UNDER_CHALLENGE"
        if record.transition_cause == "RECLAIM_CONFIRMED":
            return "RECLAIMED"
        if record.lifecycle is LifecycleState.CONFIRMED_BROKEN:
            return "CONFIRMED_BROKEN"
        if record.challenge_started_at is not None:
            return "RESOLVED"
        return "NONE"

    @staticmethod
    def _record_payload(record: StructuralSwingRecord) -> dict[str, object]:
        # Explicit fields (same content as asdict + enum .value). Avoid asdict cost.
        return {
            "swing_id": record.swing_id,
            "fingerprint": record.fingerprint,
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
            "challenge_started_at": record.challenge_started_at,
            "challenge_extreme_price": record.challenge_extreme_price,
            "challenge_evidence": list(record.challenge_evidence),
            "transition_cause": record.transition_cause,
            "transition_time": record.transition_time,
            "created_sequence": record.created_sequence,
            "last_transition_sequence": record.last_transition_sequence,
        }

    @staticmethod
    def _record_from_payload(
        item: Mapping[str, object], *, checkpoint_version: int
    ) -> StructuralSwingRecord:
        lifecycle_value = str(item["lifecycle"])
        if checkpoint_version == 1 and lifecycle_value == "BREACHED":
            lifecycle_value = LifecycleState.CHALLENGED.value
        migrated_challenge = (
            checkpoint_version == 1
            and lifecycle_value == LifecycleState.CHALLENGED.value
        )
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
            lifecycle=LifecycleState(lifecycle_value),
            challenge_started_at=(
                None
                if item.get("challenge_started_at") is None
                else float(item["challenge_started_at"])
            ),
            challenge_extreme_price=(
                None
                if item.get("challenge_extreme_price") is None
                else float(item["challenge_extreme_price"])
            ),
            challenge_evidence=tuple(
                str(value) for value in item.get("challenge_evidence", ())
            )
            or (
                ("Migrated from H-2 BREACHED state",)
                if migrated_challenge
                else ()
            ),
            transition_cause=str(
                item.get(
                    "transition_cause",
                    "H2_BREACH_MIGRATED_TO_CHALLENGE"
                    if migrated_challenge
                    else "CHECKPOINT_RESTORED",
                )
            ),
            transition_time=float(item.get("transition_time", 0.0)),
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
