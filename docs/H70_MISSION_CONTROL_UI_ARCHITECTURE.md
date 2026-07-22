# Sprint H-7.0 — Mission Control UI Architecture Design

**Status: DESIGN ONLY (FROZEN INTENT)**  
**Scope:** Operator interface architecture for HOTIRJAM AI 5  
**Forbidden in this sprint:** Implementation · Code · Refactoring · Runtime / engine / logger / checkpoint changes

This document defines the complete Mission Control UI. It does not authorize code.

---

## 0. Design principles (absolute)

| # | Principle | Meaning |
|---|-----------|---------|
| 1 | **2-second comprehension** | Window 1 answers “what is the market doing, what does AI say, what happens next, am I safe?” without scrolling into debug |
| 2 | **No black boxes** | Every listed module is visible, expandable, and shows Status / Health / Latency / Inputs / Outputs / Confidence / Reason / History |
| 3 | **Presentation never computes** | UI reads latest frames / projections / timing / journals only. Never calls `hierarchy.evaluate`, `audit_objectives`, or re-runs engines for display (H-6.8.2 / H-6.9.3) |
| 4 | **Two missions, two windows** | Window 1 = Professional Trading. Window 2 = Complete AI Transparency. Future Window 3 = Developer Console (raw probes) |
| 5 | **Honesty over fantasy** | Modules that are DISABLED, Dashboard-only, evidence-fields, or not yet wired must show that state explicitly—not invent health |
| 6 | **R vs P preserved** | Runtime truth remains ObjectiveAuditReport **R**. Logger / summary chrome may use DiagnosticProjection **P**. Lab detail for Objective uses **R** from latest frame |

---

## 1. System context (today → Mission Control)

HOTIRJAM AI 5 today has **two observation spines**:

| Spine | Entry | Role |
|-------|-------|------|
| **Trade Decision Dashboard** | `python -m hotirjam_ai5` | Market → Physics/Liquidity → Market State → Decision stack → Memory / Account / History |
| **Live Validator / Certification + IDC** | `hotirjam-ai5-live-validator` | Tick → Objective → Initiative → Response → Continuation → Break; Logger **P**; Checkpoints; Decision/Execution **DISABLED** |

Mission Control **unifies these as operator windows**, not as a third engine. Window 1 is the trading cockpit (decision + account + market). Window 2 is the AI Laboratory (every architecture module). Window 3 (future) is developer/raw.

```
┌─────────────────────────────────────────────────────────────────┐
│                     MISSION CONTROL (operator)                   │
│  W1 Trading Cockpit  │  W2 AI Laboratory  │  W3 Developer (fut.) │
└───────────┬──────────┴─────────┬──────────┴──────────┬──────────┘
            │                    │                     │
            ▼                    ▼                     ▼
   Trade Decision spine    Architecture spine     Probes / dumps
   + Account / Memory      (LV frame R+P)         (no new engines)
   + System health         + Module cards
```

**Hard rule:** Mission Control is a **consumer**. It never becomes a producer of Objective / Response / Break / Decision truth.

---

## 2. Navigation model

### 2.1 Window chrome

```
┌──────────────────────────────────────────────────────────────────────┐
│ HOTIRJAM AI 5  ·  MISSION CONTROL          Feed: LIVE  Clock: HH:MM:SS│
│ [ 1 Cockpit ]  [ 2 Laboratory ]  [ 3 Developer · soon ]               │
│ Symbol MNQ   Mode: OBSERVE / SHADOW / LIVE*   Decision: ENABLED|OFF  │
└──────────────────────────────────────────────────────────────────────┘
```

\* LIVE trading mode is a future gate; Cockpit must still render when Decision/Execution are DISABLED (current LV truth).

| Input | Action |
|-------|--------|
| `1` | Focus Trading Cockpit |
| `2` | Focus AI Laboratory |
| `3` | Developer Console (future — show “NOT AVAILABLE”) |
| `Tab` / arrows | Move focus between Cockpit panels or Lab module cards |
| `Enter` / `E` | Expand / collapse selected Lab module |
| `Q` | Collapse to Lab overview / leave nested detail |
| `?` | Shortcut overlay (does not change layout) |

No mouse required for v1 (terminal-first). GUI port later must preserve the same information architecture.

### 2.2 Information density rule

