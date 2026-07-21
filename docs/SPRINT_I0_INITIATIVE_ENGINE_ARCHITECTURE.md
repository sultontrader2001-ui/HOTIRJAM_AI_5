# HOTIRJAM AI 5 — Sprint I-0  
# Initiative Engine Architecture

**Status:** Architecture only  
**Date:** 2026-07-22  
**Scope:** Design document. No implementation. No formulas. No calibration.  
**Authority:** Supersedes informal Module 02 assumptions where they conflict with this document.

---

## 1. Mission

The Initiative Engine answers exactly one question:

> **Who is currently pushing the market?**

| Output | Meaning |
|--------|---------|
| `BUY` | Buyers currently hold initiative |
| `SELL` | Sellers currently hold initiative |
| `NONE` | No clear controlling side |

It does **not** answer:

- Where the market wants to go → **Objective Engine**
- Whether the push can break structure → **Break Capability**
- Whether the opposing side is absorbing → **Response Engine**
- Whether the push is continuing or fading → **Continuation Engine**
- Whether to trade → **Decision / Execution** (out of scope for architecture modules)

---

## 2. Boundary with Objective Engine

| Concern | Owner |
|---------|-------|
| Structural map (battlefield) | Objective Engine |
| Who is pushing *now* | Initiative Engine |

**Hard rule:** Initiative must **not** take `ObjectiveSnapshot` (or any Objective field) as an input.

Rationale:

- Objective describes *where* structure is.
- Initiative describes *who* is currently exerting control.
- Coupling them recreates the current defect: Initiative confidence depends on map completeness (`is_complete`), which is unrelated to who is pushing.
- A market can have initiative with incomplete objectives, and objectives with no initiative.

---

## 3. Absolute prohibitions

The Initiative Engine **MUST NOT**:

1. Make trade decisions  
2. Generate BUY/SELL orders  
3. Generate entry signals  
4. Use Objective as an input  
5. Know anything about Execution, Trade Planning, Position Lock, or broker adapters  
6. Emit recommendations, entries, stops, or targets  
7. Mutate upstream market data or downstream engine state  

---

## 4. Proposed `InitiativeSnapshot` (fields only)

Observation artifact only. No trading semantics.

| Field | Type (conceptual) | Purpose |
|-------|-------------------|---------|
| `side` | `BUY` \| `SELL` \| `NONE` | Who currently controls the push |
| `strength` | scalar observation | How strong the controlling push is |
| `confidence` | scalar observation | How reliable the side label is from available evidence |
| `state` | intensity label | Coarse intensity of initiative (e.g. weak / medium / strong) — **not** a trade state |
| `reason` | ordered explanations | Human-readable evidence trail for `side` / `state` |
| `timestamp` | evaluation time | When this observation was formed |

### Explicitly out of the snapshot

| Do not include | Why |
|----------------|-----|
| Objective prices / distances | Objective ownership |
| Trade direction / order intent | Decision ownership |
| Break probability | Break Capability ownership |
| Response / absorption labels | Response ownership |
| Continuation / decay labels | Continuation ownership |
| Entry / exit / sizing | Execution / planning ownership |

### Naming note

Legacy Module 02 uses `initiative_side` (`BUYER`/`SELLER`) and separate component scores (`impulse_score`, `momentum_score`, `candle_strength_score`). Sprint I-0 proposes a **cleaner public contract** (`side`, `strength`, `confidence`, `state`, `reason`, `timestamp`). Internal detectors may still exist later; they are implementation detail, not architecture contract.

---

## 5. Responsibilities

### Initiative **is** responsible for

1. Observing which side currently exerts control (`BUY` / `SELL` / `NONE`)  
2. Observing the intensity of that control (`strength`, `state`)  
3. Expressing evidence quality (`confidence`, `reason`)  
4. Remaining deterministic and explainable from declared inputs  
5. Remaining independent of Objective, Decision, and Execution  

### Initiative **is not** responsible for

