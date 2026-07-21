# Sprint 40 — Market Memory Architecture Design

**Status:** DESIGN ONLY  
**Scope:** Specify a Market Memory Layer that stores evolution of existing observation engines.  
**Non-goals:** No implementation. No engine modifications. No threshold selection. No Trade Decision behavior change in this sprint.

**Depends on:** Sprint 39 Decision Horizon Audit (`docs/SPRINT_39_DECISION_HORIZON_AUDIT.md`).

---

## 1. Problem (from Sprint 39)

| Layer today | Memory | Effect |
|-------------|--------|--------|
| Physics | 2–3 ticks | Instant direction/momentum flips |
| Liquidity | 1 DOM snapshot | Book bias with no path |
| State / Behavior | Current sample (+ session avg rate) | Labels without measured persistence |
| Signal stability | 3 UI frames (~0.75–1.5 s) | Confirms **scores**, not market evolution |

**Result:** Micro-scalping / ultra-short reactive decisions. The AI does not understand how the market **evolved** into the current snapshot.

---

## 2. Design principle

Market Memory is a **new observation layer**. It does **not** replace:

- Physics  
- Liquidity  
- Market State  
- Market Behavior  

Those engines remain the **producers of instantaneous truth**. Memory **records their evolution** and exposes derived persistence views to consumers (eventually Trade Decision — not in this sprint).

```
Producers (unchanged contracts)
  PhysicsSnapshot
  LiquiditySnapshot
  MarketStateSnapshot (+ direction)
  MarketBehaviorSnapshot (+ direction)
  TradeDecisionSnapshot (observation-only history)
        │
        ▼
┌───────────────────────────┐
│   Market Memory Layer     │  append / expire / summarize
│   (design target)         │
└───────────────────────────┘
        │
        ▼
Consumers (future; not this sprint)
  Trade Decision Policy (optional read)
  Dashboard / diagnostics
  Entry Timing / Performance audits
```

---

## 3. Architecture diagram

```
                    Live ticks / DOM
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      PhysicsEngine   LiquidityEngine   FeedHealth
           │               │               │
           └───────┬───────┘               │
                   ▼                       │
            MarketStateEngine              │
                   │                       │
            MarketTransitionEngine         │
                   │                       │
            MarketBehaviorEngine           │
                   │                       │
            MarketContextEngine ◄──────────┘
                   │
                   │  current snapshots (unchanged)
                   ▼
         ┌─────────────────────┐
         │  Market Memory      │
         │  Ring buffers by    │
         │  stream + window     │
         └─────────┬───────────┘
                   │
         MemorySummary (Fast/Medium/Slow)
                   │
     Decision stack (Foundation → … → Trade Decision)
                   │
                   └── today: ignores Memory
                       future: may gate / score with persistence
```

**Ownership boundary:** Memory never recomputes velocity, DOM bias, state labels, or scores. It only stores and aggregates values already emitted by upstream engines.

---

## 4. Memory item schema

Every recorded observation is a **MemoryItem** (logical design — not a class yet):

| Field | Meaning | Source examples |
|-------|---------|-----------------|
| `timestamp` | Wall / event time of the sample | Engine snapshot timestamp |
| `stream` | Which producer | `PHYSICS` · `LIQUIDITY` · `STATE` · `BEHAVIOR` · `DECISION` |
| `direction` | Signed / categorical direction | Physics: sign(v); Liquidity: BUY/SELL/NEUTRAL; State: UP/DOWN/NEUTRAL; Behavior: BUY/SELL/NEUTRAL; Decision: BUY_INTERNAL/SELL_INTERNAL/NO_TRADE |
| `strength` | Magnitude of the observation | \|velocity\|, \|acceleration\|, imbalance confidence, score total, etc. |
| `confidence` | Reliability of this sample | Feed healthy? DOM healthy? Liquidity confidence? Assessment READY? |

**Rules:**

