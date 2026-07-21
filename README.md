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

**Out of scope still:** emitting BUY, SELL, order execution, broker connectivity, risk

Market/DOM/physics fields show `—` until enough live updates exist. No synthetic data.
Market State is observation-only (UNKNOWN / QUIET / NORMAL / ACTIVE / TRENDING / VOLATILE).
Market Transition retrospectively reports state changes; it does not forecast.
Market Behavior describes how the market is behaving; it does not advise trades.
Market Context aggregates observation layers into one immutable snapshot.
Decision Foundation only checks whether observation context is complete enough for a future decision.
Decision Intent maps foundation readiness to WAIT / OBSERVE / EVALUATE workflow steps only.
Decision Evaluation maps intent to IDLE / WAITING / EVALUATING lifecycle states only.
Decision Assessment maps evaluation status to BLOCKED / REVIEW / READY only.
Trade Decision keeps emitting `NO_TRADE` and reports BUY Score (setup quality) plus BUY Confidence (decision reliability), both 0–100.

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

Emits `NO_TRADE` only. Displays:
- `BUY Score       : XX / 100` (setup quality)
- `BUY Confidence : YY %` (decision reliability; independent of score)

BUY is not emitted. SELL remains unavailable.

### Test

```bash
pytest
```

### Architecture (planned)

```
NinjaTrader (NT01/NT04) → Live Data → Physics → Market State → Market Transition → Market Behavior → Market Context → Decision Foundation → Decision Intent → Decision Evaluation → Decision Assessment → Trade Decision → Execution
```
