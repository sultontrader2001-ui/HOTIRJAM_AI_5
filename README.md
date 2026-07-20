# HOTIRJAM AI 5

Professional AI assistant for MNQ futures trading (NinjaTrader + Python).

## Sprint status

| Sprint | Feature | Status |
|--------|---------|--------|
| 1 | Terminal dashboard | Done |
| 2 | Live tick ingress (NT01 NDJSON) | Done |

**Out of scope still:** DOM, physics, momentum, decision, BUY/SELL, AI

Market fields show `—` until the first valid live tick. No synthetic prices. No historical replay (file tail starts at EOF).

### Requirements

- Python 3.13+
- macOS and Windows
- NinjaTrader 8 with **NT01_NinjaTraderTickExporter** writing `HOTIRJAM/mnq_ticks.ndjson`

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
# or with an explicit tick file:
python -m hotirjam_ai5 --tick-file "/path/to/HOTIRJAM/mnq_ticks.ndjson"
```

Override NinjaTrader user data dir:

```bash
export HOTIRJAM_NINJATRADER_USER_DATA_DIR="/path/to/NinjaTrader 8"
```

Press `Ctrl+C` to stop.

`Connection Status` stays `CONNECTING` until the first valid live tick, then `CONNECTED`. If no ticks arrive for `--stale-seconds` (default 5), status becomes `DISCONNECTED` and the log records `Connection lost`.

### Test

```bash
pytest
```

### Architecture (planned)

```
NinjaTrader (NT01) → Live Data → Physics → Momentum → Decision → Execution
```

Sprint 2 implements NT01 file ingress + live dashboard updates.