- Direction/strength/confidence are **copied or mapped** from existing fields — not invented in Memory.  
- One producer tick/DOM/frame may emit **one item per stream** (or a fixed multi-field packing — see §6).  
- Missing upstream values → item is skipped or recorded with direction `NONE` and strength `0` (design choice to freeze at implementation sprint).

### Streams to retain

| Stream | What evolves | Direction | Strength | Confidence |
|--------|--------------|-----------|----------|------------|
| **Physics** | Velocity / acceleration path | Sign of velocity (primary); accel as strength component | Combined or dual magnitudes | Feed healthy + finite Δt |
| **Liquidity** | Shift + imbalance path | Bias enum | Imbalance confidence / size ratio | DOM health |
| **Market State** | Regime + state_direction | UP/DOWN/NEUTRAL | Regime rank or \|velocity\| used in classification | Feed + non-UNKNOWN |
| **Behavior** | Behavior label + behavior_direction | BUY/SELL/NEUTRAL | Accel magnitude / label weight | Same as state readiness |
| **Decision** | Internal decision path | BUY_INTERNAL / SELL_INTERNAL / NO_TRADE | buy_score or sell_score | buy/sell confidence |

Decision history is for **audit and persistence of prior activations**, not a feedback loop into scoring unless a later certified design explicitly allows it.

---

## 5. Observation windows (bands — values not frozen)

Design uses **three horizon bands**. Exact durations are **not chosen** in Sprint 40; examples illustrate scale only.

| Band | Example scale | Role |
|------|---------------|------|
| **Fast Memory** | ~10 s (example) | Noise vs immediate continuation |
| **Medium Memory** | ~30 s (example) | Developing move / short momentum |
| **Slow Memory** | ~60 s (example) | Regime persistence / avoid micro-scalp only |

### Advantages / disadvantages (before picking numbers)

| Band | Advantages | Disadvantages |
|------|------------|---------------|
| **Fast** | Catches true micro-continuation; aligns with MNQ tick bursts; cheap to store | Still noisy; may not escape micro-scalping if used alone |
| **Medium** | Matches “developing move” intuition; useful persistence tests | Needs enough samples under slow tape; may lag sudden reversals |
| **Slow** | Distinguishes trend-like persistence from flicker | Over-smooths; session open/close regime shifts; larger buffer cost |
| **Multi-band together** | Decision can require Fast agree + Medium persist | Calibration surface grows; certification must freeze bands with evidence |

**Certification note:** Band durations are calibration candidates. Per methodology: no duration freeze without live audit evidence. Sprint 40 only defines the **slots**.

---

## 6. Memory flow

```
1. Upstream engine emits snapshot S at time t
2. MemoryAdapter maps S → MemoryItem(s) for that stream
3. Append to stream ring buffer (time-indexed)
4. Expire items outside Slow band (or Soft/Hard policies — §7)
5. On consumer query (or each dashboard frame):
     build MemorySummary:
       per stream × per band:
         dominant_direction
         persistence_ratio
         strength_mean / strength_trend
         sample_count
         confidence_mean
6. Publish MemorySnapshot (immutable) alongside MarketContext
```

**Sampling policy (design options — pick later):**

| Policy | Description | Fit |
|--------|-------------|-----|
| **Frame-sampled** | Append on each dashboard refresh (like today’s decision cadence) | Consistent with Trade Decision; under-samples tick physics |
| **Event-sampled** | Append on every physics tick / DOM update | High fidelity; larger buffers |
| **Hybrid** | Physics/Liquidity event-sampled; State/Behavior/Decision frame-sampled | Recommended default for design |

---

## 7. Design questions — answers

### 7.1 How should memory expire?

**Recommendation: Hybrid expiry.**

| Mode | Behavior | Use |
|------|----------|-----|
| **Rolling window (primary)** | Drop items older than Slow band wall-clock | Predictable horizons; matches Fast/Medium/Slow queries |
| **Event-based (secondary)** | Cap max samples per stream (e.g. if tape floods) | Protect memory under bursty MNQ |
| **Hard reset** | Clear on feed DISCONNECTED / session boundary | Avoid stitching stale pre-disconnect path |

