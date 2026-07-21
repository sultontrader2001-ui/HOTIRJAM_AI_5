# Sprint 39 — Decision Horizon Audit

**Status:** AUDIT ONLY  
**Scope:** Measure how much market history each Trade Decision input actually uses.  
**Non-goals:** No changes to Decision Engine, Physics, Liquidity, thresholds, Dashboard, or Performance. No implementation.

---

## Verdict

HOTIRJAM AI 5 decides from an **ultra-short reactive horizon**.

| Layer | Effective memory |
|-------|------------------|
| Physics direction / momentum | Last **2–3 ticks** |
| Liquidity | **1** DOM snapshot |
| Market State / Behavior labels | Current magnitudes + session average tick rate |
| Only multi-step gate | **`SIGNAL_STABILITY_WINDOW = 3` dashboard evaluations** (~0.75–1.5 s at default refresh) |

There is **no** multi-second price persistence buffer, **no** bar/candle lookback, and **no** developing-move memory before `BUY_INTERNAL` / `SELL_INTERNAL`.

**Style estimate:** Micro scalping / ultra-short momentum — **not** swing momentum or trend following.  
**Mode:** Reacts. Does not anticipate.

---

## 1. Architecture timeline

Trade Decision is **not** evaluated per tick. Physics and liquidity update on ingress; decision scoring runs **once per dashboard refresh** (default **250 ms**).

```
Live tick (poll ≤ 50 ms)
  → FeedHealthMonitor.record_tick
  → PhysicsEngine.on_tick          # velocity: last 2 prices; accel: last 2 velocities
  → SessionStatistics.record_tick  # session tick_count / elapsed

Live DOM
  → DomHealthMonitor
  → LiquidityEngine.on_dom         # single latest book snapshot

DashboardController.snapshot()     # every refresh: 250–500 ms
  → MarketStateEngine.evaluate     # physics + session tick_rate + feed flags
  → MarketTransitionEngine         # previous state only + duration
  → MarketBehaviorEngine.evaluate  # physics + state + transition edge
  → MarketContextEngine.evaluate   # aggregator (no own history)
  → DecisionFoundation → Intent → Evaluation → Assessment
  → TradeDecisionEngine.evaluate   # scores + 3-frame stability + readiness
  → SELL_INTERNAL | BUY_INTERNAL | NO_TRADE
```

### Minimum history before `BUY_INTERNAL` / `SELL_INTERNAL`

| Prerequisite | Minimum |
|--------------|---------|
| Physics acceleration available | ≥ **3 ticks** with positive Δt |
| Liquidity present | ≥ **1** healthy DOM update |
| Feed `HEALTHY` | Last tick age &lt; **2 s** |
| Eligible state + direction | Current snapshot (ACTIVE/TRENDING + UP or DOWN) |
| Eligible behavior + direction | Current snapshot (STABLE/ACCELERATING + BUY or SELL) |
| Assessment `READY` | Foundation complete → Intent `EVALUATE` (no temporal smooth) |
| Signal stability | **3 consecutive** qualifying evaluations (score ≥ 80, confidence ≥ 85) |
| Readiness liquidity gate | shift **and** imbalance both match side |

**Wall-clock floor (default):** ~**0.75 s** of score confirmation (3 × 0.25 s), after physics has at least 3 ticks. Between frames many ticks may rewrite physics; only **frame-sampled** scores enter the stability window.

---

## 2. Observation window table

| Module | History Length | Snapshot / History | Direction | Persistence | Single Tick Sensitive |
|--------|----------------|--------------------|-----------|-------------|------------------------|
| **Physics** (spread/mid) | Current tick | Snapshot | No | No | YES |
| **Physics** (velocity) | Last **2** prices + timestamps | Minimal history | YES (sign of Δp/Δt) | No | YES |
| **Physics** (acceleration) | Last **2** velocity samples (≈ **3** ticks) | Minimal history | Momentum (Δv/Δt) | No | YES |
| **Liquidity** | Latest DOM only | Snapshot | Size bias only (not path) | No | YES (one DOM update) |
| **Market State** | Current physics + **session-average** `tick_rate` | Snapshot (+ session rate) | YES via current velocity sign | No (label “TRENDING” ≠ measured trend) | YES for regime/direction |
| **Market Behavior** | Current physics + state + one transition edge | Snapshot (+ prev state) | YES via current velocity sign | No | YES |
| **Market Transition** | Previous state + duration since change | Length-1 history | Retrospective change only | Duration only | YES when state flips |
| **Market Context** | None (pass-through) | Snapshot aggregator | Pass-through | No | YES (inherits upstream) |
| **Assessment** | None (maps evaluation status) | Snapshot | No | No | YES |
| **Trade Decision scores** | Current assessment/context/physics/liquidity | Snapshot | Directional gates | No | YES |
| **Signal Stability** | Last **3 evaluations** of (score, confidence) | History (score frames) | N/A | Score persistence only | Cold start: NO; after 2 qualify: YES on 3rd frame |
| **Feed Health** | Last-tick age; **1.0 s** rate window (display) | Hybrid | No | Connectivity only | YES |

### Per-module detail

#### Physics

- **History:** Spread/mid = last tick. Velocity = last 2 `last_price` values. Acceleration = last 2 velocity samples.
- **Type:** Hybrid (snapshot + consecutive sample).
- **Observes:** Direction (velocity sign), momentum (velocity + acceleration). No multi-sample persistence.
- **Single-tick flip:** **YES** — one new price rewrites velocity; one new velocity sample rewrites acceleration.
- **Evidence:** `physics/tick_velocity.py`, `physics/tick_acceleration.py`, `physics/measurements.py`.