1. Defining structural objectives or persistence  
2. Measuring opposing absorption / counter-response  
3. Measuring continuation vs exhaustion of a push  
4. Estimating break probability against structure  
5. Classifying long-horizon market regime as a product decision  
6. Storing long-term narrative memory as a trading memory product  
7. Approving, blocking, or timing trades  

---

## 6. Input architecture

Inputs are categorized by **evidence type**, then mapped to **existing HOTIRJAM AI 5 modules**.

No formulas are defined here. This section answers only: *what may feed Initiative, and why*.

### 6.1 Allowed input categories

| Category | Question it helps answer | Belongs in Initiative? |
|----------|--------------------------|------------------------|
| **Force / Impulse** | Is there a sudden directional push? | Yes |
| **Momentum** | Is the push accelerating or merely present? | Yes |
| **Pressure** | Is one side persistently leaning? | Yes (short-horizon control pressure only) |
| **Energy / Activity** | Is the market active enough for initiative to be meaningful? | Yes (as confidence / validity evidence) |
| **Liquidity / Auction imbalance** | Which side is pressing the book? | Conditional — yes only as *who is pushing*, never as trade permission |
| **Market micro-behavior** | Is control accelerating, stalling, or flipping? | Conditional — short-horizon control only |
| **Raw market prints / bars** | Direct observation substrate | Yes (necessary carrier of force/momentum) |

### 6.2 Existing modules that should feed Initiative

| Module | Path | Category | Why it belongs |
|--------|------|----------|----------------|
| Live tick ingress | `live_data` | Raw market prints | Provides last, bid, ask, volume — the microscopic substrate of who is pushing |
| Tick / bar builder | `live_validator` candle glue (or future neutral bar module) | Raw bars | Aggregates prints into short windows where impulse and momentum are observable |
| Physics | `physics` → `PhysicsSnapshot` | Force / Momentum / Energy | `tick_velocity`, `tick_acceleration`, `tick_count`, spread/mid describe short-horizon push intensity and activity without deciding direction of trade |
| Liquidity | `liquidity` → `LiquiditySnapshot` | Liquidity / Pressure | `dom_imbalance`, `liquidity_shift` can evidence which side is pressing the auction |
| Market State | `market_state` → `MarketStateSnapshot` | Market State (micro) | Short-horizon directional activity (`direction`) and activity regime can support confidence that a push is real |
| Market Behavior | `market_behavior` → `BehaviorSnapshot` | Momentum / Pressure | `ACCELERATING` / related behaviors and `direction` describe control dynamics, not destination |

### 6.3 Existing modules that must **not** feed Initiative

| Module | Path | Why it must not belong |
|--------|------|------------------------|
| **Objective Engine** | `objective` | Answers *where*, not *who*. Hard ban. |
| **Objective Diagnostics** | `objective_diagnostics` | Structural eligibility evidence for Objective only |
| **Response Engine** | `response` | Measures opposing reaction *after* initiative; consumer of Initiative, not input |
| **Continuation Engine** | `continuation` | Measures whether initiative persists/fades; consumer, not input |
| **Break Capability** | `break_capability` | Measures ability to break Objective; requires Objective + Initiative + Response + Continuation |
| **Market Context** | `market_context` | Aggregator of many layers including decision-path context; too broad and already mixes concerns Initiative must not own |
| **Market Transition** | `market_transition` | Retrospective regime-change reporting; not “who is pushing now” |
| **Market Memory** | `memory` | Passive-horizon passive memory including decision-sourced items; Initiative must stay present-tense and non-decision |
| **Decision Foundation / Intent / Evaluation / Assessment** | `decision_*` | Decision workflow gates |
| **Trade Decision** | `trade_decision` | INTERNAL BUY/SELL/NO_TRADE policy |
| **Trade Planning / Position Lock** | `trade_planning`, `position_lock` | Plan and lock lifecycle |
| **Entry Timing / Performance** | `entry_timing`, `performance` | Post-signal analytics |
| **Dashboard / Live Validator UI** | `dashboard`, `live_validator` display | Presentation only |
| **Execution / Broker** | (not in AI5 architecture chain) | Orders and broker state |