| Window | Density | Scroll |
|--------|---------|--------|
| Cockpit | Fixed first viewport — **six panels only** | No vertical scroll for primary six; events list is a short ring (N≤8) |
| Laboratory | Overview grid + one expanded detail pane | Overview fits one screen; expand uses remaining height |
| Developer (future) | Dense, scrollable | Allowed |

---

## 3. Window 1 — Trading Cockpit

### 3.1 Purpose

Professional trading surface. Operator understands **entire AI trading state in ≤2 seconds**.

**Allowed panels only:**

1. Market  
2. AI Decision  
3. Next Trigger  
4. Account  
5. System Health  
6. Recent Events  

**Forbidden on Cockpit:** Debug dumps, full swing collections, hierarchy journal, loop-stage breakdowns, raw NDJSON, module dependency graphs, certification matrices.

### 3.2 Layout diagram (first viewport)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ W1 · TRADING COCKPIT                                                      │
├────────────────────────────┬─────────────────────────────────────────────┤
│                            │  2 · AI DECISION                            │
│  1 · MARKET                │  Side ........ BUY | SELL | FLAT | NONE     │
│  Symbol ...... MNQ         │  Action ...... ENTER | HOLD | EXIT | WAIT   │
│  Last ........ #####.##    │  Confidence .. ##%   Grade .. A|B|C|N/A     │
│  Bid/Ask ..... # / #       │  Reason ...... ≤2 lines (plain language)    │
│  Spread ...... #.# ticks   │  Architecture. Obj→Ini→Rsp→Cont→Brk strip   │
│  Tick rate ... ## /s       │  Decision eng. ENABLED | DISABLED           │
│  Latency ..... # ms        │  Execution ... DISABLED (always visible)    │
│  Session ..... RTH|ETH     │                                             │
├────────────────────────────┤  3 · NEXT TRIGGER                           │
│                            │  What would change the decision next?       │
│  4 · ACCOUNT               │  • Price vs Objective High/Low              │
│  Equity ......             │  • Initiative flip threshold                │
│  Open P&L ....             │  • Break probability gate                   │
│  Day P&L .....             │  • Risk / account limit (if armed)          │
│  Positions ...             │  Trigger distance .. # ticks | N/A          │
│  Risk status . OK|WARN|HALT│  ETA / condition ... one line               │
├────────────────────────────┴─────────────────────────────────────────────┤
│  5 · SYSTEM HEALTH                                                        │
│  Feed [■■■□] LIVE   Engines [■■■■] OK   Logger [■■□] OK   Ckpt [■□] OK │
│  Loop ##ms  Checkpoint ##ms  Logger ##ms  Stale? NO                       │
├──────────────────────────────────────────────────────────────────────────┤
│  6 · RECENT EVENTS (ring ≤8)                                              │
│  HH:MM:SS  INFO|WARN|ERROR  one-line message …                            │
└──────────────────────────────────────────────────────────────────────────┘
```

**2-second scan path (mandatory UX):**

1. Market Last + Feed color  
2. AI Decision Side + Action + Confidence  
3. Next Trigger one-liner  
4. System Health strip (any red?)  
5. Account Risk status  

If any of those five are red/amber, operator opens Laboratory for that module — not debug on Cockpit.

### 3.3 Panel contracts (Cockpit)

#### 1 · Market

| Field | Source spine | Notes |
|-------|--------------|-------|
| Last / Bid / Ask / Spread | Live tick / DOM if available | Missing → `NOT AVAILABLE` |
| Tick rate / Latency | Ingress / feed health | STALE if age > threshold |
| Session | Clock + calendar rules | Presentation only |

#### 2 · AI Decision

| Field | Source | Notes |
|-------|--------|-------|
| Side / Action / Confidence / Reason | Trade Decision dashboard spine when armed; else architecture strip only | When Decision **DISABLED**, show `DISABLED` large — never invent BUY/SELL |
| Architecture strip | Latest `ValidatorFrame` snapshots | Compact: Objective side · Initiative dominant · Response · Continuation · Break % |
| Execution | Always show DISABLED until broker adapter certified | |

#### 3 · Next Trigger

Forward-looking **conditions**, not predictions.

Derived only from latest engine outputs already on frame (distances, states, thresholds already computed). No new model.

Examples:

- “Price within X ticks of Objective High → re-evaluate Response”  
- “Initiative confidence below Y → Decision holds FLAT”  
- “Break probability ≥ Z → Halt new entries”  

If Decision DISABLED: Next Trigger describes **architecture state changes**, not trade orders.

#### 4 · Account

| Field | Source |
|-------|--------|
| Equity / Open / Day P&L / Positions | Virtual account (today) or broker later |
| Risk status | Prop rules / limits; `N/A` if Risk module not armed |

#### 5 · System Health

Aggregate lights only (detail lives in Laboratory):

| Light | Aggregates |
|-------|------------|
| Feed | Ingress LIVE/STALE/WAITING |
| Engines | Any Lab module CRITICAL → red |
| Logger | Snapshot Logger write/rotate health |
| Checkpoint | Hierarchy / Initiative checkpoint freshness |

Show last loop / checkpoint / logger ms as numbers, not graphs.

#### 6 · Recent Events

Append-only ring from existing AuditLog / event log. No stack traces on Cockpit.

---

## 4. Window 2 — AI Laboratory

### 4.1 Purpose

Complete AI transparency. **Every module appears. Every module expandable.** No module may be a black box.

### 4.2 Overview layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ W2 · AI LABORATORY                         Selected: OBJECTIVE  [ENTER]  │
├──────────────────────────────────────────────────────────────────────────┤
│ MODULE GRID (status · health · latency chips)                             │
│ ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐ │
│ │ DATA   ││ NORM.  ││PHYSICS ││ FORCE  ││ ENERGY ││ LIQUID ││ MKT ST │ │
│ │ ● OK   ││ ● OK   ││ ◐ DASH ││ ◐ INI  ││ ◐ INI  ││ ◐ MIX  ││ ◐ DASH │ │
│ └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘ │
│ ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐ │
│ │ MEMORY ││ OBJECT ││RESPONS ││CONTINU ││ BREAK  ││ RISK   ││ EXEC   │ │
│ │ ◐ DASH ││ ● LIVE ││ ● LIVE ││ ● LIVE ││ ● LIVE ││ ○ N/A  ││ ○ OFF  │ │
│ └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘ │
│ ┌────────┐┌────────┐                                                      │
│ │ LOGGER ││ CHECKP │                                                      │
│ │ ● LIVE ││ ● LIVE │                                                      │
│ └────────┘└────────┘                                                      │
├──────────────────────────────────────────────────────────────────────────┤
│ DEPENDENCY STRIP (live animation — see §7)                                │
│ Data → Norm → Physics → … → Objective → Response → Cont → Break → Risk→Ex│
│         ↘ Memory ↗              ↘ Logger / Checkpoint (side effects)      │
├──────────────────────────────────────────────────────────────────────────┤
│ EXPANDED MODULE DETAIL (8 mandatory sections)                             │
│ Status | Health | Latency | Inputs | Outputs | Confidence | Reason | Hist│
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Expanded module detail — mandatory sections

Every expanded module **must** render these eight blocks. Empty → explicit `NOT AVAILABLE` + reason code (UNWIRED / DISABLED / EVIDENCE_ONLY / DASHBOARD_ONLY / PENDING).

| Section | Content |
|---------|---------|
| **Status** | RUNNING / IDLE / STALE / DISABLED / UNWIRED / ERROR |
| **Health** | HEALTHY / DEGRADED / CRITICAL + one-line cause |
| **Latency** | Last evaluate / update ms; age of last output |
| **Inputs** | Named inputs with values or counts (not raw megabytes) |
| **Outputs** | Named outputs (snapshot fields) |
| **Confidence** | Module confidence if defined; else `N/A` |
| **Reason** | Why current output exists (plain language + evidence keys) |
| **History** | Last N state changes / transitions (from journals or ring buffers already maintained) |

**Expand never triggers recompute.**

### 4.4 Wiring honesty badges (required on every card)

| Badge | Meaning |
|-------|---------|
| `LIVE` | On Live Validator architecture path |
| `DASH` | Exists on Trade Decision dashboard spine only |
| `INI` | Not a standalone engine — Initiative evidence field |
| `OFF` | Intentionally DISABLED |
| `N/A` | Module not implemented as architecture engine |
| `MIX` | Partial: some signals LIVE, some DASH |

---

## 5. Module catalog (complete)

For each module: Purpose · Input · Output · Health · Performance · Visualization.

### 5.1 Data

| Aspect | Design |
|--------|--------|
| **Purpose** | Ingest live market reality (ticks, optional DOM) into typed observations |
| **Input** | NT01/NT04 NDJSON / ingress files; wall clock |
| **Output** | `LiveTick`, optional `DomSnapshot`, poll snapshot (batch size, gaps) |
| **Health** | WAITING / LIVE / STALE; parse error rate; gap detection |
| **Performance** | Poll ms; ticks/s; batch size; time since last tick |
| **Visualization** | Sparkline of tick arrivals; feed badge; last tick age bar |

### 5.2 Normalizer

| Aspect | Design |
|--------|--------|
| **Purpose** | Convert raw ingress into engine-ready structure (bars, confirmed swings). Today: parsers + `TickBarBuilder` + `SwingConfirmer` (no separate Normalizer package — Lab still shows this **stage**) |
| **Input** | Live ticks; bar period config |
| **Output** | OHLC candles; confirmed highs/lows; counts |
| **Health** | Candle continuity; swing confirm rate; empty buffers |
| **Performance** | Build ms per tick; candle count growth |
| **Visualization** | Mini OHLC strip; swing high/low markers count |

### 5.3 Physics

| Aspect | Design |
|--------|--------|
| **Purpose** | Describe motion of price (spread, mid, velocity, acceleration) |
| **Input** | Live ticks (Dashboard spine today) |
| **Output** | `PhysicsSnapshot` |
| **Health** | UNWIRED on LV path → badge `DASH`; HEALTHY when dashboard physics updates |
| **Performance** | Physics evaluate ms (dashboard loop) |
| **Visualization** | Velocity/acceleration gauges; mid vs last |

### 5.4 Force

| Aspect | Design |
|--------|--------|
| **Purpose** | Measure directional push / impulse intensity |
| **Input** | Candle / Initiative evidence inputs |
| **Output** | Scalar force (Initiative evidence); Response “strength” is **related but distinct** — Lab must not conflate labels |
| **Health** | Badge `INI` — always expandable; never pretend standalone engine |
| **Performance** | Included in Initiative evaluate latency |
| **Visualization** | Horizontal force bar (−/+/0); dominant side tint |

### 5.5 Energy

| Aspect | Design |
|--------|--------|
| **Purpose** | Measure activity / range-volume energy of the local auction |
| **Input** | OHLC / volume evidence |
| **Output** | Energy scalar (Initiative evidence) |
| **Health** | Badge `INI` |
| **Performance** | Shared with Initiative |
| **Visualization** | Energy meter 0–100; recent energy history sparkline |

### 5.6 Liquidity

| Aspect | Design |
|--------|--------|
| **Purpose** | Describe available liquidity / imbalance / shift |
| **Input** | DOM (Dashboard `LiquidityEngine`) and/or candle-side Initiative liquidity |
| **Output** | `LiquiditySnapshot` and/or Initiative liquidity evidence |
| **Health** | Badge `MIX` until DOM liquidity is on architecture path |
| **Performance** | DOM liquidity ms vs Initiative measure ms (show both if present) |
| **Visualization** | Bid/ask imbalance bar; liquidity shift arrow |

### 5.7 Market State

| Aspect | Design |
|--------|--------|
| **Purpose** | Classify regime (trend / range / volatile / unknown …) |
| **Input** | Physics + feed + stats (Dashboard) |
| **Output** | `MarketStateSnapshot` + direction |
| **Health** | Badge `DASH` on LV; CRITICAL only if dashboard path errors while Cockpit Decision armed |
| **Performance** | Evaluate ms on decision refresh cadence |
| **Visualization** | State chip + direction arrow + confidence |

### 5.8 Memory

| Aspect | Design |
|--------|--------|
| **Purpose** | Persist short-horizon market/decision memory for influence & audit |
| **Input** | Snapshots / adapters |
| **Output** | Memory diagnostics (band, consensus, timeline) |
| **Health** | Badge `DASH`; buffer fill %; corruption → CRITICAL |
| **Performance** | Append/read ms; ring occupancy |
| **Visualization** | Timeline of last N memory events; consensus meter |

### 5.9 Objective

| Aspect | Design |
|--------|--------|
| **Purpose** | Select nearest eligible structural High/Low battlefield |
| **Input** | Price, tick size, confirmed swings; hierarchy state |
| **Output** | `ObjectiveSnapshot`; runtime report **R**; projection **P** for log/summary |
| **Health** | Missing diagnostics → DEGRADED; stale checkpoint → WARN; dual-evaluate probe FAIL → CRITICAL |
| **Performance** | Hierarchy evaluate ms (≤1 per tick); derive(P) ms |
| **Visualization** | Price ladder vs selected High/Low; lifecycle chips; summary from **P**, detail from **R** |

### 5.10 Response

| Aspect | Design |
|--------|--------|
| **Purpose** | Describe how price is reacting to Objectives under Initiative |
| **Input** | Objective + Initiative + candles |
| **Output** | `ResponseSnapshot` (side, state, strength/confidence) |
| **Health** | LIVE on architecture path; incomplete inputs → DEGRADED |
| **Performance** | Response evaluate ms |
| **Visualization** | Reaction arrow; strength bar; state chip |

### 5.11 Continuation

| Aspect | Design |
|--------|--------|
| **Purpose** | Measure whether the response is continuing or decaying |
| **Input** | Objective + Initiative + Response + candles |
| **Output** | `ContinuationSnapshot` (score, weakening, confidence) |
| **Health** | LIVE; dependency on Response freshness |
| **Performance** | Continuation evaluate ms |
| **Visualization** | Continuation score gauge; decay sparkline |

### 5.12 Break

| Aspect | Design |
|--------|--------|
| **Purpose** | Measure break capability against structural objectives |
| **Input** | Full upstream architecture chain |
| **Output** | `BreakCapabilitySnapshot` (target, probability, pressure) |
| **Health** | LIVE; UNKNOWN target → DEGRADED not CRITICAL |
| **Performance** | Break evaluate ms |
| **Visualization** | Break probability meter; target side chip; pressure bar |

### 5.13 Risk

| Aspect | Design |
|--------|--------|
| **Purpose** | Constrain trade size / exposure / prop rules before execution |
| **Input** | Account, plan geometry, limits (future Risk engine) |
| **Output** | Allow / reduce / halt + reasons |
| **Health** | Badge `N/A` until Risk engine exists; Cockpit may show virtual “Risk Status” as **Account presentation**, not a Lab engine fake |
| **Performance** | N/A |
| **Visualization** | Limit bars (daily loss, contracts); gate lamp ALLOW/BLOCK when implemented |

### 5.14 Execution

| Aspect | Design |
|--------|--------|
| **Purpose** | Send / manage broker orders |
| **Input** | Armed decision + Risk allow |
| **Output** | Order intents / fills (future) |
| **Health** | Always show `OFF` / DISABLED until certified broker path |
| **Performance** | N/A while disabled |
| **Visualization** | Large DISABLED seal; no simulated fills disguised as live |

### 5.15 Logger

| Aspect | Design |
|--------|--------|
| **Purpose** | Persist observation frames for replay (diagnostics = **P** only) |
| **Input** | `ValidatorFrame` (serialize **P**, never full **R** collections) |
| **Output** | NDJSON lines; rotation; footprints |
| **Health** | Write/flush/rotate errors; schema version ≠ 1 → CRITICAL |
| **Performance** | Build / serialize / write / flush / rotate ms (exclusive timings) |
| **Visualization** | Bytes/line sparkline; phase cost bars; schema version chip |

### 5.16 Checkpoint

| Aspect | Design |
|--------|--------|
| **Purpose** | Persist hierarchy (and initiative) state across restarts |
| **Input** | Hierarchy version deltas; initiative lifecycle |
| **Output** | Checkpoint JSON; journal length; versions |
| **Health** | Write failure CRITICAL; stale vs hierarchy version WARN |
| **Performance** | Initiative vs hierarchy checkpoint exclusive ms; fsync cost |
| **Visualization** | Version counter; journal growth; write cadence (write iff version change) |

---

## 6. Module dependency graph

### 6.1 Logical operator graph (Mission Control)

```
                    ┌────────── Data ──────────┐
                    │                          │
                    ▼                          ▼
               Normalizer                   (DOM path)
                    │                          │
         ┌──────────┼──────────┐               │
         ▼          ▼          ▼               ▼
      Physics    Energy     Force         Liquidity
         │          │          │               │
         └────┬─────┴────┬─────┘               │
              ▼          ▼                     │
         Market State   Initiative evidence ───┘
              │                │
              │                ▼
           Memory         Objective ←── Hierarchy/Checkpoint
              │                │
              │                ▼
              │            Response
              │                │
              │                ▼
              │          Continuation
              │                │
              │                ▼
              │              Break
              │                │
              └───────┬────────┘
                      ▼
                    Risk ──(gate)──► Execution
                      │
              Logger ◄─┴─ Checkpoint (side persistence)
