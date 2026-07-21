# Sprint 42 — Market Memory Live Audit

**Status:** AUDIT ONLY  
**Scope:** Verify Market Memory captures market evolution correctly.  
**Non-goals:** No changes to Decision Engine, Physics, Liquidity, Market State, Behavior, thresholds, or Dashboard.

**Depends on:** Sprint 41 Market Memory v1 (`hotirjam_ai5.memory`).

---

## Evidence source

| Item | Status |
|------|--------|
| Live `mnq_ticks.ndjson` / `mnq_dom.ndjson` on host | **Absent** at audit time (default NinjaTrader HOTIRJAM paths empty) |
| Controlled evolution session | **Used** — 600 ticks / 300 DOM / 150 dashboard frames (~30 s wall) through existing `DashboardController` |
| Raw evidence JSON | `docs/evidence/sprint_42_memory_audit.json` |

Controlled session phases (price + book bias):

1. **Up impulse** (~10 s) — rising ticks, buy-biased DOM  
2. **Chop** (~10 s) — alternating ±0.25, neutral DOM  
3. **Down impulse** (~10 s) — falling ticks, sell-biased DOM  

This validates Memory plumbing and evolution capture. **Replace with a production live session** before certification claims.

---

## 1. Memory timeline

```
t=0s     tick/DOM start → PhysicsAdapter / LiquidityAdapter append
t≈0–10s  UP physics runs · BUY liquidity · STATE tracks UP
t≈10–20s chop → frequent Physics direction flips · Liquidity NEUTRAL
t≈20–30s DOWN physics runs · SELL liquidity · STATE tracks DOWN
each 4th tick → snapshot frame → State / Behavior / Decision append
         (Decision after Trade Decision evaluate — Memory never inputs)
```

| Source | Records | Update frequency | First → last (session) |
|--------|---------|------------------|------------------------|
| PHYSICS | 599 | ~20.0 / s | tick cadence (1st tick skipped — no velocity yet) |
| LIQUIDITY | 300 | ~10.0 / s | every other tick |
| STATE | 150 | ~5.0 / s | dashboard frames |
| BEHAVIOR | 150 | ~5.0 / s | dashboard frames |
| DECISION | 150 | ~5.0 / s | dashboard frames |
| **Total** | **1349** | — | ~30 s · capacity 2048 · no overflow |

### Direction distribution

| Source | Distribution |
|--------|----------------|
| PHYSICS | UP 299 · DOWN 300 |
| LIQUIDITY | BUY 100 · NEUTRAL 100 · SELL 100 |
| STATE | UP 99 · DOWN 50 · NEUTRAL 1 |
| BEHAVIOR | NEUTRAL 115 · BUY 17 · SELL 18 |
| DECISION | NO_TRADE 150 |

### Strength / confidence (summary)

| Source | Strength mean (p50) | Confidence mean (p50) |
|--------|---------------------|------------------------|
| PHYSICS | 80.5 (26.0) | 0.999 (1.0) |
| LIQUIDITY | 0.22 (0.33) | 0.22 (0.33) |
| STATE | 0.97 (1.0) | 1.0 (1.0) |
| BEHAVIOR | 0.88 (1.0) | 1.0 (1.0) |
| DECISION | 62.8 (55.0) score pts | 0.73 (0.65) |

---

## 2. Integrity verification

| Check | Result |
|-------|--------|
| Chronological order (global buffer) | **PASS** — timestamps non-decreasing |
| Missing timestamps | **PASS** — 0 |
| Duplicate timestamps **per source** | **PASS** — 0 for all five sources |
| Duplicate timestamps **global** | Expected — 749 shared wall times across streams at the same instant |
| Mutation of stored items | **PASS** — `MemoryItem` frozen |
| Append-only (non-item rejected) | **PASS** — `TypeError` on dict append |
| Ring buffer overflow | **PASS** — capacity 100 store dropped oldest (kept timestamps 50…149 after 150 appends) |

---

## 3. Persistence / run statistics

