# HOTIRJAM AI 5

Professional AI assistant for MNQ futures trading (NinjaTrader + Python).

## Sprint status

| Sprint | Feature | Status |
|--------|---------|--------|
| 1 | Terminal dashboard | Done |
| 2 | Live tick ingress (NT01 NDJSON) | Done |
| 3 | Dashboard feed health monitor | Done |
| 4 | DOM ingress + visualization | Done |
| 5 | Physics measurements | Done |
| 6 | Market State Engine v1 | Done |
| 7 | Market Transition Engine v1 | Done |
| 8 | Market Behavior Engine v1 | Done |
| 9 | Market Context Engine v1 | Done |
| 10 | Decision Foundation v1 | Done |
| 12 | Decision Intent Engine v1 | Done |
| 13 | Decision Evaluation Engine v1 | Done |
| 14 | Decision Assessment Engine v1 | Done |
| 15 | Trade Decision Engine v1 (Skeleton) | Done |
| 16 | Trade Decision Policy v1 | Done |
| 17 | Trade Decision Policy v2 (Rule-Based NO_TRADE) | Done |
| 18 | Trade Authorization Policy v1 | Done |
| 19 | First BUY Rule v1 (framework, not emitted) | Done |
| 20 | BUY Conditions v1 (not emitted) | Done |
| 21 | Structured BUY Strategy v1 (not emitted) | Done |
| 22 | BUY Strategy Phase 3 — Physics Filter (not emitted) | Done |
| 23 | BUY Strategy Phase 4 — Liquidity Filter (not emitted) | Done |
| 24 | BUY Strategy Scoring Framework (not emitted) | Done |
| 25 | BUY Confidence Framework (not emitted) | Done |
| 26 | Decision Explanation Framework (not emitted) | Done |
| 27 | Liquidity Engine Integration (not emitted) | Done |
| 28 | Signal Stability Framework (not emitted) | Done |
| 29 | Decision Readiness Framework (not emitted) | Done |
| 30 | Internal BUY Activation (observation only) | Done |
| 31 | Internal SELL Activation (observation only) | Done |
| 32 | Performance Tracker + Multi-Timezone Logging | Done |
| 33 | Professional Live Dashboard v2 | Done |
| 34 | Full Decision Architecture Audit (audit only) | Done |
| 35 | Signed Market State & Behavior | Done |
| 36 | Decision Explainability Engine | Done |
| 37 | Entry Timing Audit (audit only) | Done |
| 38 | Decision Explainability v2 | Done |
| 39 | Decision Horizon Audit (audit only) | Done |
| 40 | Market Memory Architecture Design (design only) | Done |
| 41 | Market Memory v1 Foundation | Done |
| 42 | Market Memory Live Audit (audit only) | Done |
| 43 | Market Memory Diagnostics | Done |
| 44 | Market Memory Decision Integration v1 | Done |
| 45 | Professional Trading Dashboard v2 | Done |
| 46 | Lifetime Performance Dashboard | Done |
| 47 | Virtual 50K Prop Account Dashboard | Done |
| 48 | Professional Dual Column Dashboard | Done |

**Out of scope still:** tradable BUY, SELL, order execution, broker connectivity,
positions, risk