#### Liquidity

- **History:** Single latest DOM (`total_bid`/`total_ask`, best sizes).
- **Type:** Snapshot.
- **Observes:** Current book bias only.
- **Single-tick/DOM flip:** **YES**.
- **Evidence:** `liquidity/engine.py`, `liquidity/classifier.py`.

#### Market State (+ `state_direction`)

- **History:** No own buffer. Uses current physics, feed flags, and `tick_rate = tick_count / session_elapsed` (entire session average — **not** a rolling N-second window). Feed’s `RATE_WINDOW_SECONDS = 1.0` is **not** used here.
- **Type:** Snapshot classification with session-average activity.
- **Observes:** Regime from current magnitudes; direction = sign of **current** tick velocity. Labels such as TRENDING are **not** backed by multi-tick persistence.
- **Single-tick flip:** **YES** for VOLATILE/TRENDING/direction.
- **Evidence:** `market_state/classifier.py`, `market_state/engine.py`, `dashboard/statistics.py`.

#### Market Behavior (+ `behavior_direction`)

- **History:** Current physics + market state + optional previous-state transition edge. Accel thresholds `0.5` / `3.0`.
- **Type:** Snapshot (+ length-1 transition).
- **Observes:** Momentum-like labels from signed acceleration; direction from current velocity. No multi-tick persistence.
- **Single-tick flip:** **YES**.
- **Evidence:** `market_behavior/engine.py`.

#### Assessment

- **History:** None — maps Decision Evaluation → BLOCKED / REVIEW / READY.
- **Type:** Snapshot.
- **Observes:** Workflow readiness only.
- **Single-tick flip:** **YES** when upstream foundation/intent flips.
- **Evidence:** `decision_assessment/engine.py`.

#### Decision Engine (Trade Decision Policy)

- **History:** Scores from current inputs. Only rolling memory: BUY/SELL deques of length **`SIGNAL_STABILITY_WINDOW = 3`**. Gates: score ≥ 80, confidence ≥ 85.
- **Type:** Snapshot scoring + 3-evaluation confirmation.
- **Observes:** Directional alignment of state/behavior/physics/liquidity. Stability confirms **high scores across frames**, not price path persistence.
- **Single evaluation flip:** Scores **YES**. Emission from cold start **NO** (needs 3 qualifying frames). After two qualify, the third frame **can** emit.
- **Evidence:** `trade_decision/policy.py`, `trade_decision/engine.py`.

---

## 3. Critical findings

1. **Physics memory is 2–3 ticks.** Velocity and acceleration are consecutive differences, not rolling averages. One noisy tick can reverse “Physics confirmed.”

2. **Liquidity has zero temporal depth.** Book bias is the latest print only. No resting-order persistence, no shift-over-time.

3. **“TRENDING” / “ACCELERATING” are instantaneous labels.** They do not measure a developing move over seconds or minutes. `state_direction` / `behavior_direction` are the sign of the current velocity sample.

4. **Session `tick_rate` is not a decision lookback.** It averages activity over the whole session and can lag true short-horizon activity. Market State does not use the 1-second feed rate window.

5. **The only intentional persistence gate is score stability across ~0.75–1.5 s of UI frames.** That confirms that **scores stayed high**, not that price or order flow persisted in the signal direction.

6. **Decision cadence ≠ tick cadence.** Many ticks can rewrite physics between two stability samples; the engine never requires N consecutive ticks of same-sign velocity.

7. **Architecture reacts; it does not anticipate.** Market Transition is retrospective. No forecasts, no lead indicators, no path projection.

8. **Observation history is too short** for validating a developing market move, swing momentum, or trend following. It is **sufficient only** for ultra-short reactive micro-confirmation of the current snapshot.

---

## 4. Recommendations (audit conclusions — no fixes)

These are **characterization** recommendations for certification planning. They are **not** implementation proposals.

1. **Classify the live system as micro-scalping / ultra-short momentum** for any performance or entry-timing interpretation (including Sprint 37 MFE/MAE windows of 30s–5m, which are far longer than the decision horizon).

2. **Treat “TRENDING” and “ACCELERATING” as current-sample labels**, not evidence of multi-second persistence, when reading logs or dashboards.

3. **When judging false activations**, assume single-tick / single-DOM sensitivity upstream of the 3-frame score gate — score stability alone does not prove a developing move.

4. **Keep Sprint 39 evidence locked as the horizon baseline** before any future horizon-extension design. Do not change thresholds or engines in this sprint.

5. **Defer fix design** to a later sprint only after live evidence shows horizon mismatch against intended strategy class.

---

## Evidence map (key constants)

| Constant | Value | File |
|----------|-------|------|
| Velocity history | last 2 prices | `physics/tick_velocity.py` |
| Acceleration history | last 2 velocity samples | `physics/tick_acceleration.py` |
| `SIGNAL_STABILITY_WINDOW` | 3 evaluations | `trade_decision/policy.py` |
| Score / confidence gates | 80 / 85 | `trade_decision/policy.py` |
| Eligible states | ACTIVE, TRENDING | `trade_decision/policy.py` |
| Eligible behaviors | STABLE, ACCELERATING | `trade_decision/policy.py` |
| Session `tick_rate` | `tick_count / elapsed` | `dashboard/statistics.py` |
| Feed rate window | 1.0 s (health/display only) | `dashboard/feed_health.py` |
| Decision refresh | 0.25 s default | `dashboard/app.py` |

---

## Stop

Sprint 39 ends here. No code or threshold changes.