```

### 6.2 Runtime wiring honesty (must be visible on graph)

| Edge | Status today |
|------|----------------|
| Data → Normalizer → Objective → Response → Continuation → Break | **LIVE** (LV) |
| Initiative evidence (Force/Energy/Liquidity-candle) → Objective chain | **LIVE** |
| Data → Physics → Market State → Decision → Memory | **DASH** |
| DOM → LiquidityEngine | **DASH** |
| Break → Risk → Execution | **UNWIRED / OFF** |
| Frame → Logger (P) | **LIVE** |
| Hierarchy → Checkpoint | **LIVE** |

Lab graph uses **solid lines** for LIVE, **dashed** for DASH, **dotted** for UNWIRED/OFF.

---

## 7. Live animation · colors · failure

### 7.1 Live animation (Lab dependency strip)

| Animation | Meaning |
|-----------|---------|
| Soft pulse on node | Module produced new output this tick / refresh |
| Flow tick along edge | Upstream output consumed by downstream (presentation-only; based on timestamps) |
| Dim node | STALE / IDLE |
| Halt glyph on Execution | DISABLED |
| Flash once | Module entered CRITICAL (then stays solid red until cleared) |

Animation is **decorative confirmation of existing timestamps**, not a second clock domain. Cap FPS to presentation refresh (e.g. 4–10 Hz). Never animate by re-evaluating engines.

### 7.2 Module colors (identity — hue)

Stable identity colors (not health):

| Module | Hue token | Use |
|--------|-----------|-----|
| Data | Slate | Ingress |
| Normalizer | Steel | Structure |
| Physics | Cyan | Motion |
| Force | Orange | Push |
| Energy | Amber | Activity |
| Liquidity | Teal | Depth |
| Market State | Indigo | Regime |
| Memory | Violet | Recall |
| Objective | Blue | Battlefield |
| Response | Green | Reaction |
| Continuation | Lime | Persistence |
| Break | Magenta | Break risk |
| Risk | Gold | Constraints |
| Execution | White/Gray | Orders |
| Logger | Brown | Persist log |
| Checkpoint | Olive | Persist state |

Hue is for recognition. **Health overrides border/glow**, not fill identity.

### 7.3 Health colors

| Health | Color | Cockpit usage |
|--------|-------|---------------|
| HEALTHY | Green | Normal |
| DEGRADED | Amber | Attention — open Lab |
| CRITICAL | Red | Immediate — open Lab |
| UNKNOWN / N/A | Gray | Honest absence |
| DISABLED / OFF | Gray + strike | Intentional |

### 7.4 Failure colors / patterns

| Failure class | Pattern |
|---------------|---------|
| Feed failure | Red Data node + Cockpit Feed light |
| Engine exception | Red module + ERROR event |
| Logger schema / IO | Red Logger + CRITICAL System Health |
| Checkpoint IO / version stall | Red Checkpoint |
| Forbidden second evaluate detected | Red Objective + CRITICAL banner in Lab only |
| Decision armed while Execution OFF | Amber Execution (expected) — not red |

---

## 8. Operator workflow

```
Start Mission Control
    │
    ▼