Market/DOM/physics fields show `—` until enough live updates exist. No synthetic data.
Market State is observation-only (UNKNOWN / QUIET / NORMAL / ACTIVE / TRENDING / VOLATILE)
with a signed direction (UP / DOWN / NEUTRAL) derived from tick velocity (Sprint 35).
Market Behavior carries a signed direction (BUY / SELL / NEUTRAL); directional
state/behavior award score points to one side only — NEUTRAL awards neither.
Market Transition retrospectively reports state changes; it does not forecast.
Market Behavior describes how the market is behaving; it does not advise trades.
Market Context aggregates observation layers into one immutable snapshot.
Decision Foundation only checks whether observation context is complete enough for a future decision.
Decision Intent maps foundation readiness to WAIT / OBSERVE / EVALUATE workflow steps only.
Decision Evaluation maps intent to IDLE / WAITING / EVALUATING lifecycle states only.
Decision Assessment maps evaluation status to BLOCKED / REVIEW / READY only.
Trade Decision emits observation-only `BUY_INTERNAL` / `SELL_INTERNAL` / `NO_TRADE`
with BUY/SELL scores and a DECISION EXPLANATION section that exposes real
input evidence (physics velocity/acceleration, liquidity shift/imbalance, state,
behavior, assessment, feed latency) plus contribution totals — no recalculation
(Sprint 36/38).
Decision horizon audit (Sprint 39): physics memory is 2–3 ticks; liquidity is one DOM
snapshot; the only multi-step gate is 3 dashboard evaluations (~0.75–1.5 s). See
`docs/SPRINT_39_DECISION_HORIZON_AUDIT.md`.
Market Memory architecture (Sprint 40, design only): a new layer stores evolution of
Physics / Liquidity / State / Behavior / Decision without replacing those engines.
See `docs/SPRINT_40_MARKET_MEMORY_ARCHITECTURE.md`.
Market Memory v1 (Sprint 41): passive bounded ring buffer + adapters. Does **not**
feed Trade Decision. Diagnostics via `memory_diagnostics` (no dashboard UI yet).
Market Memory live audit (Sprint 42): controlled-session evidence in
`docs/SPRINT_42_MARKET_MEMORY_LIVE_AUDIT.md` (production NDJSON absent at audit time).
Market Memory Diagnostics (Sprint 43): read-only Fast/Medium/Slow band summaries,
consensus, timeline, and store metrics via `build_memory_diagnostics` — not wired into
Trade Decision or dashboard rendering.
Market Memory Decision Integration v1 (Sprint 44): capped secondary BUY/SELL score
adjustment from Memory Diagnostics (max boost ±5 / oppose ±3). Primary category
thresholds unchanged. Memory never invents decisions.
Professional Trading Dashboard v2 (Sprint 45): visualization-only LIVE monitor with
MARKET / AI STATUS / TRADE DECISION / MEMORY panels.
Lifetime Performance Dashboard (Sprint 46): TODAY / LIFETIME / SIGNAL HISTORY / SYSTEM
statistics persisted to `logs/lifetime_performance.json` (survives restart; Today rolls
on the America/New_York calendar day). Visualization only — no trading-logic changes.
Virtual 50K Prop Account (Sprint 47): ACCOUNT STATUS panel driven by completed
observation trades (MNQ $2/pt default). Persists to `logs/virtual_account.json`.
Configurable starting balance / target / max drawdown. No broker. Statistics only.
Professional Dual-Column Dashboard (Sprint 48): layout-only redesign. Terminal width
≥160 → two columns (MARKET/AI/TRADE/MEMORY | TODAY/LIFETIME/ACCOUNT/SYSTEM) with
SIGNAL HISTORY full-width below; narrower terminals keep single-column fallback.
Unicode box drawing; no trading-logic changes.

### Requirements

- Python 3.13+
- macOS and Windows
- NinjaTrader 8 with **NT01** (`mnq_ticks.ndjson`) and **NT04** (`mnq_dom.ndjson`)

### Install

```bash
cd HOTIRJAM_AI_5
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run

```bash
python -m hotirjam_ai5
python -m hotirjam_ai5 \
  --tick-file "/path/to/HOTIRJAM/mnq_ticks.ndjson" \
  --dom-file "/path/to/HOTIRJAM/mnq_dom.ndjson"