### 6.4 Category detail — why each allowed category belongs

#### Force / Impulse

Belongs because initiative is first a statement about a **directional push**. Without force/impulse evidence, `BUY`/`SELL` is unverifiable.

#### Momentum

Belongs because a single impulse can be noise. Momentum distinguishes a controlling push from a one-bar flicker. Still about *who is pushing*, not *where price should go*.

#### Pressure

Belongs only as **short-horizon control pressure** (who is leaning). Must not become “pressure toward Objective,” which is Break Capability.

#### Energy / Activity

Belongs as **validity evidence**. In dead markets, initiative should trend to `NONE` or low confidence. Energy does not choose a trade side.

#### Liquidity / Auction imbalance

Belongs only if interpreted as **who is pressing the book**, not as permission to enter. Liquidity filters in Trade Decision remain outside Initiative.

#### Market State / Behavior (micro)

Belong only as **present-tense control context**. They must not import long-horizon narrative, transition history, or decision readiness.

---

## 7. Output consumers (architecture position)

Initiative sits after raw market evidence and **before** response/continuation/break.

```text
Market evidence (ticks / bars / physics / optional liquidity / micro-state)
        ↓
 Initiative Engine  →  InitiativeSnapshot (BUY | SELL | NONE)
        ↓
 Response Engine        (may consume Initiative)
        ↓
 Continuation Engine    (may consume Initiative)
        ↓
 Break Capability       (may consume Initiative + Objective + Response + Continuation)
```

Objective remains a **sibling map**, not a parent of Initiative:

```text
 Confirmed structure → Objective Engine → ObjectiveSnapshot
                                              ↘
                                               Break Capability
 Market push evidence → Initiative Engine → InitiativeSnapshot ↗
```

---

## 8. Current implementation debt (architecture findings only)

These are observations about today’s Module 02. They are **not** implementation tasks in I-0.

1. **`InitiativeInputs` currently requires `ObjectiveSnapshot`.** This violates the hard rule in §2–§3.  
2. **Scorer currently uses Objective only as `is_complete` confidence nudge.** That is still Objective coupling and must be removed in a later implementation sprint.  
3. **Live Validator feeds Objective + OHLC bars only.** Physics, liquidity, and market micro-state exist in AI5 but are not on the architecture Initiative path.  
4. **Main dashboard decision chain does not run Module 02.** Dual architectures remain a certification risk.  
5. **Public side labels differ** (`BUYER`/`SELLER` vs proposed `BUY`/`SELL`). Future implementation must choose one contract and migrate deliberately.  
6. **Initiative is not yet in the certification registry** as its own module row.

---

## 9. Architecture acceptance criteria for later sprints

A future Initiative implementation sprint may begin only if:

1. This document remains the contract  
2. Objective is removed from Initiative inputs  
3. Snapshot fields remain observation-only (`side`, `strength`, `confidence`, `state`, `reason`, `timestamp`)  
4. No Decision / Execution fields are introduced  
5. Any new input module is justified under §6 categories  
6. Unit tests cover: BUY, SELL, NONE, and independence from Objective  
7. Certification registry is updated when status advances  

---

## 10. Non-goals of Sprint I-0

- No code changes  
- No formula design  
- No threshold proposals  
- No calibration  
- No dashboard redesign  
- No wiring of physics/liquidity into Initiative yet  
- No commits  

---

## 11. Summary

Initiative Engine architecture:

- **One job:** who is currently pushing (`BUY` / `SELL` / `NONE`)  
- **One artifact:** `InitiativeSnapshot` with `side`, `strength`, `confidence`, `state`, `reason`, `timestamp`  
- **Allowed feeds:** short-horizon force, momentum, pressure, energy, optional liquidity imbalance, micro market state/behavior, raw ticks/bars  
- **Forbidden feeds:** Objective, diagnostics, Response, Continuation, Break, Decision stack, Memory-as-decision, Execution  
- **Sibling to Objective, not child of Objective**
