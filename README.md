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

**Out of scope still:** momentum, decision, BUY/SELL, AI, risk

Market/DOM/physics fields show `—` until enough live updates exist. No synthetic data.

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

Dashboard redraw uses line-diff updates when ANSI/VT is available; otherwise a Windows-safe full redraw. Display refresh is clamped to 250–500 ms (`--refresh`); tick/DOM polling stays faster (`--poll`, default 50 ms).

### PHYSICS section

| Measurement | Formula |
|-------------|---------|
| Spread | `ask − bid` |
| Mid Price | `(bid + ask) / 2` |
| Tick Velocity | `Δlast_price / Δt` |
| Tick Acceleration | `Δvelocity / Δt` |

Velocity needs ≥2 ticks; acceleration needs ≥2 velocity samples.

### Test

```bash
pytest
```

### Architecture (planned)

```
NinjaTrader (NT01/NT04) → Live Data → Physics → Momentum → Decision → Execution
```