```

Dashboard redraw uses line-diff updates when ANSI/VT is available; otherwise a Windows-safe full redraw. Display refresh is clamped to 250–500 ms (`--refresh`); tick/DOM polling stays faster (`--poll`, default 50 ms). The terminal layout is compact two-column (SYSTEM/LIVE MARKET, FEED/DOM HEALTH, PHYSICS/STATISTICS) plus MARKET ANALYSIS, CONTEXT, and DECISION FOUNDATION.

### PHYSICS section

| Measurement | Formula |
|-------------|---------|
| Spread | `ask − bid` |
| Mid Price | `(bid + ask) / 2` |
| Tick Velocity | `Δlast_price / Δt` |
| Tick Acceleration | `Δvelocity / Δt` |

Velocity needs ≥2 ticks; acceleration needs ≥2 velocity samples.

### MARKET STATE section

Observation-only classification from existing feed health, physics, and statistics.
States: `UNKNOWN`, `QUIET`, `NORMAL`, `ACTIVE`, `TRENDING`, `VOLATILE`.
Does not emit BUY/SELL, entries, exits, risk, or confidence.

### MARKET TRANSITION section

Compares consecutive `MarketStateSnapshot` values and reports completed transitions,
whether the state changed, and how long the prior/current state persisted.
`NONE` is displayed when no change occurred.

### MARKET BEHAVIOR section

Observation-only description from existing state, transition, physics, and health snapshots.
Behaviors: `UNKNOWN`, `STABLE`, `ACCELERATING`, `DECELERATING`, `BALANCED`, `UNSTABLE`.
Does not emit BUY/SELL, entries, exits, risk, or confidence.

### MARKET CONTEXT section

Aggregates existing state, transition, behavior, health, physics, and statistics snapshots
into one immutable `MarketContextSnapshot` with a concise descriptive summary.
Does not predict, score, or recommend trades.

### DECISION FOUNDATION section

Readiness gate over `MarketContextSnapshot` only.
Answers whether the observation layer is complete enough for a future decision.
Does not emit BUY/SELL, signals, confidence, probability, or risk.

### DECISION INTENT section

Workflow controller over `DecisionFoundationSnapshot` only.
Intents: `WAIT`, `OBSERVE`, `EVALUATE`.
Does not trade, score, or predict.

### DECISION EVALUATION section

Evaluation lifecycle over `DecisionIntentSnapshot` only.
Maps `WAIT` to `WAITING`, `OBSERVE` to `IDLE`, and `EVALUATE` to `EVALUATING`.
Does not inspect lower layers or produce trading outputs.

### DECISION ASSESSMENT section

Final evaluation standardization over `DecisionEvaluationSnapshot` only.
Maps `WAITING` to `BLOCKED`, `IDLE` to `REVIEW`, and `EVALUATING` to `READY`.
Does not emit BUY/SELL, orders, risk, probability, or confidence.

### TRADE DECISION section

Emits observation-only `SELL_INTERNAL` when SELL Decision Readiness is `READY`,
else `BUY_INTERNAL` when BUY Decision Readiness is `READY`, else `NO_TRADE`.
Displays mirrored BUY/SELL scores, confidence, stability, and readiness.
Internal activations are counted on the dashboard and appended to
`logs/signals.log`; they are never printed to the terminal display, which
shows only current dashboard state. They never reach orders, positions,
execution, or a broker. Tradable BUY and SELL remain unavailable.

### PERFORMANCE / LIFETIME stats

Analytics-only observer of `BUY_INTERNAL` / `SELL_INTERNAL`. Records each
activation (edge-triggered), evaluates price move after 5 minutes, and appends
completed evaluations to `logs/performance_log.jsonl`. Sprint 46 persists
TODAY / LIFETIME aggregates and the latest completed signal history to
`logs/lifetime_performance.json` (survives restart; Today rolls on the
America/New_York calendar day). Sprint 47 maps completed trades into a virtual
prop account (`logs/virtual_account.json`, default $50K / $2 per MNQ point).
Never connects to a broker or modifies Trade Decision.

### Live Dashboard v2

Default terminal layout (Sprint 48): dual-column when width ≥160 — left MARKET /
AI STATUS / TRADE DECISION / MEMORY; right TODAY / LIFETIME / ACCOUNT STATUS /
SYSTEM; SIGNAL HISTORY full width at the bottom. Narrower terminals use a single
column stack. Unicode box panels; NY/UZ wall times always visible. Pipeline
internals appear only with `--verbose`.

### Test

```bash
pytest
```

### Architecture (planned)

```
NinjaTrader (NT01/NT04) → Live Data → Physics → Market State → Market Transition → Market Behavior → Market Context → Decision Foundation → Decision Intent → Decision Evaluation → Decision Assessment → Trade Decision → (Performance Tracker observes) → Execution
```
