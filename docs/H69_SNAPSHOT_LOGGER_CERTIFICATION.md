# Sprint H-6.9 — Snapshot Logger Certification

**VERDICT: PARTIALLY CONFIRMED**

Evidence only. No optimization. No behavior / API / persistence changes.  
Suite: **570 passed**. Samples: **100** accepted ticks (seeded swings + SnapshotLogger + checkpoints).

---

## Architecture (post H-6.8.2)

```
Accepted Tick
  → bars / swings
  → pipeline.evaluate
       → hierarchy.evaluate (once)
       → ObjectiveAuditReport reference → ValidatorFrame.objective_diagnostics
       → Initiative / Response / Continuation / Break
       → checkpoints (initiative + hierarchy when version bumps)
  → SnapshotLogger.log(frame)
       1. Frame preparation          (_jsonable non-diagnostics fields)
       2. Objective diagnostics      (_jsonable objective_diagnostics)
       3. Serialization              (json.dumps)
       4. NDJSON write
       5. Flush
       6. Rotation check             (stat / maybe rotate)
       7. Reopen                     (only if rotation occurred)
```

---

## Timing table (ms)

| Phase | N | Min | Max | Avg | Med | P95 | P99 | Std | Total |
|-------|--:|----:|----:|----:|----:|----:|----:|----:|------:|
| Frame preparation | 100 | 0.0225 | 0.0451 | 0.0273 | 0.0278 | 0.0308 | 0.0411 | 0.0032 | 2.7341 |
| Objective diagnostics attachment | 100 | 0.0294 | 0.2992 | 0.1542 | 0.1534 | 0.2633 | 0.2751 | 0.0737 | 15.4164 |
| Serialization | 100 | 0.0233 | 0.1142 | 0.0637 | 0.0645 | 0.0957 | 0.1136 | 0.0231 | 6.3744 |
| NDJSON write | 100 | 0.0002 | 0.0172 | 0.0083 | 0.0093 | 0.0128 | 0.0138 | 0.0037 | 0.8350 |
| Flush | 100 | 0.0016 | 0.0562 | 0.0033 | 0.0018 | 0.0088 | 0.0228 | 0.0060 | 0.3318 |
| Rotation check | 100 | 0.0063 | 0.0151 | 0.0074 | 0.0070 | 0.0096 | 0.0123 | 0.0012 | 0.7426 |
| Reopen | 100 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| **Total Snapshot Logger** | 100 | 0.1022 | 0.4412 | **0.2693** | 0.2676 | 0.4139 | 0.4411 | 0.0968 | 26.9326 |

---

## Phase ranking (share of logger total)

| Rank | Phase | % of logger |
|-----:|-------|------------:|
| 1 | Objective diagnostics attachment | **57.24%** |
| 2 | Serialization | 23.67% |
| 3 | Frame preparation | 10.15% |
| 4 | NDJSON write | 3.10% |
| 5 | Rotation check | 2.76% |
| 6 | Flush | 1.23% |
| 7 | Reopen | 0.00% |

**Hottest internal phase:** Objective diagnostics attachment (`_jsonable` of diagnostics).

---

## Correlation / contribution

| Metric | Value |
|--------|------:|
| Mean logger | 0.2693 ms |
| Mean loop | 1.0710 ms |
| Mean poll_once | 1.0700 ms |
| Mean checkpoint | 0.2835 ms |
| **Logger share of loop** | **25.15% → class `25–50%`** |
| Corr(logger, loop) | 0.4210 |
| Corr(logger, poll) | 0.4212 |
| Corr(logger, checkpoint) | −0.1087 |

Checkpoint mean (0.28 ms) ≈ logger mean (0.27 ms) in this harness — logger is a major cost but not alone.

---

## Contribution classification

**25–50% of Loop Time**

---

## Verdict definition used

| Verdict | Rule |
|---------|------|
| CONFIRMED | mean logger / loop **> 50%** |
| PARTIALLY CONFIRMED | **25–50%**, or ≥10% with logger still material |
| REJECTED | **< 25%** and not primary |

---

## Conclusion

# PARTIALLY CONFIRMED

Snapshot Logger is a **material** post–H-6.8.2 cost (~¼ of per-tick loop time in this evidence set) and its dominant internal hotspot is **serializing `objective_diagnostics` into the NDJSON payload**, but it is **not** the sole primary bottleneck (>50% of loop): checkpoint cost is comparable.
