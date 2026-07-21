# Sprint 37 — Entry Timing Audit

**Status:** AUDIT ONLY  
**Scope:** Observe `BUY_INTERNAL` / `SELL_INTERNAL` post-entry price path.  
**Non-goals:** No Trade Decision changes, no threshold changes, no broker/orders.

---

## 1. Timing report (methodology + instrumentation)

### What is recorded for every internal signal

| Field | Source |
|-------|--------|
| Signal | `BUY_INTERNAL` or `SELL_INTERNAL` (edge-triggered) |
| Entry Price | Live market last price at signal open |
| Entry Time | UTC epoch at signal open |
| Checkpoints | 30s, 1m, 2m, 3m, 5m — price + signed points from entry |
| MFE | Maximum Favorable Excursion in first 5 minutes |
| MAE | Maximum Adverse Excursion in first 5 minutes |

**Signed points**

- BUY: `current_price − entry_price`
- SELL: `entry_price − current_price`

### Example output format

```
Signal     BUY_INTERNAL
Entry      29050.25
30 sec     +1.25
1 min      +3.75
2 min      +6.50
3 min      +9.75
5 min      +14.25
MFE        +14.25
MAE        +0.00
Class      NORMAL
Reason     Price continued in signal direction (5m +14.25, MFE 14.25 ≥ |MAE| 0.00).
```

### Live collection

`EntryTimingAuditor` is wired into `DashboardController` as an analytics observer
(alongside Performance Tracker). Completed audits append to:

`logs/entry_timing_log.jsonl`

No live session JSONL was present in the workspace at audit time. Statistics below
are produced from **controlled synthetic paths** that exercise EARLY / NORMAL / LATE
rules (see unit tests). Re-run the live dashboard for ≥ one session to replace
synthetic evidence with production samples.

---

## 2. MFE / MAE statistics (synthetic validation suite)

From Sprint 37 unit fixtures (`tests/test_entry_timing.py`):

| Scenario | Decision | MFE | MAE | 5m points | Class |
|----------|----------|-----|-----|-----------|-------|
| Strong continuation | BUY | ~+14.25 | ~0.00 | +14.25 | NORMAL |
| Adverse then recover | BUY | ≥+5 | ≤−3 | +5 | EARLY |
| Weak follow-through | BUY | ~+1.5 | ~0 | +1.5 | LATE |
| Down move continuation | SELL | +5.00 | 0.00 | +5.00 | NORMAL |

**Aggregate (2-signal summary fixture)**

| Metric | Value (fixture) |
|--------|-----------------|
| Average MFE | > 0 (continuation-biased fixture) |
| Average MAE | ≥ 0 or near 0 when no adverse sample |
| Avg move 30s / 1m / 2m / 3m / 5m | Positive and increasing when NORMAL paths dominate |

> Production averages must be recomputed from `entry_timing_log.jsonl` after live
> collection. Do not treat synthetic averages as certification evidence.

---

## 3. Entry timing classification

### Rules (deterministic)

| Class | Rule | Reasoning |
|-------|------|-----------|
| **EARLY** | `MAE ≤ −2` AND `MFE ≥ 2` AND `points_5m > 0` | Signal immediately reverses (adverse), but the trend later resumes in the signal direction within 5 minutes. |
| **LATE** | `MFE < 3` AND `points_5m ≤ 2` | Little favorable follow-through after entry — most of the move likely already happened before the signal. |
| **NORMAL** | `points_5m > 0` AND `MFE ≥ \|MAE\|` AND not EARLY | Price continues strongly in the signal direction after entry. |
| **INCONCLUSIVE** | Anything else | Mixed / flat path; insufficient to label EARLY/NORMAL/LATE. |

These classification constants live in `entry_timing/classify.py` and are **audit
constants only**. They are not Trade Decision readiness thresholds (80/85) and must
not be confused with scoring weights.

### Classification findings (from fixtures)

1. **NORMAL** paths show rising checkpoint points and MFE ≫ adverse.
2. **EARLY** paths show a clear MAE dip then recovery — useful for diagnosing
   premature readiness windows or stability that fires before pullback completes.
3. **LATE** paths show muted MFE — useful for diagnosing signals that appear after
   directional physics/liquidity have already been “priced in.”

---

## 4. Recommendations (DO NOT IMPLEMENT in this sprint)

| ID | Recommendation | Why |
|----|----------------|-----|
| R1 | Collect ≥ 100 live internal signals with full 5-minute paths before any timing calibration | Synthetic fixtures prove the auditor; they do not prove live entry quality. |
| R2 | Stratify timing class by side (BUY vs SELL) and by market regime (UP/DOWN state) | Sprint 35 signed state/behavior may shift EARLY/LATE rates asymmetrically. |
| R3 | If live data shows high **EARLY** rate: audit Signal Stability window vs pullback depth — do **not** loosen readiness without evidence | EARLY implies activation before adverse completes. |
| R4 | If live data shows high **LATE** rate: audit whether Physics/Liquidity already peaked before READY — consider earlier diagnostic flags, not blind threshold cuts | LATE implies missed follow-through. |
| R5 | Keep Trade Decision thresholds (80/85, window=3) unchanged until live MFE/MAE distributions are certified | Certification methodology: audit → evidence → one constant → regression → validation. |
| R6 | Correlate Performance Tracker SUCCESS/FAILED with TimingClass | A SUCCESS that is LATE may still be profitable but suboptimal; EARLY FAIL may be timing, not direction. |

---

## Architecture note

```
Trade Decision → BUY_INTERNAL / SELL_INTERNAL / NO_TRADE
        │
        ├─ Performance Tracker (5m binary SUCCESS/FAILED)   [Sprint 32]
        └─ Entry Timing Auditor (checkpoints + MFE/MAE + class) [Sprint 37]
```

Both observers are edge-triggered and analytics-only. Neither modifies Trade Decision.

---

## Files introduced

| File | Role |
|------|------|
| `src/hotirjam_ai5/entry_timing/` | Models, classify, tracker, JSONL log |
| `tests/test_entry_timing.py` | NORMAL / EARLY / LATE / SELL / summary |
| `docs/SPRINT_37_ENTRY_TIMING_AUDIT.md` | This audit deliverable |

Controller wiring: `DashboardController` observes via `EntryTimingAuditor` only.

---

**Sprint 37 complete. No trading fixes implemented.**
