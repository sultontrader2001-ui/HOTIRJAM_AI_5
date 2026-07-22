"""H-6.9.1 — Recursive _jsonable audit for objective_diagnostics (evidence only).

Produces byte-identical results to live_validator.logger._jsonable while
recording per-node timings and structural metrics. Never changes persistence.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class PathAggregate:
    path: str
    node_type: str
    count: int
    self_ms: float
    children_ms: float
    total_ms: float
    max_depth: int


@dataclass(frozen=True, slots=True)
class TypeAggregate:
    node_type: str
    count: int
    self_ms: float
    children_ms: float
    total_ms: float


@dataclass(frozen=True, slots=True)
class JsonableAuditSnapshot:
    """One audited conversion of objective_diagnostics."""

    root_serialized_bytes: int
    object_count: int
    field_count: int
    max_nesting_depth: int
    list_count: int
    tuple_as_list_count: int
    dataclass_count: int
    dict_count: int
    enum_count: int
    string_count: int
    primitive_count: int
    none_count: int
    repeated_object_ids: int
    unique_object_ids: int
    wall_ms: float
    path_aggregates: tuple[PathAggregate, ...]
    type_aggregates: tuple[TypeAggregate, ...]
    top_hottest_paths: tuple[PathAggregate, ...]
    largest_path: str | None
    deepest_path: str | None
    most_expensive_path: str | None
    most_frequent_path: str | None
    largest_serialized_section: str | None
    largest_serialized_section_bytes: int | None
    section_sizes: tuple[tuple[str, int], ...]
    cause_class: str
    verdict: str


_enabled = True
_latest: JsonableAuditSnapshot | None = None
_history: list[JsonableAuditSnapshot] = []


def reset_jsonable_audit_for_tests() -> None:
    global _latest, _history, _enabled
    _latest = None
    _history = []
    _enabled = True


def set_jsonable_audit_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = bool(enabled)


def latest_jsonable_audit() -> JsonableAuditSnapshot | None:
    return _latest


def jsonable_audit_history() -> tuple[JsonableAuditSnapshot, ...]:
    return tuple(_history)


def _node_type_name(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, Enum):
        return "enum"
    if is_dataclass(value) and not isinstance(value, type):
        return "dataclass"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return type(value).__name__


class _AuditBuilder:
    __slots__ = (
        "object_count",
        "field_count",
        "max_depth",
        "list_count",
        "tuple_count",
        "dataclass_count",
        "dict_count",
        "enum_count",
        "string_count",
        "primitive_count",
        "none_count",
        "seen_ids",
        "repeated_ids",
        "path_rows",
        "type_rows",
        "depth_by_path",
    )

    def __init__(self) -> None:
        self.object_count = 0
        self.field_count = 0
        self.max_depth = 0
        self.list_count = 0
        self.tuple_count = 0
        self.dataclass_count = 0
        self.dict_count = 0
        self.enum_count = 0
        self.string_count = 0
        self.primitive_count = 0
        self.none_count = 0
        self.seen_ids: set[int] = set()
        self.repeated_ids = 0
        # path -> [type, count, self, children, total, max_depth]
        self.path_rows: dict[str, list[Any]] = {}
        self.type_rows: dict[str, list[float]] = {}
        self.depth_by_path: dict[str, int] = {}

    def _bump_type(self, ntype: str, self_ms: float, children_ms: float, total_ms: float) -> None:
        row = self.type_rows.get(ntype)
        if row is None:
            self.type_rows[ntype] = [1.0, self_ms, children_ms, total_ms]
        else:
            row[0] += 1.0
            row[1] += self_ms
            row[2] += children_ms
            row[3] += total_ms

    def _bump_path(
        self,
        path: str,
        ntype: str,
        self_ms: float,
        children_ms: float,
        total_ms: float,
        depth: int,
    ) -> None:
        row = self.path_rows.get(path)
        if row is None:
            self.path_rows[path] = [ntype, 1, self_ms, children_ms, total_ms, depth]
        else:
            row[1] += 1
            row[2] += self_ms
            row[3] += children_ms
            row[4] += total_ms
            if depth > row[5]:
                row[5] = depth
        prev = self.depth_by_path.get(path, 0)
        if depth > prev:
            self.depth_by_path[path] = depth

    def convert(self, value: Any, path: str, depth: int) -> tuple[Any, float]:
        """Return ``(jsonable_value, total_ms)`` identical to logger._jsonable."""
        self.object_count += 1
        if depth > self.max_depth:
            self.max_depth = depth

        oid = id(value)
        # Only track container identities for repeated-conversion detection.
        if not isinstance(value, (str, bytes, int, float, bool, type(None), Enum)):
            if oid in self.seen_ids:
                self.repeated_ids += 1
            else:
                self.seen_ids.add(oid)

        t0 = time.perf_counter()
        children_ms = 0.0
        ntype = _node_type_name(value)

        if value is None:
            self.none_count += 1
            self.primitive_count += 1
            result: Any = None
        elif isinstance(value, Enum):
            self.enum_count += 1
            result = value.value
        elif is_dataclass(value) and not isinstance(value, type):
            self.dataclass_count += 1
            items: list[tuple[str, Any]] = []
            for f in fields(value):
                self.field_count += 1
                child_path = f"{path}.{f.name}"
                child, child_total = self.convert(getattr(value, f.name), child_path, depth + 1)
                children_ms += child_total
                items.append((f.name, child))
            items.sort(key=lambda item: item[0])
            result = {key: val for key, val in items}
        elif isinstance(value, tuple):
            self.tuple_count += 1
            self.list_count += 1  # serialized as JSON array
            out_list: list[Any] = []
            for index, item in enumerate(value):
                child, child_total = self.convert(item, f"{path}[{index}]", depth + 1)
                children_ms += child_total
                out_list.append(child)
            result = out_list
        elif isinstance(value, list):
            self.list_count += 1
            out_list = []
            for index, item in enumerate(value):
                child, child_total = self.convert(item, f"{path}[{index}]", depth + 1)
                children_ms += child_total
                out_list.append(child)
            result = out_list
        elif isinstance(value, dict):
            self.dict_count += 1
            items = []
            for key, item in value.items():
                child, child_total = self.convert(item, f"{path}.{key}", depth + 1)
                children_ms += child_total
                items.append((str(key), child))
            items.sort(key=lambda item: item[0])
            result = {key: val for key, val in items}
        elif isinstance(value, str):
            self.string_count += 1
            result = value
        else:
            self.primitive_count += 1
            result = value

        total_ms = (time.perf_counter() - t0) * 1000.0
        self_ms = max(0.0, total_ms - children_ms)
        self._bump_path(path, ntype, self_ms, children_ms, total_ms, depth)
        self._bump_type(ntype, self_ms, children_ms, total_ms)
        return result, total_ms


def _classify_cause(snap_parts: dict[str, Any]) -> tuple[str, str]:
    """Return (cause_class, verdict) from structural evidence."""
    reasons: list[str] = []
    if snap_parts["repeated_object_ids"] > 0:
        reasons.append("Repeated conversion")
    # Duplicate traversal: same path visited >1 in a single tree (aggregates count>1
    # for leaf paths that aren't under a loop). For list indices each path is unique
    # per visit; dataclass root fields count==1. Use repeated_ids instead.
    if snap_parts["max_nesting_depth"] >= 4:
        reasons.append("Deep recursion")
    if snap_parts["list_or_tuple"] >= 8 or snap_parts["dataclass_count"] >= 8:
        reasons.append("Large collections")
    if snap_parts["root_serialized_bytes"] >= 2_000:
        reasons.append("Large object")
    if snap_parts["dataclass_count"] >= 5 and snap_parts["field_count"] >= 50:
        reasons.append("Large object")

    # Primary label preference.
    if "Large collections" in reasons and "Large object" in reasons:
        cause = "Large collections"
    elif reasons:
        # Prefer most specific first match in priority order.
        priority = (
            "Repeated conversion",
            "Duplicate traversal",
            "Large collections",
            "Deep recursion",
            "Large object",
            "Other",
        )
        cause = next((p for p in priority if p in reasons), reasons[0])
    else:
        cause = "Other"

    if cause in {"Large collections", "Large object", "Deep recursion", "Repeated conversion"}:
        # Clear primary structural explanation of the hot phase.
        if len(reasons) == 1 or (
            cause == "Large collections" and snap_parts["dataclass_share"] >= 0.4
        ):
            verdict = "CONFIRMED"
        else:
            verdict = "PARTIALLY CONFIRMED"
    elif cause == "Other":
        verdict = "REJECTED"
    else:
        verdict = "PARTIALLY CONFIRMED"
    return cause, verdict


def jsonable_with_audit(value: Any, *, root_path: str = "objective_diagnostics") -> Any:
    """Convert identically to ``_jsonable`` and record an audit snapshot."""
    global _latest
    if not _enabled:
        # Fall back without audit (caller still needs conversion).
        from hotirjam_ai5.live_validator.logger import _jsonable

        return _jsonable(value)

    builder = _AuditBuilder()
    _wall0 = time.perf_counter()
    converted, _total = builder.convert(value, root_path, 0)
    wall_ms = (time.perf_counter() - _wall0) * 1000.0

    encoded_root = json.dumps(converted, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    section_sizes: list[tuple[str, int]] = []
    if isinstance(converted, dict):
        for key, section in converted.items():
            raw = json.dumps(section, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            section_sizes.append((f"{root_path}.{key}", len(raw)))
        section_sizes.sort(key=lambda item: item[1], reverse=True)

    path_aggs = [
        PathAggregate(
            path=path,
            node_type=str(row[0]),
            count=int(row[1]),
            self_ms=float(row[2]),
            children_ms=float(row[3]),
            total_ms=float(row[4]),
            max_depth=int(row[5]),
        )
        for path, row in builder.path_rows.items()
    ]
    path_aggs.sort(key=lambda item: item.total_ms, reverse=True)

    type_aggs = [
        TypeAggregate(
            node_type=ntype,
            count=int(row[0]),
            self_ms=float(row[1]),
            children_ms=float(row[2]),
            total_ms=float(row[3]),
        )
        for ntype, row in builder.type_rows.items()
    ]
    type_aggs.sort(key=lambda item: item.total_ms, reverse=True)

    largest_path = None
    if section_sizes:
        # Prefer structural path with largest encoded child section among top containers.
        largest_path = section_sizes[0][0]
    elif path_aggs:
        largest_path = path_aggs[0].path

    deepest_path = None
    if builder.depth_by_path:
        deepest_path = max(builder.depth_by_path.items(), key=lambda kv: kv[1])[0]

    most_expensive = path_aggs[0].path if path_aggs else None
    most_frequent = None
    if path_aggs:
        most_frequent = max(path_aggs, key=lambda item: item.count).path

    largest_section = section_sizes[0][0] if section_sizes else None
    largest_section_bytes = section_sizes[0][1] if section_sizes else None

    dc_share = 0.0
    if type_aggs:
        total_type = sum(t.total_ms for t in type_aggs) or 1.0
        dc = next((t for t in type_aggs if t.node_type == "dataclass"), None)
        if dc is not None:
            dc_share = dc.total_ms / total_type

    cause, verdict = _classify_cause(
        {
            "repeated_object_ids": builder.repeated_ids,
            "max_nesting_depth": builder.max_depth,
            "list_or_tuple": builder.list_count,
            "dataclass_count": builder.dataclass_count,
            "root_serialized_bytes": len(encoded_root),
            "field_count": builder.field_count,
            "dataclass_share": dc_share,
        }
    )

    snap = JsonableAuditSnapshot(
        root_serialized_bytes=len(encoded_root),
        object_count=builder.object_count,
        field_count=builder.field_count,
        max_nesting_depth=builder.max_depth,
        list_count=builder.list_count,
        tuple_as_list_count=builder.tuple_count,
        dataclass_count=builder.dataclass_count,
        dict_count=builder.dict_count,
        enum_count=builder.enum_count,
        string_count=builder.string_count,
        primitive_count=builder.primitive_count,
        none_count=builder.none_count,
        repeated_object_ids=builder.repeated_ids,
        unique_object_ids=len(builder.seen_ids),
        wall_ms=wall_ms,
        path_aggregates=tuple(path_aggs),
        type_aggregates=tuple(type_aggs),
        top_hottest_paths=tuple(path_aggs[:20]),
        largest_path=largest_path,
        deepest_path=deepest_path,
        most_expensive_path=most_expensive,
        most_frequent_path=most_frequent,
        largest_serialized_section=largest_section,
        largest_serialized_section_bytes=largest_section_bytes,
        section_sizes=tuple(section_sizes[:12]),
        cause_class=cause,
        verdict=verdict,
    )
    _latest = snap
    _history.append(snap)
    return converted


def render_jsonable_audit_report(snap: JsonableAuditSnapshot | None = None) -> str:
    snap = snap or _latest
    if snap is None:
        return "H-6.9.1 Jsonable Audit\nVERDICT: REJECTED\nNo samples.\n"

    lines = [
        "HOTIRJAM AI 5",
        "Sprint H-6.9.1 — Objective Diagnostics Serialization Audit",
        "====================================================",
        "EVIDENCE REPORT",
        "====================================================",
        "",
        f"VERDICT: {snap.verdict}",
        f"Cause class: {snap.cause_class}",
        "",
        "ARCHITECTURE",
        "  SnapshotLogger.log",
        "    → _jsonable(frame fields)",
        "    → objective_diagnostics  ← audited recursive conversion",
        "         Enum / dataclass / tuple|list / dict / primitives",
        "    → json.dumps(payload)",
        "",
        "ROOT METRICS",
        f"  Root serialized size...... {snap.root_serialized_bytes} bytes",
        f"  Object count.............. {snap.object_count}",
        f"  Field count (dataclass)... {snap.field_count}",
        f"  Max nesting depth......... {snap.max_nesting_depth}",
        f"  Lists (JSON arrays)....... {snap.list_count}",
        f"  Tuples (as arrays)........ {snap.tuple_as_list_count}",
        f"  Dataclasses............... {snap.dataclass_count}",
        f"  Dicts..................... {snap.dict_count}",
        f"  Enums..................... {snap.enum_count}",
        f"  Strings................... {snap.string_count}",
        f"  Primitives (non-str)...... {snap.primitive_count}",
        f"  None...................... {snap.none_count}",
        f"  Unique container ids...... {snap.unique_object_ids}",
        f"  Repeated container ids.... {snap.repeated_object_ids}",
        f"  Wall conversion ms........ {snap.wall_ms:.4f}",
        "",
        "TYPE TIMING TREE (total_ms desc)",
        f"{'Type':<14} {'Count':>8} {'Self':>10} {'Children':>10} {'Total':>10} {'%':>8}",
    ]
    type_total = sum(t.total_ms for t in snap.type_aggregates) or 1.0
    for t in snap.type_aggregates:
        lines.append(
            f"{t.node_type:<14} {t.count:>8} {t.self_ms:>10.4f} {t.children_ms:>10.4f} "
            f"{t.total_ms:>10.4f} {(t.total_ms / type_total) * 100:>7.2f}%"
        )

    lines.extend(
        [
            "",
            "TOP 20 HOTTEST OBJECT PATHS (by total_ms)",
            f"{'Path':<52} {'Type':<10} {'N':>5} {'Self':>9} {'Child':>9} {'Total':>9}",
        ]
    )
    path_total = sum(p.total_ms for p in snap.top_hottest_paths) or 1.0
    for p in snap.top_hottest_paths:
        lines.append(
            f"{p.path:<52} {p.node_type:<10} {p.count:>5} {p.self_ms:>9.4f} "
            f"{p.children_ms:>9.4f} {p.total_ms:>9.4f}"
        )

    lines.extend(
        [
            "",
            "SECTION SIZES (serialized)",
        ]
    )
    for name, size in snap.section_sizes:
        lines.append(f"  {name:<48} {size} bytes")

    lines.extend(
        [
            "",
            "SUMMARY OBJECTS",
            f"  Largest object/path......... {snap.largest_path}",
            f"  Deepest object/path......... {snap.deepest_path}",
            f"  Most expensive path......... {snap.most_expensive_path}",
            f"  Most frequently converted... {snap.most_frequent_path}",
            f"  Largest serialized section.. {snap.largest_serialized_section} "
            f"({snap.largest_serialized_section_bytes} bytes)",
            "",
            f"Top-path contribution vs audited wall: "
            f"{(snap.top_hottest_paths[0].total_ms / path_total) * 100:.2f}% of top-20 sum"
            if snap.top_hottest_paths
            else "  (no paths)",
            "",
        ]
    )
    return "\n".join(lines)


def merge_history_verdict(
    history: tuple[JsonableAuditSnapshot, ...] | None = None,
) -> tuple[str, str]:
    """Majority cause/verdict across samples for the sprint conclusion."""
    history = history or tuple(_history)
    if not history:
        return "Other", "REJECTED"
    # Use the latest non-empty diagnostics sample preferentially.
    nonempty = [s for s in history if s.object_count > 1]
    pick = nonempty[-1] if nonempty else history[-1]
    return pick.cause_class, pick.verdict