Pure rolling window alone risks unbounded sample count under high tick rates. Pure event-based alone loses wall-clock meaning (“last 500 ticks” ≠ “last 30 seconds”).

### 7.2 How much history is enough?

Enough to answer: *“Has direction persisted longer than a few ticks / few frames?”*

| Intent | Minimum conceptual history |
|--------|----------------------------|
| Escape Sprint 39 micro horizon | ≫ 3 ticks and ≫ 3 UI frames |
| Short momentum | Medium band order of tens of seconds (example ~30 s) |
| Regime persistence | Slow band order of ~1 minute (example ~60 s) |
| Swing / multi-minute trend | Out of scope for v1 Memory; would need longer bands later |

**Enough for v1:** multi-band coverage through Slow example scale, with sample caps.  
**Not enough if:** only Fast band is wired into decisions — that would recreate micro-scalping with prettier buffers.

Exact sufficiency is an **evidence question** (live audit), not a design constant.

### 7.3 How should Decision Engine read memory?

**Read-only consumer of `MemorySnapshot` summaries — never raw buffer mutation.**

Proposed interaction stages (future sprints; ordered for certification safety):

1. **Diagnostics-only** — Dashboard / logs show persistence; Trade Decision unchanged.  
2. **Soft gate** — Require Medium-band direction agreement before READY / INTERNAL (thresholds later).  
3. **Score contribution** — Optional persistence points (new category or modifier) with full audit trail.  

**Must not:** recompute physics inside Decision; double-count current snapshot and memory of the same instant without a defined rule; create feedback where Decision history inflates the next Decision score without an explicit certified policy.

### 7.4 How should Physics contribute?

- Emit MemoryItems from existing `tick_velocity` / `tick_acceleration` (and optionally spread).  
- Direction = sign(velocity); Strength = \|v\| and/or \|a\| (schema allows one strength or a packed pair in implementation).  
- Physics engine **unchanged**; Memory listens (adapter) after `PhysicsEngine.on_tick` or from the snapshot already held by the controller.

### 7.5 How should Liquidity contribute?

- Emit MemoryItems from `liquidity_shift`, `dom_imbalance`, `confidence`.  
- Direction = shift (or require shift==imbalance for non-NEUTRAL direction).  
- Strength = confidence or size imbalance ratio.  
- Liquidity engine **unchanged**; adapter on `LiquidityEngine.on_dom` / latest snapshot.

### 7.6 How should persistence be measured?

Persistence is a **Memory-derived metric**, not a producer responsibility.

| Metric | Definition (design) |
|--------|---------------------|
| **Direction persistence ratio** | Fraction of samples in band whose `direction` equals target side (or equals majority) |
| **Same-sign run length** | Duration / count of consecutive agreeing samples ending at “now” |
| **Strength trend** | Sign of strength change across band (rising / falling / flat) — optional |
| **Agreement across streams** | Physics ∩ Liquidity ∩ State ∩ Behavior directions align within band |
| **Cross-band consistency** | Fast and Medium (and optionally Slow) share dominant direction |

**Single-tick sensitivity today** is mitigated when Decision requires e.g. Medium persistence ratio above a future calibrated floor — still **not calibrated here**.

---

## 8. Data ownership

| Component | Owns | Does not own |
|-----------|------|--------------|
| Physics / Liquidity / State / Behavior / Trade Decision engines | Current snapshot truth | Historical buffers |
| **Market Memory Layer** | Ring buffers, expiry, summaries, `MemorySnapshot` | Recomputation of producer formulas |
| Market Context | Optional pointer / embed of latest `MemorySnapshot` | Buffer mutation |
| Dashboard controller | Wiring: call Memory.update(...) after producers | Memory policy constants (live in Memory module) |
| Trade Decision | Future: read summary fields only | Writing into Memory except Decision stream append from its own output |

**Immutability:** Consumers receive frozen `MemorySnapshot` per evaluation cycle — same pattern as other AI 5 snapshots.

