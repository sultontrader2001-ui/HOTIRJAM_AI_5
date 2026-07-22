# Sprint H-6.9.1 — Objective Diagnostics Serialization Audit

**VERDICT: CONFIRMED**  
**Cause class: Large collections**

Evidence only. No optimization, caching, refactoring, or behavior changes.  
Suite: **572 passed**.

---

## Architecture

```
SnapshotLogger.log(frame)
  ├─ _jsonable(non-diagnostics fields)     # frame prep
  └─ _jsonable(objective_diagnostics)      # HOT — audited here
        ├─ dataclass ObjectiveAuditReport
        │    ├─ highs: tuple → JSON array of SwingDiagnostic dataclasses
        │    ├─ lows:  tuple → JSON array of SwingDiagnostic dataclasses
        │    ├─ summary_lines: tuple[str]
        │    └─ scalars / versions
        └─ per SwingDiagnostic: ~18 fields (enums, tuples, primitives)
  → json.dumps(payload) → write → flush → rotate
```

---

## Object tree (logical)

```
objective_diagnostics: ObjectiveAuditReport
├── highs[0..N]: SwingDiagnostic
│     ├── enums (side, lifecycle, category)
│     ├── rejection_reasons[] / challenge_evidence[]
│     └── primitives
├── lows[0..M]: SwingDiagnostic   (same shape)
└── summary_lines[]
```

---

## Root metrics (latest sample, 20+20 seeded swings)

| Metric | Value |
|--------|------:|
| Root serialized size | **28,324 bytes** |
| Object count | **1,326** |
| Dataclass field visits | **874** |
| Max nesting depth | **4** |
| Lists/tuples (JSON arrays) | **99** |
| Dataclasses | **49** |
| Enums | **144** |
| Strings | **499** |
| Primitives (non-str) | **535** |
| Repeated container ids | **72** (shared empty tuples across records) |
| Wall conversion | **1.17 ms** |

---

## Timing tree by node type

| Type | Count | Self ms | Children ms | Total ms | % |
|------|------:|--------:|------------:|---------:|--:|
| **dataclass** | 49 | 0.54 | 1.48 | **2.01** | **55.6%** |
| **tuple** | 99 | 0.25 | 0.98 | **1.23** | **34.0%** |
| string | 499 | 0.16 | 0 | 0.16 | 4.5% |
| float | 339 | 0.13 | 0 | 0.13 | 3.5% |
| int / enum / bool / none | … | … | … | … | ~6% |

---

## Top hottest paths (abbrev.)

| Path | Type | Total ms |
|------|------|---------:|
| `objective_diagnostics` | dataclass | 1.17 |
| `objective_diagnostics.lows` | tuple | 0.45 |
| `objective_diagnostics.highs` | tuple | 0.43 |
| `objective_diagnostics.summary_lines` | tuple | 0.27 |
| `objective_diagnostics.lows[i]` / `highs[i]` | dataclass | ~0.02 each |

---

## Largest / deepest / most expensive

| Question | Answer |
|----------|--------|
| Largest object / section | **`objective_diagnostics.lows`** (10,767 bytes) |
| Next sections | highs 9,712 B; summary_lines 7,666 B |
| Deepest path | `…highs[i].rejection_reasons[j]` (depth 4) |
| Most expensive path | `objective_diagnostics` (root) |
| Most frequently converted path | root / per-element dataclasses (N=1 per path; volume is collection size) |

---

## Cause determination

| Hypothesis | Evidence |
|------------|----------|
| Repeated conversion | Partial — 72 repeated container ids (shared `()` tuples on diagnostics) |
| Duplicate traversal | Not primary — each index path visited once per conversion |
| Large object | Yes — 28 KB root payload |
| Deep recursion | Mild — max depth 4 (not the driver) |
| **Large collections** | **Primary** — `highs`/`lows` arrays of rich `SwingDiagnostic` dataclasses dominate time (dataclass 56% + tuple 34%) |

---

## Contribution

- Dataclass + tuple node work ≈ **90%** of audited conversion time.  
- `lows` + `highs` + `summary_lines` are the three largest serialized sections and the three hottest child paths under the root.

---

## Conclusion

# CONFIRMED

`_jsonable(objective_diagnostics)` is hottest because it recursively converts **large collections** of **dataclass** swing diagnostics (`highs` / `lows`) plus `summary_lines`, producing a multi‑tens‑of‑KB JSON subtree—not because of deep recursion or a second presentation evaluate.