| Source | Direction changes | Longest BUY/UP | Longest SELL/DOWN | Avg run length |
|--------|-------------------|----------------|-------------------|----------------|
| PHYSICS | 199 | 200 | 201 | **3.0** |
| LIQUIDITY | 2 | 100 | 100 | 100.0 |
| STATE | 2 | 99 | 50 | 50.0 |
| BEHAVIOR | 67 | 1 | 2 | 2.2 |
| DECISION | 0 | 0 | 0 | 150 (all NO_TRADE) |

### Interpretation (observe only)

- **Physics** longest runs match the designed impulses (~10 s), but **average run length ≈ 3** because the chop phase flips almost every tick — Memory correctly records micro-flippiness (Sprint 39 horizon).  
- **Liquidity** shows long stable phase runs — book bias changes infrequently vs tick physics.  
- **State** persists with the impulse phases and agrees with physics direction (see cross-stream).  
- **Behavior** is noisy / mostly NEUTRAL — short runs; does not stably “follow” state in this session.  
- **Decision** stayed NO_TRADE — Memory recorded decision evolution as inactivity, not INTERNAL activations.

---

## 4. Cross-stream ordering

| Question | Observation (this session) |
|----------|----------------------------|
| Does Physics usually change before Liquidity? | **Yes when liquidity flips** — 1 paired flip; Physics led by ~0.05 s (one tick). Liquidity flips are rare (phase-based). |
| Does Liquidity usually change before Decision? | **No INTERNAL decisions** — 0 BUY/SELL decision events; cannot confirm lead into activation. Liquidity still evolved while Decision stayed NO_TRADE. |
| Does State lag Physics? | **No material lag** — State direction matched latest Physics on **100%** of comparable frames (149). State samples less often (frame cadence) but tracks Physics sign. |
| Does Behavior follow State? | **Weakly** — mapped direction agreement **24%**; Behavior remained NEUTRAL on most frames while State was UP/DOWN. |

**Event flip counts:** Physics 199 · Liquidity 1 · State 2 · Behavior 34 · Decision 0.

No optimization performed.

---

## 5. Performance statistics

| Metric | Value |
|--------|-------|
| Ingest/frame ops measured | 1050 |
| Append/ingest latency mean | **0.071 ms** |
| Latency p50 | **0.010 ms** |
| Latency p95 | **0.40 ms** |
| Latency max | **1.55 ms** |
| Final memory size | 1349 records |
| Peak records | 1349 |
| Capacity | 2048 (no overflow in session) |
| tracemalloc peak | ~242 KiB (session + controller) |

Passive Memory append path is negligible vs tick/DOM I/O and decision evaluate cost.

---

## 6. Architecture findings

1. **Memory fills correctly** for all five sources under controller live path (tick → physics; DOM → liquidity; frame → state/behavior/decision).  
2. **Append-only + ring buffer + frozen items** hold under structural and session tests.  
3. **Cadence asymmetry is real:** Physics ≫ Liquidity ≫ State/Behavior/Decision — Memory preserves evolution *at producer rates*, not a uniform clock.  
4. **Physics average persistence remains ultra-short** in chop (avg run ~3), consistent with Sprint 39 — Memory makes that visible; it does not invent longer horizon.  
5. **State tracks Physics direction tightly** at frame rate; **Behavior does not** in this session — cross-stream “Behavior follows State” is not generally true today.  
6. **Decision stream is useful for absence** (all NO_TRADE) as well as presence; INTERNAL lead/lag vs Liquidity needs a session that actually emits BUY/SELL_INTERNAL.  
7. **Global timestamp collisions are normal**; integrity must be judged **per source**.  
8. **No production live file** was available — re-run this audit against NT01/NT04 NDJSON before treating numbers as certification evidence.

---

## 7. Recommendations (audit conclusions — no fixes)

These are observation conclusions only — **not** implementation proposals.

1. Treat Sprint 42 controlled numbers as **plumbing + methodology validation**, not live market certification.  
2. Schedule a **production live audit** once `mnq_ticks.ndjson` / `mnq_dom.ndjson` are present; reuse the same metrics schema in `docs/evidence/sprint_42_memory_audit.json`.  
3. When INTERNAL signals appear, re-measure Liquidity→Decision lead times — currently unobservable.  
4. Keep Memory passive until a later sprint explicitly designs Decision reads (Sprint 40 migration).

---

## Stop

Sprint 42 ends here. **No product code changes.** Engines, thresholds, and Dashboard untouched.
