# HOTIRJAM AI 5

Professional AI assistant for MNQ futures trading (NinjaTrader + Python).

## Sprint status

| Sprint | Feature | Status |
|--------|---------|--------|
| 1 | Terminal dashboard | Done |
| 2 | Live tick ingress (NT01 NDJSON) | Done |
| 3 | Dashboard feed health monitor | Done |
| 4 | DOM ingress + visualization | Done |

**Out of scope still:** physics, momentum, decision, BUY/SELL, AI

Market/DOM fields show `—` until the first valid live update. No synthetic data. No historical replay (file tails start at EOF).

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

Dashboard redraw uses line-diff updates (no full-screen clear / flicker). Display refresh is clamped to 250–500 ms (`--refresh`); tick/DOM polling stays faster (`--poll`, default 50 ms). LOG keeps significant events only.

### DOM section

| Field | Source |
|--------|--------|
| Best Bid/Ask Size | Top of book level size |
| Total Bid/Ask Size | `bid_total_size` / `ask_total_size` |
| Depth Levels | `depth_levels` |
| DOM Update Rate | Live updates/sec |

DOM HEALTH mirrors tick feed health (`HEALTHY` / `STALE` / `DISCONNECTED`).

LOG also records: `DOM connected`, `DOM stalled`, `DOM resumed`, `DOM connection lost`.

### Test

```bash
pytest
```

### Architecture (planned)

```
NinjaTrader (NT01/NT04) → Live Data → Physics → Momentum → Decision → Execution
```