┌─────────────┐     ≤2s scan
│ W1 Cockpit  │◄────────────────────────────┐
└──────┬──────┘                             │
       │ any amber/red OR curiosity         │
       ▼                                    │
┌─────────────┐   select module             │
│ W2 Lab Grid │──────────────────┐          │
└─────────────┘                  ▼          │
                          Expand module     │
                          8 sections read   │
                          History confirm   │
                                 │          │
                                 └──────────┘
                                        │
                        need raw dumps / probes
                                        ▼
                               W3 Developer (future)
```

**Operator decision loop**

1. Cockpit: Is feed live? Is decision clear? Is risk OK?  
2. If AI Decision unclear → Lab: Objective → Initiative evidence → Response → Continuation → Break  
3. If System Health amber → Lab: Data / Logger / Checkpoint  
4. Never chase stack traces on Cockpit  

---

## 9. Developer workflow (Window 3 — future)

Window 3 is **out of H-7.0 primary build**, but architected now:

| Capability | Notes |
|------------|-------|
| Raw `ValidatorFrame` / R dump | Read-only; size-warned |
| Hierarchy journal full | Scrollable |
| Loop timing exclusive tables | From existing probes |
| Evaluate probe stats | Max evals/tick |
| NDJSON tail | Schema-validated **P** |
| Fingerprints FP-R / FP-P / FP-S | Cert tooling |

Developer Console **must not** become the place operators trade from.

---

## 10. Mapping to existing IDC / dashboards (migration intent)

| Today | Mission Control target |
|-------|------------------------|
| Trade Decision Dashboard panels | Mostly **W1 Cockpit** (Market, Decision, Account, Memory→Lab, System, Events) |
| LV Certification Dashboard | Transitional → **W1 architecture strip** + **W2 cards** |
| IDC Objective / Initiative / Performance | **W2** expanded modules (Objective, Force/Energy/Liquidity-as-INI, Logger/Checkpoint/Perf) |
| IDC placeholders (Response, Cont, Break, …) | **W2** full module pages |
| Developer View (`D`) | Seeds **W3** |

No requirement to delete old UIs in design phase; implementation order below phases replacement.

---

## 11. Non-goals (this design)

- Redesigning Objective / Response / Break math  
- Changing logger to emit **R**  
- Enabling Execution  
- Inventing a Risk engine implementation  
- Collapsing Force/Energy into fake standalone runtime engines without stating `INI`  
- Mouse-only GUI as v1 requirement  

---

## 12. Recommended implementation order

Design-only sequencing for later sprints (each sprint still needs its own cert plan):

| Phase | Deliverable | Why first |
|-------|-------------|-----------|
| **H-7.1** | Mission Control shell + window switcher (W1/W2) reading **existing** frames only | Navigation without new truth |
| **H-7.2** | W1 Cockpit six-panel layout (Decision DISABLED honesty) | 2-second operator goal |
| **H-7.3** | W2 module grid + expand shell with 8 sections + wiring badges | No black box rule |
| **H-7.4** | Wire LIVE modules: Data, Normalizer, Objective, Response, Continuation, Break, Logger, Checkpoint | Architecture spine complete |
| **H-7.5** | Wire INI modules: Force, Energy, Liquidity (candle) under Initiative evidence contract | Transparency without false engines |
| **H-7.6** | Wire DASH modules: Physics, Market State, Memory, DOM Liquidity (read dashboard spine) | Unify transparency |
| **H-7.7** | Dependency graph + live animation + color system | Spatial understanding |
| **H-7.8** | Next Trigger panel rules (presentation-only predicates) | Cockpit foresight |
| **H-7.9** | W3 Developer Console (probes, fingerprints, raw R with size gate) | Cert / debug separation |
| **H-7.10** | Risk/Execution cards remain OFF until those engines certify | No fake trading |

**Certification note:** Any phase that changes presentation must preserve H-6.8.2 / H-6.9.3 (no second evaluate; logger = **P**).

---

## 13. Acceptance criteria for a future implementation sprint

Implementation may claim H-7.x complete only if:

1. W1 shows exactly the six panels — nothing else  
2. Operator can answer Market / Decision / Next / Account risk / System health in ≤2 seconds  
3. W2 lists all 16 modules; each expands to the eight sections  
4. UNWIRED / DISABLED / DASH / INI badges are truthful  
5. No presentation path calls `hierarchy.evaluate` / `audit_objectives`  
6. Execution cannot appear ENABLED without a separate Execution certification  
7. Color / health / failure semantics match §7  

---

## 14. Final gate statement

### Design completeness

Window diagrams, navigation, all 16 module contracts, dependency graph, animation/color systems, operator/developer workflows, and implementation order are specified above.

### Implementation authorization

# NOT AUTHORIZED

This document is **design only**. No code may ship under H-7.0. Implementation requires a subsequent sprint that cites this architecture and adds its own certification gates.