---

## 9. Interaction with existing engines

| Engine | Interaction |
|--------|-------------|
| Physics | Produce-only; Memory appends mapped items |
| Liquidity | Produce-only; Memory appends mapped items |
| Market State | Produce-only; Memory stores state + direction |
| Market Behavior | Produce-only; Memory stores behavior + direction |
| Market Transition | Optional: store transition events as sparse markers (not required for v1) |
| Market Context | May aggregate Memory summary into context for downstream |
| Decision Foundation → Assessment | Unchanged initially; later may treat “memory ready” as completeness |
| Trade Decision | Unchanged in design sprint; later reads MemorySnapshot |
| Signal Stability (3-frame) | Remains score-frame gate; Memory is **market** persistence, complementary not duplicate |
| Performance / Entry Timing | May correlate INTERNAL signals with pre-signal Memory persistence (audit) |

**Complementarity:** Signal stability asks “were scores high for 3 frames?” Memory asks “did the **market streams** agree in direction over Fast/Medium/Slow?”

---

## 10. Advantages

1. Separates **instantaneous measurement** from **evolution understanding**.  
2. Leaves LOCKED/certified producer math untouched when Memory is added.  
3. Multi-band design supports escaping micro-scalping without jumping to swing systems.  
4. Diagnostics-first migration avoids premature threshold changes.  
5. Persistence becomes measurable and auditable (Sprint 37 timing can be conditioned on Memory).  
6. Clear ownership reduces duplicated calculations (Sprint 38 explainability can later cite Memory summaries).

---

## 11. Risks

| Risk | Why it matters | Mitigation (design-level) |
|------|----------------|---------------------------|
| **Calibration explosion** | Three bands × many metrics × sides | Diagnostics-only first; change one constant later with evidence |
| **False sense of trend** | Slow band still short vs true trends | Name bands honestly; do not label Memory as trend-following |
| **Double counting** | Snapshot score + memory of same tick | Define whether current sample is included once in band |
| **Sampling bias** | Frame vs event sampling mismatch | Hybrid sampling policy; document cadence |
| **Stale memory after disconnect** | Prefill with dead path | Hard reset on feed/DOM disconnect |
| **Decision feedback loops** | Decision history boosting Decision | Decision stream audit-only until certified otherwise |
| **Cost / complexity** | Buffers under MNQ bursts | Max samples per stream + rolling Slow expiry |
| **Methodology violation** | Wiring Memory into scores too early | Certification registry: Memory NOT_STARTED → design → implement → audit before any gate |

---

## 12. Migration plan (no code this sprint)

| Phase | Work | Decision behavior |
|-------|------|-------------------|
| **40 (this)** | Architecture design frozen as doc | Unchanged |
| **41 (suggested)** | Implement Memory module + adapters + unit tests; diagnostics on dashboard/logs | Unchanged |
| **42 (suggested)** | Live audit: persistence distributions at INTERNAL vs NO_TRADE | Unchanged |
| **43+ (suggested)** | Controlled calibration: one persistence gate or score term | Change only with DX evidence |
| **Validate** | ≥1000 decisions with Memory-aware policy if behavior changes | Registry advance |

Each phase stops for evidence. No skipping audit → calibration.

---

## 13. Out of scope (explicit)

- Choosing Fast/Medium/Slow numeric durations  
- Implementing buffers or APIs  
- Changing Physics, Liquidity, State, Behavior, or Trade Decision  
- Threshold or weight changes  
- Claiming trend-following capability  

---

## 14. Design freeze statement

Sprint 40 freezes **intent and boundaries** only:

- Memory stores evolution; producers stay authoritative for current values.  
- MemoryItem = timestamp + direction + strength + confidence per stream.  
- Expiry = hybrid rolling + caps + disconnect reset.  
- Persistence measured in Memory summaries across multi-band windows.  
- Decision reads Memory later via immutable snapshot; migration is diagnostics-first.

**Stop.** No implementation in Sprint 40.
